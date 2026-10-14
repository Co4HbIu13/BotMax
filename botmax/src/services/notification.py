"""Push notification bridge between SBP / lottery events and MAX Messenger Bot"""

import logging
from typing import Optional, List, Dict, Any
from maxapi import Bot

logger = logging.getLogger("botmax.notification")


class NotificationService:
    """Service to deliver transaction alerts and lottery outcomes to MAX Messenger users"""

    def __init__(
        self,
        bot: Optional[Bot] = None,
        db: Optional[Any] = None,
        admin_ids: Optional[List[int]] = None,
        mini_app_url: str = "",
    ):
        self.bot = bot
        self.db = db
        self.admin_ids = admin_ids or []
        self.mini_app_url = mini_app_url or "https://anussai.duckdns.org"

    def set_bot(self, bot: Bot) -> None:
        """Register active bot instance"""
        self.bot = bot

    def set_db(self, db: Any) -> None:
        """Register database instance for chat broadcasts"""
        self.db = db

    def set_admin_ids(self, admin_ids: List[int]) -> None:
        """Register target admin MAX user IDs for instant cashier alerts"""
        self.admin_ids = admin_ids

    async def notify_admin_new_reservation(
        self,
        raffle_title: str,
        buyer_username: str,
        buyer_user_id: int,
        buyer_phone: str,
        ticket_numbers: List[int],
        amount: float,
        order_id: str,
        target_admin_ids: Optional[List[int]] = None,
        recipient_name: str = "",
        recipient_phone: str = "",
        recipient_bank: str = "",
    ) -> bool:
        """Notify admin(s) in MAX Bot about a new ticket reservation awaiting confirmation"""
        if not self.bot:
            logger.warning("Bot client not attached to NotificationService; skipping admin alert.")
            return False

        tickets_str = ", ".join(f"#{num}" for num in ticket_numbers)
        phone_line = f"📞 **Телефон покупателя:** {buyer_phone}\n" if buyer_phone else ""
        recipient_line = ""
        if recipient_phone or recipient_bank:
            recipient_line = f"💳 **Куда переводить:** {recipient_bank} ({recipient_phone}) — {recipient_name}\n"

        cashier_url = f"{self.mini_app_url.rstrip('/')}/admin"
        text = (
            f"🔔 **Новый заказ в Кассе! Ожидает оплаты**\n\n"
            f"🎯 **Игра:** {raffle_title}\n"
            f"👤 **Покупатель:** @{buyer_username} (ID: {buyer_user_id})\n"
            f"{phone_line}"
            f"🎟️ **Билеты:** {tickets_str} ({len(ticket_numbers)} шт.)\n"
            f"💰 **Сумма к получению:** **{amount:.2f} ₽**\n"
            f"🧾 **Код перевода:** `{order_id}`\n"
            f"{recipient_line}"
            f"⏱️ **Бронь:** 10 минут\n\n"
            f"👉 После проверки поступления нажмите «Подтвердить оплату» в Кассе:\n"
            f"🔗 {cashier_url}"
        )

        sent_any = False
        bot_id = self.bot.me.user_id if (self.bot.me and hasattr(self.bot.me, "user_id")) else None

        # 1. Collect target admin user IDs from DB and parameters (excluding bot's own user_id)
        target_ids = set()
        if self.db:
            try:
                db_ids = await self.db.get_admin_max_user_ids()
                target_ids.update(db_ids)
            except Exception as e:
                logger.warning(f"Failed to query admin max_user_ids: {e}")

        for aid in (target_admin_ids or self.admin_ids):
            if aid and aid != bot_id:
                target_ids.add(int(aid))

        # 2. Deliver DMs to admin MAX accounts
        for uid in target_ids:
            if uid == bot_id:
                continue
            try:
                await self.bot.send_message(user_id=uid, text=text)
                logger.info(f"Delivered cashier reservation alert to admin DM {uid}")
                sent_any = True
            except Exception as e:
                logger.warning(f"Could not deliver cashier alert to admin {uid} (dialog not started yet): {e}")

        # 3. Deliver alert to active connected group chats / channels
        # Group messages are always delivered and wake up organizers on their phones!
        if self.db:
            try:
                active_chats = await self.db.get_active_chats()
                for c in active_chats:
                    cid = c.get("chat_id")
                    if not cid:
                        continue
                    try:
                        await self.bot.send_message(chat_id=cid, text=text)
                        logger.info(f"Delivered cashier reservation alert to group chat {cid}")
                        sent_any = True
                    except Exception as ch_err:
                        logger.warning(f"Could not send cashier alert to chat {cid}: {ch_err}")
            except Exception as e:
                logger.warning(f"Failed to broadcast cashier alert to active chats: {e}")

        return sent_any

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

    async def broadcast_raffle_announcement(
        self,
        raffle: Dict[str, Any],
        keyboard: Any,
        pin: bool = True,
    ) -> int:
        """
        Broadcast complete raffle showcase with lot breakdown and photos to all active MAX groups.
        Posts main announcement with Lot 1 photo and interactive Mini-App keyboard.
        Posts follow-up photos for Lot 2, Lot 3, etc. so all prizes are fully displayed in chat.
        """
        if not self.bot or not self.db:
            logger.warning("Bot or DB not attached; skipping broadcast.")
            return 0

        active_chats = await self.db.get_active_chats()
        if not active_chats:
            return 0

        prizes = raffle.get("prizes", [])
        medal_map = {1: "🥇", 2: "🥈", 3: "🥉"}

        prizes_lines = []
        for p in prizes:
            pl = p.get("place", 1)
            lt = p.get("lot_number", pl)
            t = p.get("title", "")
            d = p.get("description", "").strip()
            m = medal_map.get(pl, f"🏅 {pl} место")
            line = f"{m} **Лот №{lt} ({pl} место)**: {t}"
            if d:
                line += f"\n   _{d}_"
            prizes_lines.append(line)

        prizes_block = "\n".join(prizes_lines) + "\n\n" if prizes_lines else ""
        creator_line = f"👤 Организатор: **{raffle['creator_name']}**\n" if raffle.get("creator_name") else ""

        main_text = (
            f"🎁 **Внимание! Новый розыгрыш в BotMAX!**\n\n"
            f"🎮 **{raffle['title']}**\n\n"
            f"{creator_line}"
            f"{raffle.get('description', '')}\n\n"
            f"🏆 **Призовые места и лоты:**\n"
            f"{prizes_block}"
            f"💰 Стоимость 1 билета: **{raffle['price_per_ticket']:.0f} ₽**\n"
            f"🎫 Всего билетов: **{raffle['total_tickets']} шт.**\n"
            f"🟢 Доступно сейчас: **{raffle['available_tickets']} шт.**\n\n"
            f"Мгновенная оплата по СБП в любом банке РФ. Билеты выбывают сразу!\n"
            f"👇 **Нажмите кнопку ниже, чтобы открыть табло и занять номера:**"
        )

        # Resolve media for each lot
        from pathlib import Path
        async def _resolve_media(img_url: str):
            if not img_url:
                return None
            img_url = img_url.strip()
            # 1. Local upload check
            filename = None
            if img_url.startswith("/static/uploads/"):
                filename = img_url.replace("/static/uploads/", "")
            elif "/static/uploads/" in img_url:
                filename = img_url.split("/static/uploads/")[-1]

            if filename:
                p = Path("data/uploads") / filename
                if p.exists():
                    try:
                        from maxapi.types.input_media import InputMedia
                        return InputMedia(path=str(p.resolve()))
                    except Exception as ie:
                        logger.warning(f"Failed to create InputMedia for {p}: {ie}")

            # 2. Web URL check
            if img_url.startswith("http://") or img_url.startswith("https://"):
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=8.0) as client:
                        resp = await client.get(img_url)
                        if resp.status_code == 200 and resp.content:
                            from maxapi.types.input_media import InputMediaBuffer
                            return InputMediaBuffer(buffer=resp.content, filename="lot_prize.jpg")
                except Exception as he:
                    logger.warning(f"Could not download photo {img_url} for broadcast: {he}")

            return None

        lot_media_list = []
        for p in prizes:
            img = p.get("prize_image_url") or raffle.get("prize_image_url")
            med = await _resolve_media(img) if img else None
            lot_media_list.append({
                "place": p.get("place", 1),
                "lot_number": p.get("lot_number", 1),
                "title": p.get("title", ""),
                "description": p.get("description", ""),
                "media": med,
            })

        count = 0
        for grp in active_chats:
            gid = grp.get("chat_id")
            if not gid:
                continue
            try:
                # 1. Send Main Message with Lot 1 media (if available) and interactive keyboard
                main_attachments = []
                if lot_media_list and lot_media_list[0]["media"]:
                    main_attachments.append(lot_media_list[0]["media"])
                if keyboard:
                    main_attachments.append(keyboard)

                sent = await self.bot.send_message(
                    chat_id=gid,
                    text=main_text,
                    attachments=main_attachments if main_attachments else None,
                )

                if pin and sent and hasattr(sent, "body") and sent.body and sent.body.mid:
                    try:
                        await self.bot.pin_message(chat_id=gid, message_id=sent.body.mid, notify=True)
                        await self.db.save_chat(chat_id=gid, pinned_message_id=sent.body.mid)
                    except Exception as pe:
                        logger.warning(f"Could not pin message in group {gid}: {pe}")

                # 2. If multiple lots, send follow-up photo cards for Lot 2, Lot 3...
                if len(lot_media_list) > 1:
                    for lot in lot_media_list[1:]:
                        medal = medal_map.get(lot["place"], f"🏅 {lot['place']} место")
                        lot_text = (
                            f"{medal} **Лот №{lot['lot_number']} ({lot['place']} место) — {lot['title']}**"
                        )
                        if lot["description"]:
                            lot_text += f"\n_{lot['description']}_"

                        lot_att = [lot["media"]] if lot["media"] else None
                        try:
                            await self.bot.send_message(
                                chat_id=gid,
                                text=lot_text,
                                attachments=lot_att,
                            )
                        except Exception as le:
                            logger.warning(f"Could not send follow-up lot photo to group {gid}: {le}")

                count += 1
            except Exception as e:
                logger.warning(f"Failed to broadcast raffle to group {gid}: {e}")

        logger.info(f"Broadcasted raffle {raffle['id']} to {count}/{len(active_chats)} groups with all lot photos")
        return count
