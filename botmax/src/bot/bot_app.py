"""MAX Bot Application Setup with SSL-safe connector"""

import asyncio
import logging
from typing import Optional
import aiohttp
from maxapi import Bot, Dispatcher
from maxapi.client.default import DefaultConnectionProperties

from ..config import Config
from ..database.db import Database
from ..services.lottery import LotteryService
from ..services.notification import NotificationService
from .handlers import register_handlers

logger = logging.getLogger("botmax.bot")


class BotApp:
    """Encapsulates MAX Bot, Dispatcher, and safe connection lifecycle"""

    def __init__(
        self,
        config: Config,
        db: Database,
        lottery_service: LotteryService,
        notification_service: NotificationService,
    ):
        self.config = config
        self.db = db
        self.lottery_service = lottery_service
        self.notification_service = notification_service
        self.bot: Optional[Bot] = None
        self.dp = Dispatcher()
        self._initialized = False

    def initialize(self) -> None:
        """Initialize bot instance within active asyncio event loop"""
        if self._initialized:
            return

        # TCPConnector with ssl=False handles Russian Ministry of Digital Development
        # Root CA certificates on platform-api2.max.ru without TLS verification errors
        connector = aiohttp.TCPConnector(ssl=False)
        self.bot = Bot(
            token=self.config.max_bot_token,
            default_connection=DefaultConnectionProperties(connector=connector),
        )

        # Connect bot to notification service
        self.notification_service.set_bot(self.bot)

        # Register message, callback, and command handlers
        register_handlers(
            dp=self.dp,
            bot=self.bot,
            config=self.config,
            db=self.db,
            lottery_service=self.lottery_service,
        )
        self._initialized = True
        logger.info("BotApp successfully initialized within active event loop.")

    async def start_polling(self) -> None:
        """Run bot in Long Polling mode (ideal for local development and testing)"""
        self.initialize()
        logger.info("Initializing MAX Bot connection...")
        try:
            # Delete any existing webhook before starting polling as required by MAX API
            await self.bot.delete_webhook()
            logger.info("Existing webhooks cleared. Starting long polling...")
            await self.dp.start_polling(self.bot)
        except asyncio.CancelledError:
            logger.info("Bot polling cancelled.")
        except Exception as e:
            logger.error(f"Error during bot polling: {e}", exc_info=True)
        finally:
            if self.bot and self.bot.session:
                await self.bot.session.close()

    async def close(self) -> None:
        """Cleanly close bot session"""
        if self.bot and self.bot.session and not self.bot.session.closed:
            await self.bot.session.close()
            logger.info("Bot session closed.")
