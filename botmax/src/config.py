"""Configuration management for BotMAX"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()


@dataclass
class Config:
    """BotMAX configuration"""

    # MAX Bot API
    max_bot_token: str = ""
    max_api_base_url: str = "https://platform-api2.max.ru"

    # Webhook & Server
    webhook_url: str = ""
    host: str = "0.0.0.0"
    port: int = 8000
    run_mode: str = "polling"  # 'polling' or 'webhook'

    # Database & Storage
    database_path: str = "./data/botmax.db"

    # Logging
    log_level: str = "info"
    log_file: str = "./logs/botmax.log"

    # Mini App & SBP
    mini_app_url: str = "http://localhost:8000"
    sbp_merchant_id: str = "test_merchant"
    sbp_secret_key: str = "test_secret_key"
    reservation_duration_minutes: int = 10

    # Admins & Dashboard Auth
    admin_ids: List[int] = field(default_factory=lambda: [471249415])
    admin_password: str = "maxadmin2026"
    admin_session_secret: str = "botmax_admin_secret_session_2026"

    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables"""
        token = os.environ.get(
            "MAX_BOT_TOKEN",
            "f9LHodD0cOKlYORWpPyGoAg9P6wH1JzZeVVPSHl9Jdp4Qd6DwP8vFxU5Kvn12g6D1_7fG0VQCzkl-PRPN_kG",
        )
        webhook_url = os.environ.get("WEBHOOK_URL", "")
        mini_app_url = os.environ.get(
            "MINI_APP_URL",
            webhook_url.replace("/webhook", "") if webhook_url else "http://localhost:8000",
        )

        admin_ids_raw = os.environ.get("ADMIN_IDS", "471249415")
        admin_ids = []
        for aid in admin_ids_raw.split(","):
            aid = aid.strip()
            if aid.isdigit():
                admin_ids.append(int(aid))

        return cls(
            max_bot_token=token,
            max_api_base_url=os.environ.get(
                "MAX_API_BASE_URL", "https://platform-api2.max.ru"
            ),
            webhook_url=webhook_url,
            host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "8000")),
            run_mode=os.environ.get("RUN_MODE", "polling"),
            database_path=os.environ.get("DATABASE_PATH", "./data/botmax.db"),
            log_level=os.environ.get("LOG_LEVEL", "info"),
            log_file=os.environ.get("LOG_FILE", "./logs/botmax.log"),
            mini_app_url=mini_app_url,
            sbp_merchant_id=os.environ.get("SBP_MERCHANT_ID", "test_merchant"),
            sbp_secret_key=os.environ.get("SBP_SECRET_KEY", "test_secret_key"),
            reservation_duration_minutes=int(
                os.environ.get("RESERVATION_DURATION_MINUTES", "10")
            ),
            admin_ids=admin_ids,
            admin_password=os.environ.get("ADMIN_PASSWORD", "maxadmin2026"),
            admin_session_secret=os.environ.get(
                "ADMIN_SESSION_SECRET", "botmax_admin_secret_session_2026"
            ),
        )

    def ensure_directories(self) -> None:
        """Ensure required directories exist"""
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)