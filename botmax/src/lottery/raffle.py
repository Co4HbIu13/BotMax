"""Lottery raffle management"""

import random
import logging
from typing import Optional, List
from datetime import datetime, timedelta

from ..storage.database import Database
from ..logger import get_logger

logger = get_logger(__name__)


class RaffleManager:
    """Manages lottery raffles and winner selection"""

    def __init__(self, db: Database, logger: logging.Logger):
        self.db = db
        self.logger = logger

    async def create_raffle(
        self,
        chat_id: int,
        title: str,
        total_tickets: int,
        price_per_ticket: float,
        created_by: int,
        description: str = "",
        duration_hours: int = 24,
    ) -> str:
        """Create a new raffle"""
        # Generate unique raffle ID
        raffle_id = f"raffle_{chat_id}_{int(datetime.now().timestamp())}"

        # Create raffle in database
        await self.db.create_raffle(
            raffle_id=raffle_id,
            title=title,
            description=description,
            total_tickets=total_tickets,
            price_per_ticket=price_per_ticket,
        )

        # Create individual tickets
        for ticket_num in range(1, total_tickets + 1):
            # Initially, tickets are unassigned (will be assigned when sold)
            await self.db.create_ticket(
                raffle_id=raffle_id,
                user_id=0,  # 0 means unassigned/available
                username="",
                ticket_number=ticket_num,
                price=price_per_ticket,
            )

        self.logger.info(
            f"Created raffle {raffle_id} in chat {chat_id}: "
            f"{title} ({total_tickets} tickets @ {price_per_ticket} each)"
        )

        return raffle_id

    async def finish_raffle(
        self, raffle_id: str, chat_id: int, bot: Any
    ) -> None:
        """Finish raffle and select random winner"""
        # Get raffle info
        raffle = await self.db.get_raffle(raffle_id)
        if not raffle:
            self.logger.error(f"Raffle {raffle_id} not found")
            return

        if raffle["status"] != "active":
            self.logger.warning(f"Raffle {raffle_id} is not active (status: {raffle['status']})")
            return

        # Get participants
        participants = await self.db.get_participants(raffle_id)
        if not participants:
            self.logger.warning(f"No participants in raffle {raffle_id}")
            await bot.send_message(
                chat_id=chat_id,
                text=f"🎟️ Розыгрыш '{raffle['title']}' завершен, но участников не было.",
            )
            await self.db.update_raffle_status(raffle_id, "completed")
            return

        # Select random winner weighted by ticket count
        winner = self._select_weighted_winner(participants)
        if not winner:
            self.logger.error(f"Could not select winner for raffle {raffle_id}")
            return

        winner_user_id = winner["user_id"]
        winner_username = winner["username"] or f"user_{winner_user_id}"

        # Update raffle with winner
        await self.db.update_raffle_status(
            raffle_id, "completed", winner_user_id
        )

        # Notify chat
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"🎉 Розыгрыш завершен!\n\n"
                f"📝 Название: {raffle['title']}\n"
                f"🎫 Всего билетов: {raffle['total_tickets']}\n"
                f"💰 Цена за билет: {raffle['price_per_ticket']}\n"
                f"👥 Участников: {len(participants)}\n"
                f"🏆 Победитель: @{winner_username} (ID: {winner_user_id})\n"
                f"🎫 Билетов победителя: {winner['ticket_count']}\n\n"
                f"Спасибо всем за участие!"
            ),
        )

        self.logger.info(
            f"Finished raffle {raffle_id}: winner @{winner_username} "
            f"({winner_user_id}) with {winner['ticket_count']} tickets"
        )

    def _select_weighted_winner(
        self, participants: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Select winner weighted by ticket count"""
        if not participants:
            return None

        # Create weighted list
        weighted_participants = []
        for participant in participants:
            # Add participant multiple times based on ticket count
            for _ in range(participant["ticket_count"]):
                weighted_participants.append(participant)

        if not weighted_participants:
            return None

        # Select random winner
        winner = random.choice(weighted_participants)
        return winner

    async def get_raffle_stats(self, raffle_id: str) -> Dict[str, Any]:
        """Get statistics for a raffle"""
        raffle = await self.db.get_raffle(raffle_id)
        if not raffle:
            return {}

        participants = await self.db.get_participants(raffle_id)
        available_tickets = await self.db.get_available_tickets(raffle_id)
        sold_tickets = raffle["total_tickets"] - len(available_tickets)

        return {
            "raffle_id": raffle_id,
            "title": raffle["title"],
            "status": raffle["status"],
            "total_tickets": raffle["total_tickets"],
            "sold_tickets": sold_tickets,
            "available_tickets": len(available_tickets),
            "participant_count": len(participants),
            "total_revenue": sold_tickets * raffle["price_per_ticket"],
            "winner_id": raffle.get("winner_user_id"),
        }