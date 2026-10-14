import base64
import logging
import re
import secrets
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Request, Header, Depends, status, UploadFile, File
from pydantic import BaseModel, Field

from ..services.lottery import LotteryService
from ..services.sbp import SBPService
from ..services.notification import NotificationService
from ..services.admin_auth import AdminAuthService
from ..database.db import Database
from ..config import Config
from ..bot.keyboards import group_showcase_keyboard

logger = logging.getLogger("botmax.api")

api_router = APIRouter(prefix="/api")


# ==========================================
# PYDANTIC SCHEMAS
# ==========================================
class ReserveTicketsRequest(BaseModel):
    user_id: int
    username: Optional[str] = "max_user"
    ticket_numbers: Optional[List[int]] = None
    random_count: Optional[int] = None


class SBPWebhookPayload(BaseModel):
    qrid: Optional[str] = None
    order_id: Optional[str] = None
    status: str = "SUCCESS"  # SUCCESS, FAILED
    amount: Optional[float] = None


class AdminLoginRequest(BaseModel):
    username: Optional[str] = "superadmin"
    password: str


class CreateAdminUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=4, max_length=100)
    display_name: str = Field(min_length=2, max_length=100)
    role: Optional[str] = "admin"
    sbp_phone: Optional[str] = ""
    sbp_bank: Optional[str] = "СБП"


class UpdateAdminProfileRequest(BaseModel):
    display_name: Optional[str] = None
    sbp_phone: Optional[str] = None
    sbp_bank: Optional[str] = None
    password: Optional[str] = None


class UploadImageRequest(BaseModel):
    filename: Optional[str] = "prize.jpg"
    image_data: str  # Base64 string or data URL


class RafflePrizeItem(BaseModel):
    place: int = Field(default=1, ge=1)
    lot_number: int = Field(default=1, ge=1)
    title: str = Field(min_length=1, max_length=150)
    description: Optional[str] = ""
    prize_image_url: str = Field(default="")


class CreateRaffleRequest(BaseModel):
    id: Optional[str] = None
    title: str = Field(min_length=2, max_length=150)
    description: Optional[str] = ""
    lot_number: Optional[int] = None
    category: Optional[str] = "lot"
    prize_image_url: Optional[str] = ""
    total_tickets: int = Field(gt=0, le=5000)
    price_per_ticket: float = Field(gt=0)
    prizes: Optional[List[RafflePrizeItem]] = None


class UpdateRaffleStatusRequest(BaseModel):
    status: str  # active, completed, cancelled


class CancelOrderRequest(BaseModel):
    user_id: Optional[int] = None


