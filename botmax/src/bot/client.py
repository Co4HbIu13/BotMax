"""MAX Bot API client wrapper"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from maxapi import Bot, Dispatcher
from maxapi.types import (
    MessageCreated,
    CallbackButton,
    BotStarted,
    BotAdded,
    BotRemoved,
    MessageCallback,
)

from ..config import Config
from ..logger import get_logger
from ..storage.database import Database
from ..lottery.raffle import RaffleManager
from ..payment.miniapp import PaymentProcessor

logger = get_logger(__name__)


class MAXBotClient:
    """Wrapper for MAX Bot API with business logic"""

    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self.logger = get_logger("bot.client")

        # Initialize MAX API bot and dispatcher
        self.bot = Bot(config.max_bot_token)
        self.dp = Dispatcher()

        # Initialize managers
        self.raffle_manager = RaffleManager(self.db, self.logger)
        self.payment_processor = PaymentProcessor(
            self.db, self.bot, self.config, self.logger
        )

        # Register handlers
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register all event handlers"""

        @self.dp.bot_started()
        async def on_bot_started(event: BotStarted):
            await self._on_bot_started(event)

        @self.dp.message_created()
        async def on_message_created(event: MessageCreated):
            await self._on_message_created(event)

        @self.dp.message_callback()
        async def on_message_callback(event: MessageCallback):
            await self._on_message_callback(event)

        @self.dp.bot_added()
        async def on_bot_added(event: BotAdded):
            await self._on_bot_added(event)

        @self.dp.bot_removed()
        async def on_bot_removed(event: BotRemoved):
            await self._on_bot_removed(event)

    async def _on_bot_started(self, event: BotStarted) -> None:
        """Handle bot started event"""
        self.logger.info(f"Bot started in chat {event.chat_id}")
        await self.bot.send_message(
            chat_id=event.chat_id,
            text="🤖 Бот запущен! Используйте /help для списка команд",
        )

    async def _on_message_created(self, event: MessageCreated) -> None:
        """Handle incoming messages"""
        message = event.message
        if not message.text:
            return

        text = message.text.strip()
        user_id = message.from_user.id
        username = message.from_user.username or f"user_{user_id}"
        chat_id = message.chat.id

        self.logger.info(
            f"Received message from {username} ({user_id}) in chat {chat_id}: {text}"
        )

        # Handle commands
        if text.startswith("/"):
            await self._handle_command(message, text, user_id, username, chat_id)
        else:
            # Handle regular messages (e.g., for raffle participation)
            await self._handle_regular_message(
                message, text, user_id, username, chat_id
            )

    async def _on_message_callback(self, event: MessageCallback) -> None:
        """Handle callback queries from inline keyboards"""
        callback = event.callback
        user_id = callback.from_user.id
        username = callback.from_user.username or f"user_{user_id}"
        chat_id = callback.message.chat.id if callback.message else None
        data = callback.payload

        self.logger.info(
            f"Received callback from {username} ({user_id}): {data}"
        )

        await self._handle_callback(callback, user_id, username, chat_id, data)

    async def _on_bot_added(self, event: BotAdded) -> None:
        """Handle bot added to chat"""
        self.logger.info(
            f"Bot added to chat {event.chat.id}: {event.chat.title}"
        )
        # No action needed for now

    async def _on_bot_removed(self, event: BotRemoved) -> None:
        """Handle bot removed from chat"""
        self.logger.info(
            f"Bot removed from chat {event.chat.id}"
        )
        await self.db.close()

    async def _handle_command(
        self,
        message: Any,
        text: str,
        user_id: int,
        username: str,
        chat_id: int,
    ) -> None:
        """Handle bot commands"""
        parts = text.split()
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        if command == "/start":
            await self.cmd_start(message, user_id, username, chat_id)
        elif command == "/help":
            await self.cmd_help(message, user_id, username, chat_id)
        elif command == "/lottery":
            await self.cmd_lottery(message, user_id, username, chat_id, args)
        elif command == "/raffle":
            await self.cmd_raffle(message, user_id, username, chat_id, args)
        elif command == "/balance":
            await self.cmd_balance(message, user_id, username, chat_id)
        else:
            await message.answer(
                f"❓ Неизвестная команда: {command}\n"
                "Используйте /help для списка доступных команд"
            )

    async def cmd_start(
        self, message: Any, user_id: int, username: str, chat_id: int
    ) -> None:
        """Handle /start command"""
        await message.answer(
            f"👋 Привет, {username}! Я бот для проведения розыгрышей в группе.\n\n"
            "🎯 Доступные команды:\n"
            "/help - показать эту справку\n"
            "/lottery - управлять розыгрышами\n"
            "/balance - проверить ваш баланс\n\n"
            "Для создания розыгрыша используйте:\n"
            "/lottery create <название> <билетов> <цена>\n"
            "Пример: /lottery create 'Новый год' 100 50"
        )

    async def cmd_help(
        self, message: Any, user_id: int, username: str, chat_id: int
    ) -> None:
        """Handle /help command"""
        await self.cmd_start(message, user_id, username, chat_id)

    async def cmd_lottery(
        self,
        message: Any,
        user_id: int,
        username: str,
        chat_id: int,
        args: List[str],
    ) -> None:
        """Handle lottery commands"""
        if not args:
            await message.answer(
                "🎲 Управление розыгрышами:\n"
                "/lottery create <название> <билетов> <цена> - создать розыгрыш\n"
                "/lottery list - показать активные розыгрыши\n"
                "/lottery info <id> - информация о розыгрыше\n"
                "/lottery finish <id> - завершить розыгрыш и выбрать победителя\n"
                "/lottery cancel <id> - отменить розыгрыш"
            )
            return

        subcommand = args[0].lower()

        if subcommand == "create":
            if len(args) < 4:
                await message.answer(
                    "❌ Недостаточно аргументов. Использование:\n"
                    "/lottery create <название> <количество_билетов> <цена_за_билет>\n"
                    "Пример: /lottery create 'Новый год' 100 50"
                )
                return

            try:
                title = args[1]
                total_tickets = int(args[2])
                price_per_ticket = float(args[3])

                if total_tickets <= 0 or price_per_ticket <= 0:
                    raise ValueError("Values must be positive")

                await self.raffle_manager.create_raffle(
                    chat_id=chat_id,
                    title=title,
                    total_tickets=total_tickets,
                    price_per_ticket=price_per_ticket,
                    created_by=user_id,
                )

                await message.answer(
                    f"🎉 Розыгрыш создан!\n"
                    f"📝 Название: {title}\n"
                    f"🎫 Билетов: {total_tickets}\n"
                    f"💰 Цена за билет: {price_per_ticket}\n"
                    f"🆔 ID розыгрыша: будет присвоен после создания\n\n"
                    f"Билеты можно приобрести через кнопку ниже:"
                )

                # Send message with inline keyboard for ticket purchase
                await self._send_ticket_purchase_message(chat_id, title)

            except ValueError as e:
                await message.answer(f"❌ Ошибка в аргументах: {e}")

        elif subcommand == "list":
            await self._list_active_raffles(message, chat_id)

        elif subcommand == "info":
            if len(args) < 2:
                await message.answer("❌ Укажите ID розыгрыша: /lottery info <id>")
                return
            raffle_id = args[1]
            await self._show_raffle_info(message, raffle_id)

        elif subcommand == "finish":
            if len(args) < 2:
                await message.answer("❌ Укажите ID розыгрыша: /lottery finish <id>")
                return
            raffle_id = args[1]
            await self._finish_raffle(message, raffle_id, chat_id)

        elif subcommand == "cancel":
            if len(args) < 2:
                await message.answer("❌ Укажите ID розыгрыша: /lottery cancel <id>")
                return
            raffle_id = args[1]
            await self._cancel_raffle(message, raffle_id)

        else:
            await message.answer(f"❓ Неизвестная подкоманда: {subcommand}")

    async def cmd_balance(
        self, message: Any, user_id: int, username: str, chat_id: int
    ) -> None:
        """Handle /balance command"""
        # TODO: Implement user balance checking
        await message.answer(
            f"💰 Ваш баланс: 0.00\n"
            "Функция баланса пока в разработке"
        )

    async def _handle_regular_message(
        self,
        message: Any,
        text: str,
        user_id: int,
        username: str,
        chat_id: int,
    ) -> None:
        """Handle non-command messages"""
        # Check if message is a response to raffle participation
        # This would typically be handled via callback queries, but we can
        # also handle text responses like "купить 2 билета"
        pass

    async def _handle_callback(
        self,
        callback: Any,
        user_id: int,
        username: str,
        chat_id: Optional[int],
        data: str,
    ) -> None:
        """Handle callback queries from inline keyboards"""
        if not chat_id:
            await callback.answer("❌ Ошибка: чат не определен", show_alert=True)
            return

        if data.startswith("buy_tickets:"):
            try:
                _, raffle_id_str, ticket_count_str = data.split(":")
                raffle_id = int(raffle_id_str)
                ticket_count = int(ticket_count_str)

                await self._process_ticket_purchase(
                    callback, user_id, username, raffle_id, ticket_count
                )
            except ValueError:
                await callback.answer("❌ Неверные данные", show_alert=True)
        elif data.startswith("view_raffle:"):
            raffle_id = data.split(":")[1]
            await self._show_raffle_info_callback(callback, raffle_id)
        else:
            await callback.answer("❓ Неизвестное действие", show_alert=True)

    async def _send_ticket_purchase_message(
        self, chat_id: int, raffle_title: str
    ) -> None:
        """Send message with inline keyboard for ticket purchase"""
        from maxapi.types import InlineKeyboardButton, InlineKeyboardMarkup

        # Create buttons for different ticket quantities
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🎫 1 билет", callback_data=f"buy_tickets:{raffle_id}:1"
                    ),
                    InlineKeyboardButton(
                        text="🎫🎫 2 билета", callback_data=f"buy_tickets:{raffle_id}:2"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🎫🎫🎫 3 билета", callback_data=f"buy_tickets:{raffle_id}:3"
                    ),
                    InlineKeyboardButton(
                        text="🎫×5 5 билетов", callback_data=f"buy_tickets:{raffle_id}:5"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🎫×10 10 билетов", callback_data=f"buy_tickets:{raffle_id}:10"
                    ),
                ],
            ]
        )

        await self.bot.send_message(
            chat_id=chat_id,
            text=f"🎟️ Выберите количество билетов для розыгрыша '{raffle_title}':",
            reply_markup=keyboard,
        )

    async def _process_ticket_purchase(
        self,
        callback: Any,
        user_id: int,
        username: str,
        raffle_id: int,
        ticket_count: int,
    ) -> None:
        """Process ticket purchase request"""
        await callback.answer("🔄 Обрабатываем покупку...")

        try:
            # Get raffle info
            raffle = await self.db.get_raffle(str(raffle_id))
            if not raffle:
                await callback.answer("❌ Розыгрыш не найден", show_alert=True)
                return

            if raffle["status"] != "active":
                await callback.answer(
                    "❌ Розыгрыш уже завершен или отменен", show_alert=True
                )
                return

            # Calculate total amount
            total_amount = raffle["price_per_ticket"] * ticket_count

            # Create payment record
            payment_id = await self.db.create_payment(
                raffle_id=str(raffle_id),
                user_id=user_id,
                ticket_count=ticket_count,
                amount=total_amount,
                metadata={
                    "username": username,
                    "initiated_by": "callback",
                },
            )

            # TODO: Integrate with actual payment system (SBP mini-app)
            # For now, simulate successful payment
            await self._simulate_successful_payment(
                callback, user_id, username, raffle_id, ticket_count, payment_id
            )

        except Exception as e:
            self.logger.error(f"Error processing ticket purchase: {e}")
            await callback.answer("❌ Ошибка при обработке покупки", show_alert=True)

    async def _simulate_successful_payment(
        self,
        callback: Any,
        user_id: int,
        username: str,
        raffle_id: int,
        ticket_count: int,
        payment_id: int,
    ) -> None:
        """Simulate successful payment for testing"""
        try:
            # Update payment status to completed
            await self.db.update_payment_status(
                payment_id, "completed", {"simulated": True}
            )

            # Sell tickets
            tickets_sold = 0
            for _ in range(ticket_count):
                # Get available ticket
                available_tickets = await self.db.get_available_tickets(
                    str(raffle_id)
                )
                if not available_tickets:
                    break

                ticket = available_tickets[0]
                success = await self.db.sell_ticket(ticket["id"], user_id)
                if success:
                    tickets_sold += 1

            # Add participant
            await self.db.add_participant(
                raffle_id=str(raffle_id),
                user_id=user_id,
                username=username,
                ticket_count=tickets_sold,
            )

            # Update callback message
            await callback.message.edit_text(
                f"✅ Оплата успешна!\n"
                f"🎫 Куплено билетов: {tickets_sold}\n"
                f"💰 Сумма: {ticket_count * raffle['price_per_ticket']:.2f}\n"
                f"🆔 ID платежа: {payment_id}\n\n"
                f"Спасибо за участие в розыгрыше!"
            )

            await callback.answer("🎉 Билеты куплены!", show_alert=False)

        except Exception as e:
            self.logger.error(f"Error in simulated payment: {e}")
            await callback.answer("❌ Ошибка при обработке платежа", show_alert=True)

    async def _list_active_raffles(
        self, message: Any, chat_id: int
    ) -> None:
        """List active raffles in chat"""
        # TODO: Implement raffle listing
        await message.answer("📋 Активные розыгрыши: (функция в разработке)")

    async def _show_raffle_info(
        self, message: Any, raffle_id: str
    ) -> None:
        """Show raffle information"""
        raffle = await self.db.get_raffle(raffle_id)
        if not raffle:
            await message.answer("❌ Розыгрыш не найден")
            return

        participants = await self.db.get_participants(raffle_id)
        available_tickets = await self.db.get_available_tickets(raffle_id)

        info_text = (
            f"🎟️ Информация о розыгрыше\n\n"
            f"📝 Название: {raffle['title']}\n"
            f"📄 Описание: {raffle.get('description', 'Нет описания')}\n"
            f"🎫 Всего билетов: {raffle['total_tickets']}\n"
            f"💰 Цена за билет: {raffle['price_per_ticket']}\n"
            f"📊 Статус: {raffle['status']}\n"
            f"✅ Продано билетов: {raffle['total_tickets'] - len(available_tickets)}\n"
            f"👥 Участников: {len(participants)}\n"
        )

        if raffle["winner_user_id"]:
            info_text += f"🏆 Победитель: пользователь ID {raffle['winner_user_id']}\n"

        await message.answer(info_text)

    async def _show_raffle_info_callback(
        self, callback: Any, raffle_id: str
    ) -> None:
        """Show raffle info via callback"""
        await callback.answer()  # Acknowledge callback
        raffle = await self.db.get_raffle(raffle_id)
        if not raffle:
            await callback.message.answer("❌ Розыгрыш не найден")
            return

        await callback.message.answer(
            f"🎟️ {raffle['title']}\n"
            f"💰 Цена: {raffle['price_per_ticket']} за билет\n"
            f"🎫 Доступно: {len(await self.db.get_available_tickets(raffle_id))} билетов"
        )

    async def _finish_raffle(
        self, message: Any, raffle_id: str, chat_id: int
    ) -> None:
        """Finish raffle and select winner"""
        await self.raffle_manager.finish_raffle(raffle_id, chat_id, self.bot)

    async def _cancel_raffle(
        self, message: Any, raffle_id: str
    ) -> None:
        """Cancel raffle"""
        await self.db.update_raffle_status(raffle_id, "cancelled")
        await message.answer("❌ Розыгрыш отменен")

    async def start_polling(self) -> None:
        """Start bot in polling mode"""
        self.logger.info("Starting bot in polling mode...")
        await self.dp.start_polling(self.bot)

    async def start_webhook(
        self, host: str, port: int, log_level: str = "info"
    ) -> None:
        """Start bot in webhook mode"""
        self.logger.info(f"Starting bot in webhook mode on {host}:{port}")
        await self.dp.start_webhook(
            bot=self.bot,
            webhook_path="/webhook",
            on_startup=self._on_webhook_startup,
            on_shutdown=self._on_webhook_shutdown,
            host=host,
            port=port,
            log_level=log_level,
        )

    async def _on_webhook_startup(self) -> None:
        """Webhook startup handler"""
        self.logger.info("Webhook started")

    async def _on_webhook_shutdown(self) -> None:
        """Webhook shutdown handler"""
        self.logger.info("Webhook shutting down")
        await self.db.close()