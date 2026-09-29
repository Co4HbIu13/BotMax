"""Main entry point for BotMAX"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from src.config import Config
from src.logger import setup_logger
from src.bot.client import MAXBotClient
from src.storage.database import Database


async def main() -> None:
    """Main application entry point"""
    # Setup logging
    logger = setup_logger(
        name="botmax",
        log_level="info",
        log_file="./logs/botmax.log",
    )

    logger.info("Starting BotMAX...")

    try:
        # Load configuration
        config = Config.from_env()
        config.ensure_directories()

        # Initialize database
        db = Database(config.database_path)
        await db.initialize()

        # Initialize bot client
        bot_client = MAXBotClient(config, db)

        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            asyncio.create_task(shutdown(bot_client, db))

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start bot
        logger.info("BotMAX initialized successfully")
        logger.info("Starting bot in polling mode (for testing)")
        logger.info("For production, use webhook mode with HTTPS on port 443")

        await bot_client.start_polling()

    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)


async def shutdown(bot_client: MAXBotClient, db: Database) -> None:
    """Graceful shutdown"""
    logger = logging.getLogger("botmax")
    logger.info("Shutting down BotMAX...")

    try:
        await db.close()
        logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}")

    logger.info("BotMAX stopped")


if __name__ == "__main__":
    # Ensure we're running from the project root
    if not Path("botmax").exists():
        print("Error: Please run from project root directory")
        sys.exit(1)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBotMAX stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)