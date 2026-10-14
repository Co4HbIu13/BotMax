"""Main entry point for BotMAX: FastAPI server + MAX Messenger Bot"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Add current directory and src to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config import Config
from src.logger import setup_logger, get_logger
from src.database.db import Database
from src.database.seed import seed_default_raffles
from src.services.sbp import SBPService
from src.services.notification import NotificationService
from src.services.lottery import LotteryService
from src.services.admin_auth import AdminAuthService
from src.bot.bot_app import BotApp
from src.api.routes import setup_routes

STATIC_DIR = BASE_DIR / "src" / "static"
INDEX_HTML = STATIC_DIR / "index.html"
ADMIN_HTML = STATIC_DIR / "admin.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for database, background workers, and MAX bot"""
    logger = get_logger("botmax.lifespan")
    config: Config = app.state.config
    db: Database = app.state.db
    lottery_service: LotteryService = app.state.lottery_service
    bot_app: BotApp = app.state.bot_app

    logger.info("Initializing database and seeding default raffles...")
    await db.connect()
    await seed_default_raffles(db)

    # 1. Start background worker for auto-releasing expired ticket reservations
    logger.info("Launching ticket auto-release background worker...")
    release_task = asyncio.create_task(lottery_service.start_auto_release_worker())

    # 2. Start MAX Bot in long-polling mode (or webhook mode)
    bot_task = None
    if config.max_bot_token:
        logger.info(f"Launching MAX Bot in background (Mode: {config.run_mode})...")
        bot_task = asyncio.create_task(bot_app.start_polling())
    else:
        logger.warning("MAX_BOT_TOKEN not provided; bot polling disabled.")

    yield

    # Shutdown sequence
    logger.info("Shutting down BotMAX...")
    release_task.cancel()
    if bot_task:
        bot_task.cancel()
    await bot_app.close()
    await db.close()
    logger.info("BotMAX shutdown complete.")


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    config = Config.from_env()
    config.ensure_directories()

    setup_logger(
        name="botmax",
        log_level=config.log_level,
        log_file=config.log_file,
    )
    logger = get_logger("botmax")
    logger.info(f"Initializing BotMAX on {config.host}:{config.port}...")

    app = FastAPI(
        title="BotMAX API & Mini-App",
        description="MAX Messenger Bot and Mini-App with SBP Payments and Ticket Drawdown",
        version="2.0.0",
        lifespan=lifespan,
    )

    # Enable CORS for webview & standalone browser
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def frame_options_middleware(request: Request, call_next):
        response = await call_next(request)
        if "X-Frame-Options" in response.headers:
            del response.headers["X-Frame-Options"]
        if "x-frame-options" in response.headers:
            del response.headers["x-frame-options"]
        response.headers["Content-Security-Policy"] = "frame-ancestors * https: http:;"
        return response

    # Initialize Core Services
    db = Database(config.database_path)
    sbp_service = SBPService(
        merchant_id=config.sbp_merchant_id, secret_key=config.sbp_secret_key
    )
    notification_service = NotificationService(
        db=db, admin_ids=config.admin_ids, mini_app_url=config.mini_app_url
    )
    lottery_service = LotteryService(
        db=db,
        sbp_service=sbp_service,
        notification_service=notification_service,
        reservation_duration_minutes=config.reservation_duration_minutes,
    )
    bot_app = BotApp(
        config=config,
        db=db,
        lottery_service=lottery_service,
        notification_service=notification_service,
    )
    auth_service = AdminAuthService(
        admin_password=config.admin_password,
        secret_key=config.admin_session_secret,
        db=db,
    )

    # Store in app state
    app.state.config = config
    app.state.db = db
    app.state.sbp_service = sbp_service
    app.state.notification_service = notification_service
    app.state.lottery_service = lottery_service
    app.state.auth_service = auth_service
    app.state.bot_app = bot_app

    # Mount REST API
    api_router = setup_routes(
        lottery_service=lottery_service,
        sbp_service=sbp_service,
        db=db,
        notification_service=notification_service,
        auth_service=auth_service,
        config=config,
    )
    app.include_router(api_router)

    # Mount Static Files & Uploaded Prize Photos
    UPLOADS_DIR = BASE_DIR / "data" / "uploads"
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Serve Admin Control Dashboard
    @app.get("/admin")
    @app.get("/admin/")
    async def serve_admin_panel(request: Request):
        """Serve BotMAX Secure Admin Dashboard"""
        if ADMIN_HTML.exists():
            return FileResponse(str(ADMIN_HTML))
        return HTMLResponse("<h1>BotMAX Admin Panel</h1><p>admin.html not found</p>")

    # Serve Mini-App Frontend
    @app.get("/")
    @app.get("/app")
    @app.get("/pay")
    async def serve_mini_app(request: Request):
        """Serve Mini-App Single Page Application"""
        if INDEX_HTML.exists():
            return FileResponse(str(INDEX_HTML))
        return HTMLResponse("<h1>BotMAX Mini-App</h1><p>index.html not found</p>")

    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "ok", "app": "botmax", "version": "2.0.0"}

    # Direct APK Download Endpoint
    @app.get("/apk")
    @app.get("/download-apk")
    async def download_apk():
        """Direct download endpoint for BotMAX Admin Android APK"""
        apk_path = STATIC_DIR / "botmax-admin.apk"
        if apk_path.exists():
            return FileResponse(
                str(apk_path),
                media_type="application/vnd.android.package-archive",
                filename="BotMAX-Admin.apk",
            )
        return HTMLResponse("<h1>Файл APK не найден</h1>", status_code=404)

    return app


app = create_app()


def main():
    """Application runner"""
    config = Config.from_env()
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    main()