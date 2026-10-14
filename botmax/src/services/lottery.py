"""Lottery Service: Orchestrates ticket inventory drawdown, orders, and fair draw"""

import asyncio
import logging
import secrets
import uuid
from typing import Dict, Any, List, Optional
from ..database.db import Database
from .sbp import SBPService
from .notification import NotificationService

logger = logging.getLogger("botmax.lottery")


class LotteryService:
    """Manages raffle lifecycle, live ticket reservation/drawdown, and RNG winner selection"""

    def __init__(
        self,
        db: Database,
        sbp_service: SBPService,
        notification_service: NotificationService,
        reservation_duration_minutes: int = 10,
    ):
        self.db = db
        self.sbp_service = sbp_service
        self.notification_service = notification_service
        self.reservation_duration_minutes = reservation_duration_minutes

    async def get_active_raffles(self) -> List[Dict[str, Any]]:
        """List active lotteries with current inventory numbers"""
        return await self.db.get_all_raffles()

    async def get_raffle_details(self, raffle_id: str) -> Optional[Dict[str, Any]]:
        """Get raffle info and the complete grid of ticket states"""
        raffle = await self.db.get_raffle(raffle_id)
        if not raffle:
            return None
        tickets = await self.db.get_raffle_tickets(raffle_id)
        raffle["tickets"] = tickets
        return raffle

    async def reserve_specific_tickets(
        self,
        raffle_id: str,
        user_id: int,
        username: str,
        ticket_numbers: List[int],
    ) -> Dict[str, Any]:
        """
        Reserve specific tickets by numbers.
        Creates order and generates SBP payment link and QR.
        """
        if not ticket_numbers:
            return {"success": False, "error": "Не выбрано ни одного билета"}

        raffle = await self.db.get_raffle(raffle_id)
        if not raffle:
            return {"success": False, "error": "Розыгрыш не найден"}

        if raffle["status"] != "active":
            return {"success": False, "error": "Этот розыгрыш уже завершен или недоступен"}

        order_id = f"ord_{uuid.uuid4().hex[:12].upper()}"
        total_amount = round(len(ticket_numbers) * raffle["price_per_ticket"], 2)

        # 1. Atomically reserve tickets in database
        reservation = await self.db.reserve_tickets(
            raffle_id=raffle_id,
            user_id=user_id,
            username=username,
            ticket_numbers=ticket_numbers,
            order_id=order_id,
            duration_minutes=self.reservation_duration_minutes,
        )
        if not reservation["success"]:
            return reservation

        # 2. Generate SBP payment details
        purpose = f"Оплата билетов #{','.join(map(str, ticket_numbers))} ({raffle['title'][:30]})"
        sbp_data = self.sbp_service.create_payment_payload(
            order_id=order_id,
            amount_rub=total_amount,
            purpose=purpose,
        )

        # 3. Create Order record routed to raffle creator
        creator_admin_id = raffle.get("creator_admin_id", "admin_super")
        order = await self.db.create_order(
            order_id=order_id,
            raffle_id=raffle_id,
            user_id=user_id,
            username=username,
            ticket_numbers=ticket_numbers,
            amount=total_amount,
            sbp_qrid=sbp_data["qrid"],
            sbp_pay_url=sbp_data["nspk_url"],
            duration_minutes=self.reservation_duration_minutes,
            recipient_admin_id=creator_admin_id,
        )

        return {
            "success": True,
            "order_id": order_id,
            "raffle_id": raffle_id,
            "raffle_title": raffle["title"],
            "ticket_numbers": ticket_numbers,
            "ticket_count": len(ticket_numbers),
            "amount": total_amount,
            "expires_at": order["expires_at"],
            "sbp": sbp_data,
            "recipient": {
                "admin_id": creator_admin_id,
                "display_name": raffle.get("creator_name", "Главный Администратор"),
                "sbp_phone": raffle.get("creator_sbp_phone", ""),
                "sbp_bank": raffle.get("creator_sbp_bank", "СБП"),
            },
        }

    async def reserve_random_tickets(
        self,
        raffle_id: str,
        user_id: int,
        username: str,
        count: int = 1,
    ) -> Dict[str, Any]:
        """
        Quick lucky pick: selects `count` random currently available tickets
        """
        tickets = await self.db.get_raffle_tickets(raffle_id)
        available = [t["ticket_number"] for t in tickets if t["status"] == "available"]

        if len(available) < count:
            return {
                "success": False,
                "error": f"Недостаточно свободных билетов (доступно: {len(available)})",
            }

        # Randomly sample required number of tickets
        chosen = secrets.SystemRandom().sample(available, count)
        return await self.reserve_specific_tickets(
            raffle_id=raffle_id,
            user_id=user_id,
            username=username,
            ticket_numbers=chosen,
        )

    async def complete_sbp_payment(self, order_id: str) -> Dict[str, Any]:
        """
        Process confirmed SBP payment.
        Converts tickets from 'reserved' to 'sold' (permanent inventory drawdown),
        and delivers instant push notification in MAX bot.
        """
        order = await self.db.get_order(order_id)
        if not order:
            return {"success": False, "error": f"Заказ {order_id} не найден"}

        if order["status"] == "paid":
            return {"success": True, "already_paid": True, "order": order}

        # 1. Confirm payment and update tickets to 'sold'
        confirmed_order = await self.db.confirm_order_payment(order_id)
        if not confirmed_order:
            return {"success": False, "error": "Не удалось обновить статус заказа"}

        raffle = await self.db.get_raffle(order["raffle_id"])

        # 2. Trigger push notification to MAX Messenger user
        if raffle:
            await self.notification_service.notify_ticket_purchase(
                user_id=order["user_id"],
                raffle_title=raffle["title"],
                ticket_numbers=order["ticket_numbers"],
                amount=order["amount"],
                order_id=order_id,
            )

            # 3. Check if all tickets are sold out -> ready for draw!
            if raffle["available_tickets"] == 0:
                logger.info(
                    f"Raffle {raffle['id']} fully sold out! All {raffle['total_tickets']} tickets taken."
                )

        return {
            "success": True,
            "order": confirmed_order,
            "raffle": raffle,
        }

    async def draw_raffle_winner(
        self, raffle_id: str, chat_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute provably fair winner selection for all prize places (Лоты)
        using cryptographically secure RNG.
        """
        raffle = await self.db.get_raffle(raffle_id)
        if not raffle:
            return {"success": False, "error": "Розыгрыш не найден"}

        if raffle["status"] == "completed":
            return {
                "success": False,
                "error": f"Розыгрыш уже завершен.",
                "raffle": raffle,
            }

        # Get all sold tickets
        tickets = await self.db.get_raffle_tickets(raffle_id)
        sold_tickets = [t for t in tickets if t["status"] in ("sold", "winner")]

        if not sold_tickets:
            return {"success": False, "error": "Нет проданных билетов для проведения розыгрыша"}

        prizes = await self.db.get_raffle_prizes(raffle_id)
        if not prizes:
            prizes = [{
                "id": None,
                "place": 1,
                "lot_number": raffle.get("lot_number", 1),
                "title": raffle["title"],
                "prize_image_url": raffle.get("prize_image_url", ""),
            }]

        # Sample winning tickets without replacement
        rng = secrets.SystemRandom()
        available_pool = list(sold_tickets)
        rng.shuffle(available_pool)

        winners = []
        for i, prize in enumerate(prizes):
            if available_pool:
                win_t = available_pool.pop(0)
            else:
                win_t = rng.choice(sold_tickets)

            winning_num = win_t["ticket_number"]
            winner_user_id = win_t["user_id"]
            winner_username = win_t["username"] or f"user_{winner_user_id}"

            winners.append({
                "prize_id": prize.get("id"),
                "place": prize.get("place", i + 1),
                "lot_number": prize.get("lot_number", i + 1),
                "prize_title": prize.get("title", raffle["title"]),
                "ticket_number": winning_num,
                "user_id": winner_user_id,
                "username": winner_username,
            })

        # Update database with all winners
        updated_raffle = await self.db.finish_raffle_draw_multi(
            raffle_id=raffle_id,
            winners=winners,
        )

        # Notify participants and all groups
        await self.notification_service.notify_raffle_winners_multi(
            chat_id=chat_id,
            raffle_title=raffle["title"],
            winners=winners,
        )

        first_w = winners[0] if winners else {}
        return {
            "success": True,
            "raffle": updated_raffle,
            "winners": winners,
            "winning_ticket_number": first_w.get("ticket_number"),
            "winner_user_id": first_w.get("user_id"),
            "winner_username": first_w.get("username"),
        }

    async def start_auto_release_worker(self) -> None:
        """Background loop to periodically unreserve expired unpaid tickets"""
        while True:
            try:
                await self.db.release_expired_reservations()
            except Exception as e:
                logger.error(f"Error in auto-release worker: {e}")
            await asyncio.sleep(10)
