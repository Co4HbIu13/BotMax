"""Configuration management for BotMAX"""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """BotMAX configuration"""

    # MAX Bot API
    max_bot_token: str
    max_api_base_url: str = "https://platform-api2.max.ru"

    # Webhook
    webhook_url: str = ""
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8080

    # Database
    database_path: str = "./data/botmax.db"

    # Logging
    log_level: str = "info"
    log_file: str = "./logs/botmax.log"

    # Mini App
    mini_app_url: str = ""
    sbp_merchant_id: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables"""
        config = cls(
            max_bot_token=os.environ.get("MAX_BOT_TOKEN", ""),
            max_api_base_url=os.environ.get(
                "MAX_API_BASE_URL", "https://platform-api2.max.ru"
            ),
            webhook_url=os.environ.get("WEBHOOK_URL", ""),
            webhook_host=os.environ.get("WEBHOOK_HOST", "0.0.0.0"),
            webhook_port=int(os.environ.get("WEBHOOK_PORT", "8080")),
            database_path=os.environ.get("DATABASE_PATH", "./data/botmax.db"),
            log_level=os.environ.get("LOG_LEVEL", "info"),
            log_file=os.environ.get("LOG_FILE", "./logs/botmax.log"),
            mini_app_url=os.environ.get("MINI_APP_URL", ""),
            sbp_merchant_id=os.environ.get("SBP_MERCHANT_ID", ""),
        )
        config.validate()
        return config

    def validate(self) -> None:
        """Validate required configuration"""
        if not self.max_bot_token:
            raise ValueError("MAX_BOT_TOKEN is required")
        if not self.webhook_url:
            raise ValueError("WEBHOOK_URL is required")

    def ensure_directories(self) -> None:
        """Ensure required directories exist"""
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)