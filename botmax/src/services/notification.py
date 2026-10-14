"""Push notification bridge between SBP / lottery events and MAX Messenger Bot"""

import logging
from typing import Optional, List, Dict, Any
from maxapi import Bot

logger = logging.getLogger("botmax.notification")


class NotificationService:
    """Service to deliver transaction alerts and lottery outcomes to MAX Messenger users"""

    def __init__(self, bot: Optional[Bot] = None, db: Optional[Any] = None):
        self.bot = bot
        self.db = db

    def set_bot(self, bot: Bot) -> None:
        """Register active bot instance"""
        self.bot = bot

    def set_db(self, db: Any) -> None:
        """Register database instance for chat broadcasts"""
        self.db = db

    async def notify_ticket_purchase(
        self,
        user_id: int,
        raffle_title: str,
        ticket_numbers: List[int],
        amount: float,
        order_id: str,
    ) -> bool:
        """Notify user about successful ticket purchase via SBP"""
        if not self.bot:
            logger.warning("Bot client not attached to NotificationService; skipping push.")
            return False

        tickets_str = ", ".join(f"#{num}" for num in ticket_numbers)
        text = (
            f"🎉 **Оплата по СБП успешно получена!**\n\n"
            f"🎁 **Розыгрыш:** {raffle_title}\n"
            f"🎫 **Ваши билеты:** {tickets_str} (всего: {len(ticket_numbers)} шт.)\n"
            f"💰 **Сумма:** {amount:.2f} ₽\n"
            f"🧾 **Заказ:** `{order_id}`\n\n"
            f"Билеты закреплены за вами и сняты с продажи (убыли из пула). "
            f"Желаем удачи в розыгрыше! 🍀"
        )

        try:
            await self.bot.send_message(user_id=user_id, text=text)
            logger.info(f"Delivered SBP purchase notification to user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send purchase notification to user {user_id}: {e}")
            return False

    async def notify_raffle_winner(
        self,
        chat_id: Optional[int],
        raffle_title: str,
        winning_ticket_number: int,
        winner_user_id: int,
        winner_username: str,
    ) -> bool:
        """Announce single lottery winner (backward compat)"""
        return await self.notify_raffle_winners_multi(
            chat_id=chat_id,
            raffle_title=raffle_title,
            winners=[{
                "place": 1,
                "lot_number": 1,
                "prize_title": raffle_title,
                "ticket_number": winning_ticket_number,
                "user_id": winner_user_id,
                "username": winner_username,
            }]
        )

    async def notify_raffle_winners_multi(
        self,
        chat_id: Optional[int],
        raffle_title: str,
        winners: List[Dict[str, Any]],
    ) -> bool:
        """Announce all lottery winners by place/lot in chat and DM each winner"""
        if not self.bot or not winners:
            return False

        medal_map = {1: "🥇", 2: "🥈", 3: "🥉"}

        lines = [
            "🏆 **РОЗЫГРЫШ ЗАВЕРШЕН!** 🏆\n",
            f"🎮 **Игра:** {raffle_title}\n",
            "🎉 **Победители и призовые места:**\n",
        ]

        for w in winners:
            place = w.get("place", 1)
            lot_num = w.get("lot_number", place)
            p_title = w.get("prize_title") or f"Лот №{lot_num}"
            t_num = w.get("ticket_number")
            u_name = w.get("username") or f"user_{w.get('user_id')}"
            medal = medal_map.get(place, f"🏅 {place} место")
            lines.append(f"{medal} **{place} место (Лот №{lot_num} — {p_title})**: Билет **№{t_num}** — @{u_name}")

        lines.append("\nПоздравляем победителей! Для получения призов с вами свяжется администратор.")
        text = "\n".join(lines)

        # 1. Direct message to each winner
        for w in winners:
            place = w.get("place", 1)
            lot_num = w.get("lot_number", place)
            p_title = w.get("prize_title") or f"Лот №{lot_num}"
            t_num = w.get("ticket_number")
            uid = w.get("user_id")
            if uid:
                try:
                    await self.bot.send_message(
                        user_id=uid,
                        text=(
                            f"🎊 **ПОЗДРАВЛЯЕМ! ВЫ ВЫИГРАЛИ {place}-Е МЕСТО!** 🎊\n\n"
                            f"Ваш билет **№{t_num}** выиграл приз **{p_title}** (Лот №{lot_num}) в игре «{raffle_title}»!\n\n"
                            f"Ожидайте сообщения администратора для получения приза."
                        )
                    )
                except Exception as e:
                    logger.warning(f"Could not DM winner {uid}: {e}")

        # 2. Public announcement to chat
        notified_chats = set()
        if chat_id:
            try:
                await self.bot.send_message(chat_id=chat_id, text=text)
                notified_chats.add(chat_id)
            except Exception as e:
                logger.warning(f"Could not post announcement to chat {chat_id}: {e}")

        # 3. Broadcast to all active groups
        if self.db:
            try:
                active_chats = await self.db.get_active_chats()
                for grp in active_chats:
                    gid = grp.get("chat_id")
                    if gid and gid not in notified_chats:
                        try:
                            await self.bot.send_message(chat_id=gid, text=text)
                            notified_chats.add(gid)
                        except Exception as ge:
                            logger.warning(f"Could not broadcast winner to group {gid}: {ge}")
            except Exception as dbe:
                logger.warning(f"Failed to fetch active chats for winner broadcast: {dbe}")

        return True

    async def broadcast_to_all_groups(
        self, text: str, attachments: Optional[List[Any]] = None, pin: bool = True
    ) -> int:
        """Send message to all active MAX groups and optionally pin it"""
        if not self.bot or not self.db:
            logger.warning("Bot or DB not attached to NotificationService; skipping broadcast.")
            return 0

        active_chats = await self.db.get_active_chats()
        count = 0
        for grp in active_chats:
            gid = grp.get("chat_id")
            if not gid:
                continue
            try:
                sent = await self.bot.send_message(
                    chat_id=gid,
                    text=text,
                    attachments=attachments,
                )
                if pin and sent and hasattr(sent, "body") and sent.body and sent.body.mid:
                    try:
                        await self.bot.pin_message(chat_id=gid, message_id=sent.body.mid, notify=True)
                        await self.db.save_chat(chat_id=gid, pinned_message_id=sent.body.mid)
                    except Exception as pe:
                        logger.warning(f"Could not pin message in group {gid}: {pe}")
                count += 1
            except Exception as e:
                logger.warning(f"Failed to broadcast to group {gid}: {e}")

        logger.info(f"Broadcasted message to {count}/{len(active_chats)} groups")
        return count
