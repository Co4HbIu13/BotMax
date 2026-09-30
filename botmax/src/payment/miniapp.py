"""Payment processing via SBP mini-app"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from maxapi.types import LinkButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from ..config import Config
from ..logger import get_logger
from ..storage.database import Database

logger = get_logger(__name__)


class PaymentProcessor:
    """Handles SBP payments via mini-app integration"""

    def __init__(
        self,
        db: Database,
        bot: Any,
        config: Config,
        logger: logging.Logger,
    ):
        self.db = db
        self.bot = bot
        self.config = config
        self.logger = logger

    async def create_payment_invoice(
        self,
        user_id: int,
        username: str,
        raffle_id: str,
        ticket_count: int,
        amount: float,
    ) -> str:
        """Create payment invoice and return mini-app URL"""
        # In a real implementation, this would integrate with SBP payment gateway
        # For now, we'll simulate by creating a payment record and returning
        # a placeholder URL that would open the mini-app

        # Create pending payment record
        payment_id = await self.db.create_payment(
            raffle_id=raffle_id,
            user_id=user_id,
            ticket_count=ticket_count,
            amount=amount,
            metadata={
                "username": username,
                "payment_method": "sbp",
                "created_via": "miniapp",
            },
        )

        # Generate mini-app URL (in reality, this would be your actual mini-app)
        mini_app_url = (
            f"{self.config.mini_app_url}/pay?"
            f"payment_id={payment_id}&"
            f"user_id={user_id}&"
            f"amount={amount}&"
            f"currency=RUB"
        )

        self.logger.info(
            f"Created payment invoice for user {user_id}: "
            f"payment_id={payment_id}, amount={amount}"
        )

        return mini_app_url

    async def create_payment_keyboard(
        self,
        raffle_id: str,
        ticket_count: int,
        amount: float,
    ) -> Any:
        """Create inline keyboard with payment button"""
        builder = InlineKeyboardBuilder()
        builder.row(
            LinkButton(
                text=f"💳 Оплатить {amount:.2f} Руб (SBP)",
                url=f"https://pay.example.com?raffle={raffle_id}&tickets={ticket_count}&amount={amount}",
            )
        )
        return builder.as_markup()

    async def handle_payment_callback(
        self, callback_data: str
    ) -> Optional[Dict[str, Any]]:
        """Handle payment callback from mini-app"""
        # In a real implementation, your mini-app would send back a callback
        # with payment status when the user completes payment

        # Expected format: "payment_status:{payment_id}:{status}"
        try:
            parts = callback_data.split(":")
            if len(parts) < 3 or parts[0] != "payment_status":
                return None

            payment_id = int(parts[1])
            status = parts[2]  # completed, failed, etc.

            # Update payment status in database
            await self.db.update_payment_status(payment_id, status)

            # Get payment details
            # Note: This would require adding a get_payment method to database
            # For now, we'll return basic info
            return {
                "payment_id": payment_id,
                "status": status,
                "processed_at": datetime.now().isoformat(),
            }

        except (ValueError, IndexError) as e:
            self.logger.error(f"Error parsing payment callback: {e}")
            return None

    async def process_successful_payment(
        self,
        payment_id: int,
        user_id: int,
        raffle_id: str,
        ticket_count: int,
    ) -> bool:
        """Process successful payment and issue tickets"""
        try:
            # Update payment status
            await self.db.update_payment_status(payment_id, "completed")

            # Get raffle info to verify
            raffle = await self.db.get_raffle(raffle_id)
            if not raffle or raffle["status"] != "active":
                self.logger.error(
                    f"Invalid raffle {raffle_id} for payment {payment_id}"
                )
                return False

            # Sell tickets
            tickets_issued = 0
            for _ in range(ticket_count):
                available_tickets = await self.db.get_available_tickets(raffle_id)
                if not available_tickets:
                    break

                ticket = available_tickets[0]
                success = await self.db.sell_ticket(ticket["id"], user_id)
                if success:
                    tickets_issued += 1

            if tickets_issued == 0:
                self.logger.error(f"No tickets issued for payment {payment_id}")
                await self.db.update_payment_status(payment_id, "failed")
                return False

            # Add/update participant
            await self.db.add_participant(
                raffle_id=raffle_id,
                user_id=user_id,
                username="",  # Would be filled from user info
                ticket_count=tickets_issued,
            )

            self.logger.info(
                f"Processed successful payment {payment_id}: "
                f"user {user_id} got {tickets_issued} tickets for raffle {raffle_id}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error processing successful payment {payment_id}: {e}")
            await self.db.update_payment_status(payment_id, "failed")
            return False

    async def handle_failed_payment(
        self, payment_id: int, reason: str = ""
    ) -> None:
        """Handle failed payment"""
        await self.db.update_payment_status(
            payment_id, "failed", {"reason": reason}
        )
        self.logger.warning(f"Payment {payment_id} failed: {reason}")

    def create_payment_message(
        self,
        raffle_title: str,
        ticket_count: int,
        amount: float,
    ) -> str:
        """Create message for payment request"""
        return (
            f"🎟️ Оплата участия в розыгрыше\n\n"
            f"📝 Розыгрыш: {raffle_title}\n"
            f"🎫 Билетов: {ticket_count}\n"
            f"💰 Сумма к оплате: {amount:.2f} Руб\n\n"
            f"Нажмите кнопку ниже для оплаты через СБП:"
        )