def setup_routes(
    lottery_service: LotteryService,
    sbp_service: SBPService,
    db: Database,
    notification_service: NotificationService,
    auth_service: AdminAuthService,
    config: Config,
) -> APIRouter:
    """Setup and configure all API routes with dependencies"""

    # ------------------------------------------
    # SECURITY DEPENDENCIES (ROLE-BASED)
    # ------------------------------------------
    async def require_admin(
        request: Request,
        authorization: Optional[str] = Header(None),
        x_admin_token: Optional[str] = Header(None),
    ) -> Dict[str, Any]:
        """Verify admin session token from header or cookie and return admin details"""
        token = None
        if x_admin_token:
            token = x_admin_token
        elif authorization and authorization.startswith("Bearer "):
            token = authorization.split("Bearer ", 1)[1].strip()
        elif "admin_token" in request.cookies:
            token = request.cookies.get("admin_token")

        admin = auth_service.get_session_admin(token)
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Доступ ограничен. Требуется авторизация администратора.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return admin

    async def require_superadmin(
        current_admin: Dict[str, Any] = Depends(require_admin),
    ) -> Dict[str, Any]:
        """Verify that current admin has SuperAdmin role"""
        if current_admin.get("role") != "superadmin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ запрещен. Действие доступно только Главному СуперАдминистратору.",
            )
        return current_admin

    # ==========================================
    # 1. PUBLIC MINI-APP ENDPOINTS
    # ==========================================
    @api_router.get("/raffles")
    async def get_raffles():
        """Get all active raffles with live inventory drawdown statistics"""
        raffles = await lottery_service.get_active_raffles()
        return {"success": True, "raffles": raffles}

    @api_router.get("/raffles/{raffle_id}")
    async def get_raffle(raffle_id: str):
        """Get raffle details and full ticket grid (states of tickets 1..N)"""
        details = await lottery_service.get_raffle_details(raffle_id)
        if not details:
            raise HTTPException(status_code=404, detail="Розыгрыш не найден")
        return {"success": True, "raffle": details}

    @api_router.post("/raffles/{raffle_id}/reserve")
    async def reserve_tickets(raffle_id: str, req: ReserveTicketsRequest):
        """
        Reserve tickets for SBP checkout.
        Atomically decreases available ticket pool ('убытие билетов') for 10 minutes.
        """
        await db.upsert_user(user_id=req.user_id, username=req.username)

        if req.random_count and req.random_count > 0:
            result = await lottery_service.reserve_random_tickets(
                raffle_id=raffle_id,
                user_id=req.user_id,
                username=req.username or f"user_{req.user_id}",
                count=req.random_count,
            )
        elif req.ticket_numbers:
            result = await lottery_service.reserve_specific_tickets(
                raffle_id=raffle_id,
                user_id=req.user_id,
                username=req.username or f"user_{req.user_id}",
                ticket_numbers=req.ticket_numbers,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Укажите номера билетов (ticket_numbers) или их количество (random_count)",
            )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "Ошибка бронирования"))

        return result

    @api_router.get("/orders/{order_id}")
    async def get_order(order_id: str):
        """Get order status, ticket numbers, and expiration timer"""
        order = await db.get_order(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Заказ не найден")
        return {"success": True, "order": order}

    @api_router.post("/orders/{order_id}/confirm-simulation")
    async def confirm_simulation(order_id: str):
        """
        1-Click SBP Payment Simulation (for testing, demonstration, and instant checkout verification).
        Permanently sells tickets and triggers MAX Bot push notification!
        """
        result = await lottery_service.complete_sbp_payment(order_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "Ошибка оплаты"))
        return result

    @api_router.post("/payments/sbp/webhook")
    async def sbp_webhook(
        payload: SBPWebhookPayload,
        request: Request,
        x_signature: Optional[str] = Header(None),
    ):
        """
        Bank webhook endpoint for SBP payments.
        Accepts bank notifications and permanently finalizes tickets.
        """
        order_id = payload.order_id
        if not order_id and payload.qrid:
            conn = await db.connect()
            async with conn.cursor() as cur:
                await cur.execute("SELECT id FROM orders WHERE sbp_qrid = ?", (payload.qrid,))
                row = await cur.fetchone()
                if row:
                    order_id = row["id"]

        if not order_id:
            raise HTTPException(status_code=400, detail="Order ID could not be identified")

        if payload.status.upper() in ("SUCCESS", "PAID", "CONFIRMED"):
            result = await lottery_service.complete_sbp_payment(order_id)
            return {"status": "ok", "result": result}

        return {"status": "ignored", "reason": f"Status is {payload.status}"}

    @api_router.get("/users/{user_id}/tickets")
    async def get_user_tickets(user_id: int):
        """Get all tickets purchased by a specific user"""
        tickets = await db.get_user_tickets(user_id)
        return {"success": True, "tickets": tickets}

    @api_router.get("/users/{user_id}/active-reservation")
    async def get_active_reservation(user_id: int):
        """Retrieve active pending order for user with payment data and ticket numbers"""
        order = await lottery_service.get_user_active_reservation(user_id)
        return {"success": True, "has_active": bool(order), "order": order}

    @api_router.post("/orders/{order_id}/cancel")
    async def cancel_order(order_id: str, req: Optional[CancelOrderRequest] = None):
        """Cancel reservation and release tickets back to available pool"""
        user_id = req.user_id if req else None
        result = await lottery_service.cancel_reservation(order_id, user_id=user_id, is_admin=False)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "Не удалось отменить бронь"))
        return result

    # ==========================================
    # 2. ADMIN AUTHENTICATION & PROFILE ENDPOINTS
    # ==========================================
    @api_router.post("/admin/auth/login")
    async def admin_login(req: AdminLoginRequest, request: Request):
        """
        Authenticate administrator/organizer and issue a cryptographically signed session token.
        Features brute-force rate limit protection and multi-tenant admin lookup.
        """
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        success, msg, token, admin_info = await auth_service.authenticate(
            username=req.username,
            password=req.password,
            client_ip=client_ip,
        )
        if not success:
            raise HTTPException(status_code=401, detail=msg)

        return {
            "success": True,
            "token": token,
            "admin": admin_info,
            "message": msg,
        }

    @api_router.get("/admin/auth/verify")
    async def admin_verify(current_admin: Dict[str, Any] = Depends(require_admin)):
        """Check if current admin session is valid and return profile info"""
        return {"success": True, "authenticated": True, "admin": current_admin}

    @api_router.get("/admin/me")
    async def get_admin_me(current_admin: Dict[str, Any] = Depends(require_admin)):
        """Fetch profile and SBP payout details of currently logged in admin"""
        admin = await db.get_admin_by_id(current_admin["id"])
        return {"success": True, "admin": admin or current_admin}

    @api_router.put("/admin/me")
    async def update_admin_me(
        req: UpdateAdminProfileRequest,
        current_admin: Dict[str, Any] = Depends(require_admin),
    ):
        """Update personal display name, SBP phone/bank, or password"""
        await db.update_admin(
            admin_id=current_admin["id"],
            display_name=req.display_name,
            sbp_phone=req.sbp_phone,
            sbp_bank=req.sbp_bank,
            password=req.password,
        )
        updated = await db.get_admin_by_id(current_admin["id"])
        return {"success": True, "admin": updated, "message": "Профиль и реквизиты СБП обновлены"}

    @api_router.post("/admin/auth/logout")
    async def admin_logout(
        request: Request,
        authorization: Optional[str] = Header(None),
        x_admin_token: Optional[str] = Header(None),
    ):
        """Revoke active admin session token"""
        token = x_admin_token
        if not token and authorization and authorization.startswith("Bearer "):
            token = authorization.split("Bearer ", 1)[1].strip()
        elif not token and "admin_token" in request.cookies:
            token = request.cookies.get("admin_token")

        auth_service.logout(token)
        return {"success": True, "message": "Сессия успешно завершена"}

    # ==========================================
    # 2.1 SUPERADMIN USER MANAGEMENT (USERS / ORGANIZERS)
    # ==========================================
    @api_router.get("/admin/users")
    async def get_admin_users(_: Dict[str, Any] = Depends(require_superadmin)):
        """List all admins with per-organizer revenue, ticket sales, and games counts (SuperAdmin only)"""
        admins = await db.get_all_admins()
        return {"success": True, "admins": admins}

    @api_router.post("/admin/users")
    async def create_admin_user(
        req: CreateAdminUserRequest,
        _: Dict[str, Any] = Depends(require_superadmin),
    ):
        """Create a new organizer profile with login, password, and SBP credentials (SuperAdmin only)"""
        try:
            admin = await db.create_admin(
                username=req.username,
                password=req.password,
                display_name=req.display_name,
                role=req.role or "admin",
                sbp_phone=req.sbp_phone or "",
                sbp_bank=req.sbp_bank or "СБП",
            )
            return {"success": True, "admin": admin, "message": f"Организатор {req.username} успешно создан"}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @api_router.delete("/admin/users/{admin_id}")
    async def delete_admin_user(
        admin_id: str,
        current_super: Dict[str, Any] = Depends(require_superadmin),
    ):
        """Permanently delete an organizer and reassign their games to SuperAdmin (SuperAdmin only)"""
        if admin_id == current_super["id"]:
            raise HTTPException(status_code=400, detail="Нельзя удалить собственный профиль Главного СуперАдминистратора")

        try:
            ok = await db.delete_admin(admin_id)
            if not ok:
                raise HTTPException(status_code=404, detail="Администратор не найден")
            return {"success": True, "message": "Профиль администратора успешно удален"}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # ==========================================
    # 3. PROTECTED ADMIN DASHBOARD ENDPOINTS
    # ==========================================
    @api_router.get("/admin/stats")
    async def get_admin_dashboard_stats(current_admin: Dict[str, Any] = Depends(require_admin)):
        """Fetch platform or organizer KPI metrics (revenue, tickets, raffles)"""
        admin_id = None if current_admin.get("role") == "superadmin" else current_admin.get("id")
        stats = await db.get_admin_stats(admin_id=admin_id)
        return {"success": True, "stats": stats, "current_admin": current_admin}

    @api_router.get("/admin/raffles")
    async def get_all_admin_raffles(current_admin: Dict[str, Any] = Depends(require_admin)):
        """Get list of raffles (all for SuperAdmin, only own for regular Admin)"""
        creator_admin_id = None if current_admin.get("role") == "superadmin" else current_admin.get("id")
        raffles = await db.get_all_raffles(creator_admin_id=creator_admin_id)
        return {"success": True, "raffles": raffles, "current_admin": current_admin}

    @api_router.post("/admin/upload-image")
    async def upload_prize_image(
        request: Request,
        _: Dict[str, Any] = Depends(require_admin),
    ):
        """
        Upload prize photo from local computer to server.
        Supports both multipart/form-data and Base64 JSON.
        Saves into data/uploads/ and returns public URL (/static/uploads/...).
        """
        uploads_dir = Path("data") / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)

        file_bytes = b""
        original_name = "lot_photo.jpg"
        content_type = request.headers.get("content-type", "")

        if "multipart/form-data" in content_type:
            form = await request.form()
            upload_file = form.get("file")
            if upload_file and hasattr(upload_file, "read"):
                file_bytes = await upload_file.read()
                original_name = getattr(upload_file, "filename", "lot_photo.jpg") or "lot_photo.jpg"
        else:
            try:
                body = await request.json()
            except Exception:
                body = {}
            raw_b64 = body.get("image_data", "")
            original_name = body.get("filename", "lot_photo.jpg") or "lot_photo.jpg"
            if raw_b64:
                if "," in raw_b64:
                    raw_b64 = raw_b64.split(",", 1)[1]
                try:
                    file_bytes = base64.b64decode(raw_b64)
                except Exception:
                    raise HTTPException(status_code=400, detail="Неверный формат изображения (Base64)")

        if not file_bytes:
            raise HTTPException(status_code=400, detail="Файл изображения не передан или пустой")

        # Determine extension
        ext = Path(original_name).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".jfif"]:
            ext = ".jpg"

        safe_filename = f"lot_{secrets.token_hex(6)}_{int(time.time())}{ext}"
        target_path = uploads_dir / safe_filename
        with open(target_path, "wb") as f:
            f.write(file_bytes)

        public_url = f"/static/uploads/{safe_filename}"
        logger.info(f"Admin uploaded prize photo: {safe_filename} ({len(file_bytes)} bytes)")
        return {"success": True, "url": public_url, "filename": safe_filename}

    @api_router.post("/admin/raffles")
    async def create_new_raffle(
        req: CreateRaffleRequest,
        current_admin: Dict[str, Any] = Depends(require_admin),
    ):
        """
        Create a new prize lottery (game) and associate it with the creating admin.
        Generates ticket inventory and launches into the live pool.
        """
        raffle_id = req.id
        if not raffle_id:
            slug = re.sub(r"[^a-zA-Z0-9]", "_", req.title.lower()).strip("_")[:16]
            if not slug:
                slug = "lot"
            raffle_id = f"raffle_{slug}_{secrets.token_hex(3)}"

        # Check for duplicate
        existing = await db.get_raffle(raffle_id)
        if existing:
            raffle_id = f"{raffle_id}_{secrets.token_hex(2)}"

        # Normalize prize images and list
        prizes_data = [p.dict() for p in req.prizes] if req.prizes else None
        main_img = req.prize_image_url.strip() if req.prize_image_url else ""
        if not main_img and prizes_data and len(prizes_data) > 0:
            main_img = prizes_data[0].get("prize_image_url", "")

        created = await db.create_raffle(
            raffle_id=raffle_id,
            title=req.title.strip(),
            description=req.description.strip() if req.description else "",
            prize_image_url=main_img,
            total_tickets=req.total_tickets,
            price_per_ticket=req.price_per_ticket,
            lot_number=req.lot_number,
            category=req.category or "lot",
            prizes=prizes_data,
            creator_admin_id=current_admin["id"],
        )

        logger.info(
            f"Admin {current_admin['username']} created new game: {raffle_id} ({req.title}) "
            f"with {len(created.get('prizes', []))} prizes"
        )
        return {"success": True, "raffle": created}

    @api_router.get("/admin/raffles/{raffle_id}/tickets")
    async def get_admin_raffle_tickets(
        raffle_id: str,
        current_admin: Dict[str, Any] = Depends(require_admin),
    ):
        """Inspect all tickets for a specific raffle with buyer details and timestamps"""
        raffle = await db.get_raffle(raffle_id)
        if not raffle:
            raise HTTPException(status_code=404, detail="Розыгрыш не найден")

        # Permission check
        if current_admin.get("role") != "superadmin" and raffle.get("creator_admin_id") != current_admin["id"]:
            raise HTTPException(status_code=403, detail="Вы можете просматривать только свои розыгрыши")

        tickets = await db.get_raffle_tickets(raffle_id)
        return {"success": True, "raffle": raffle, "tickets": tickets}

    @api_router.post("/admin/raffles/{raffle_id}/draw")
    async def draw_raffle_winner_admin(
        raffle_id: str,
        current_admin: Dict[str, Any] = Depends(require_admin),
    ):
        """
        Execute provably fair winner selection for all prize places (Лоты) in the game.
        Announces the winners in all connected MAX Messenger groups and sends push alerts!
        """
        raffle = await db.get_raffle(raffle_id)
        if not raffle:
            raise HTTPException(status_code=404, detail="Розыгрыш не найден")

        # Permission check
        if current_admin.get("role") != "superadmin" and raffle.get("creator_admin_id") != current_admin["id"]:
            raise HTTPException(status_code=403, detail="Вы можете проводить розыгрыш только своей игры")

        result = await lottery_service.draw_raffle_winner(raffle_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "Ошибка проведения розыгрыша"))

        winners_count = len(result.get("winners", []))
        logger.info(
            f"Winners drawn for raffle {raffle_id} by {current_admin['username']}: "
            f"{winners_count} prize places awarded"
        )
        return result

    @api_router.post("/admin/raffles/{raffle_id}/broadcast")
    async def broadcast_single_raffle(
        raffle_id: str,
        current_admin: Dict[str, Any] = Depends(require_admin),
    ):
        """Publish and pin a specific raffle showcase in all connected MAX Messenger groups"""
        raffle = await db.get_raffle(raffle_id)
        if not raffle:
            raise HTTPException(status_code=404, detail="Розыгрыш не найден")

        if current_admin.get("role") != "superadmin" and raffle.get("creator_admin_id") != current_admin["id"]:
            raise HTTPException(status_code=403, detail="Вы можете публиковать только свои розыгрыши")

        bot_username = "se14443050_bot"
        bot_id = 471249415
        if notification_service.bot and notification_service.bot.me:
            bot_username = notification_service.bot.me.username or bot_username
            bot_id = notification_service.bot.me.user_id or bot_id

        medal_map = {1: "🥇", 2: "🥈", 3: "🥉"}
        prizes = raffle.get("prizes", [])
        if prizes:
            prizes_text_lines = ["🏆 **Призовые места (Лоты):**"]
            for p in prizes:
                pl = p.get("place", 1)
                lt = p.get("lot_number", pl)
                t = p.get("title", "")
                m = medal_map.get(pl, f"🏅 {pl} место")
                prizes_text_lines.append(f"{m} **{pl} место — Лот №{lt}**: {t}")
            prizes_block = "\n".join(prizes_text_lines) + "\n\n"
        else:
            prizes_block = ""

        creator_line = ""
        if raffle.get("creator_name"):
            creator_line = f"👤 Организатор: **{raffle['creator_name']}**\n"

        text = (
            f"🎁 **Внимание! Новый розыгрыш в BotMAX!**\n\n"
            f"🎮 **{raffle['title']}**\n\n"
            f"{creator_line}"
            f"{raffle.get('description', '')}\n\n"
            f"{prizes_block}"
            f"💰 Стоимость 1 билета: **{raffle['price_per_ticket']:.0f} ₽**\n"
            f"🎫 Всего билетов: **{raffle['total_tickets']} шт.**\n"
            f"🟢 Доступно сейчас: **{raffle['available_tickets']} шт.**\n\n"
            f"Мгновенная оплата по СБП в любом банке РФ. Билеты выбывают сразу!\n"
            f"👇 **Нажмите кнопку ниже, чтобы открыть табло и занять номера:**"
        )
        kb = group_showcase_keyboard(config.mini_app_url, bot_username, bot_id)

        sent_count = await notification_service.broadcast_raffle_announcement(
            raffle=raffle, keyboard=kb, pin=True
        )
        return {"success": True, "broadcasted_groups_count": sent_count}

    @api_router.post("/admin/orders/{order_id}/release")
    async def admin_release_reservation(
        order_id: str,
        current_admin: Dict[str, Any] = Depends(require_admin),
    ):
        """Admin force-release of reserved tickets back to the available pool"""
        result = await lottery_service.cancel_reservation(order_id, is_admin=True)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result.get("error", "Не удалось снять бронь"))
        return result

    @api_router.get("/admin/raffles/{raffle_id}/pending-reservations")
    async def get_admin_pending_reservations(
        raffle_id: str,
        current_admin: Dict[str, Any] = Depends(require_admin),
    ):
        """Get all active reserved tickets and orders for this raffle"""
        orders = await db.get_raffle_pending_orders(raffle_id)
        return {"success": True, "pending_orders": orders}

    @api_router.post("/admin/broadcast-showcase")
    async def broadcast_full_showcase(_: Dict[str, Any] = Depends(require_admin)):
        """Publish and pin active lotteries showcase card in all connected MAX groups"""
        raffles = await lottery_service.get_active_raffles()
        if not raffles:
            raise HTTPException(status_code=400, detail="Нет активных розыгрышей для публикации")

        bot_username = "se14443050_bot"
        bot_id = 471249415
        if notification_service.bot and notification_service.bot.me:
            bot_username = notification_service.bot.me.username or bot_username
            bot_id = notification_service.bot.me.user_id or bot_id

        lines = [
            "🎰 **Официальные розыгрыши призов BotMAX**\n",
            "Участвуйте в розыгрышах ценных гаджетов и сертификатов с моментальной оплатой через **СБП (Систему быстрых платежей)**!\n",
            "Каждый купленный билет мгновенно выбывает из продажи в реальном времени.\n",
            "🔥 **Активные призы:**\n",
        ]
        for r in raffles[:4]:
            creator_suffix = f" (Организатор: {r.get('creator_name', 'Администратор')})" if r.get('creator_name') else ""
            lines.append(
                f"• **{r['title']}**{creator_suffix}\n"
                f"  💰 Билет: **{r['price_per_ticket']:.0f} ₽** | Свободно: **{r['available_tickets']}/{r['total_tickets']}**\n"
            )
        lines.append("👇 **Нажмите кнопку ниже, чтобы открыть табло и выбрать билеты:**")

        kb = group_showcase_keyboard(config.mini_app_url, bot_username, bot_id)
        sent_count = await notification_service.broadcast_to_all_groups(
            text="\n".join(lines), attachments=[kb], pin=True
        )
        return {"success": True, "broadcasted_groups_count": sent_count}

    @api_router.delete("/admin/raffles/{raffle_id}")
    async def delete_raffle_admin(
        raffle_id: str,
        current_admin: Dict[str, Any] = Depends(require_admin),
    ):
        """Permanently delete a raffle from the database (own raffle or SuperAdmin)"""
        raffle = await db.get_raffle(raffle_id)
        if not raffle:
            raise HTTPException(status_code=404, detail="Розыгрыш не найден")

        if current_admin.get("role") != "superadmin" and raffle.get("creator_admin_id") != current_admin["id"]:
            raise HTTPException(status_code=403, detail="Вы можете удалять только свои розыгрыши")

        await db.delete_raffle(raffle_id)
        logger.info(f"Admin {current_admin['username']} deleted raffle {raffle_id}")
        return {"success": True, "message": f"Розыгрыш {raffle_id} удален"}

    @api_router.patch("/admin/raffles/{raffle_id}/status")
    async def update_raffle_status_admin(
        raffle_id: str,
        req: UpdateRaffleStatusRequest,
        current_admin: Dict[str, Any] = Depends(require_admin),
    ):
        """Update raffle status (e.g. active, completed, cancelled)"""
        raffle = await db.get_raffle(raffle_id)
        if not raffle:
            raise HTTPException(status_code=404, detail="Розыгрыш не найден")

        if current_admin.get("role") != "superadmin" and raffle.get("creator_admin_id") != current_admin["id"]:
            raise HTTPException(status_code=403, detail="Вы можете изменять статус только своих розыгрышей")

        valid_statuses = ("active", "completed", "cancelled")
        if req.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Недопустимый статус. Допустимые значения: {valid_statuses}",
            )

        updated = await db.update_raffle_status(raffle_id, req.status)
        return {"success": True, "status": req.status}

    return api_router
