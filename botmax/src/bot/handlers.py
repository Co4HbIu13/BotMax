"""Event handlers for MAX Messenger Bot (Direct Messages & Group Chats)"""

import logging
from typing import Any, List, Optional
from maxapi import Bot, Dispatcher
from maxapi.types import (
    MessageCreated,
    MessageCallback,
    BotStarted,
    BotAdded,
)
from ..config import Config
from ..database.db import Database
from ..services.lottery import LotteryService
from .keyboards import (
    main_menu_keyboard,
    group_showcase_keyboard,
    raffles_list_keyboard,
    raffle_detail_keyboard,
)

logger = logging.getLogger("botmax.bot.handlers")


def register_handlers(
    dp: Dispatcher,
    bot: Bot,
    config: Config,
    db: Database,
    lottery_service: LotteryService,
) -> None:
    """Register all message, command, group, and callback handlers"""

    def _get_bot_info() -> tuple[str, int]:
        bot_username = bot.me.username if bot.me and bot.me.username else "se14443050_bot"
        bot_id = bot.me.user_id if bot.me and bot.me.user_id else 471249415
        return bot_username, bot_id

    def _progress_bar(percent: float, length: int = 10) -> str:
        """Generate visual progress bar (e.g. 🟩🟩🟩⬜⬜)"""
        filled = int(round((percent / 100) * length))
        filled = max(0, min(length, filled))
        return "🟩" * filled + "⬜" * (length - filled)

    def _build_group_showcase_text(raffles: List[dict]) -> str:
        lines = [
            "🎰 **Официальные розыгрыши призов BotMAX**\n",
            "Участвуйте в розыгрышах ценных призов с моментальной оплатой через **СБП (Систему быстрых платежей)**!\n",
            "Каждый купленный билет дает шанс выиграть все призовые места игры.\n",
            "🔥 **Активные игры:**\n",
        ]
        medal_map = {1: "🥇", 2: "🥈", 3: "🥉"}
        for r in raffles[:5]:
            bar = _progress_bar(r.get("percent_sold", 0))
            prizes = r.get("prizes", [])
            lines.append(f"🎮 **{r['title']}**")
            creator_name = r.get("creator_name")
            if creator_name and creator_name != "Главный Администратор":
                lines.append(f"  👤 Организатор: **{creator_name}**")
            if prizes:
                lines.append("  🏆 **Призы по местам:**")
                for p in prizes:
                    pl = p.get("place", 1)
                    lt = p.get("lot_number", pl)
                    pt = p.get("title", "")
                    m = medal_map.get(pl, f"🏅 {pl}м")
                    lines.append(f"  {m} {pl} место (Лот №{lt}): **{pt}**")
            lines.append(
                f"  💰 Билет: **{r['price_per_ticket']:.0f} ₽** | Свободно: **{r['available_tickets']}/{r['total_tickets']}**\n"
                f"  Прогресс: {bar} {r.get('percent_sold', 0)}%\n"
            )
        lines.append("👇 **Нажмите кнопку ниже, чтобы открыть табло и выбрать билеты:**")
        return "\n".join(lines)

    async def _send_group_showcase(target_chat_id: int, pin: bool = True):
        raffles = await lottery_service.get_active_raffles()
        bot_username, bot_id = _get_bot_info()

        text = _build_group_showcase_text(raffles)
        kb = group_showcase_keyboard(
            mini_app_url=config.mini_app_url,
            bot_username=bot_username,
            bot_id=bot_id,
        )

        try:
            sent = await bot.send_message(
                chat_id=target_chat_id,
                text=text,
                attachments=[kb],
            )
            if pin and sent and hasattr(sent, "body") and sent.body and sent.body.mid:
                try:
                    await bot.pin_message(chat_id=target_chat_id, message_id=sent.body.mid, notify=True)
                    await db.save_chat(chat_id=target_chat_id, pinned_message_id=sent.body.mid)
                    logger.info(f"Showcase pinned in chat {target_chat_id}")
                except Exception as pin_err:
                    logger.warning(f"Could not pin message in {target_chat_id} (check bot admin rights): {pin_err}")
            return sent
        except Exception as e:
            logger.error(f"Failed to send group showcase to {target_chat_id}: {e}")
            return None

    # ==========================================
    # 1. BOT ADDED TO GROUP / CHANNEL EVENT
    # ==========================================
    @dp.bot_added()
    async def on_bot_added(event: BotAdded):
        """Triggered automatically when the bot is added to a group or channel"""
        chat_id = event.chat_id
        is_channel = getattr(event, "is_channel", False)
        logger.info(f"Bot added to chat_id={chat_id} (is_channel={is_channel})")

        # Record group in database
        await db.save_chat(
            chat_id=chat_id,
            chat_type="channel" if is_channel else "chat",
        )

        # Greet group and auto-pin lottery showcase
        await _send_group_showcase(chat_id, pin=True)

    # ==========================================
    # 2. USER STARTED BOT (DIRECT 1-ON-1 DIALOG)
    # ==========================================
    @dp.bot_started()
    async def on_bot_started(event: BotStarted):
        """User pressed Start in a direct dialog"""
        sender = getattr(event, "user", None)
        user_id = getattr(sender, "user_id", None) or event.chat_id
        username = getattr(sender, "username", "") or ""
        first_name = getattr(sender, "first_name", "") or "Участник"

        await db.upsert_user(user_id=user_id, username=username, first_name=first_name)
        logger.info(f"Bot started by user {user_id} (@{username})")

        bot_username, bot_id = _get_bot_info()

        welcome_text = (
            f"👋 **Привет, {first_name}!**\n\n"
            f"Добро пожаловать в **BotMAX** — официальное мини-приложение для розыгрышей призов "
            f"в мессенджере MAX с мгновенной оплатой через **СБП (Систему быстрых платежей)**!\n\n"
            f"🎯 **Как это работает:**\n"
            f"1. Выберите желаемый приз (iPhone 16, PS5, наушники и др.)\n"
            f"2. Выберите понравившиеся номера билетов на интерактивном табло\n"
            f"3. Оплатите по СБП в приложении любого банка РФ\n"
            f"4. Билеты сразу снимаются с продажи (убывают из общего пула) и закрепляются за вами!\n"
            f"5. После продажи всех билетов бот автоматически определит победителя 🏆\n\n"
            f"Нажмите кнопку ниже, чтобы открыть мини-приложение:"
        )

        kb = main_menu_keyboard(
            mini_app_url=config.mini_app_url,
            bot_username=bot_username,
            bot_id=bot_id,
            user_id=user_id,
            username=username,
        )

        await bot.send_message(
            chat_id=event.chat_id,
            text=welcome_text,
            attachments=[kb],
        )

    # ==========================================
    # 3. MESSAGE DISPATCHER (DIRECT & GROUP)
    # ==========================================
    @dp.message_created()
    async def on_message_created(event: MessageCreated):
        """Universal handler for commands, mentions, and text across dialogs & groups"""
        sender = getattr(event.message, "sender", None) or getattr(event, "from_user", None)
        if not sender:
            return

        user_id = getattr(sender, "user_id", 0)
        username = getattr(sender, "username", "") or ""
        first_name = getattr(sender, "first_name", "") or "Участник"

        await db.upsert_user(user_id=user_id, username=username, first_name=first_name)

        recipient = getattr(event.message, "recipient", None)
        chat_id = getattr(recipient, "chat_id", None) or user_id
        chat_type = str(getattr(recipient, "chat_type", "dialog"))
        is_group = bool(getattr(recipient, "chat_id", None) or chat_type == "chat")

        if is_group and getattr(recipient, "chat_id", None):
            await db.save_chat(chat_id=recipient.chat_id, chat_type="chat")

        body = getattr(event.message, "body", None)
        text = (getattr(body, "text", "") or "").strip()
        if not text:
            return

        bot_username, bot_id = _get_bot_info()

        parts = text.split()
        first_word = parts[0].lower()
        args = parts[1:]
        cmd = ""

        # Parse command name and filter out mentions of other bots
        if first_word.startswith("/"):
            raw_cmd = first_word[1:]
            if "@" in raw_cmd:
                cmd_name, target_bot = raw_cmd.split("@", 1)
                if target_bot.lower() != bot_username.lower():
                    return  # Addressed to another bot in the group
                cmd = cmd_name
            else:
                cmd = raw_cmd
        elif f"@{bot_username.lower()}" in text.lower():
            cmd = "mention"
        elif first_word in ["розыгрыш", "розыгрыши", "лотерея", "призы", "билеты", "витрина"]:
            cmd = "lottery"

        if not cmd:
            return

        logger.info(
            f"Parsed command '{cmd}' from user {user_id} (@{username}) in chat {chat_id} (group={is_group})"
        )

        # ------------------------------------------
        # /start
        # ------------------------------------------
        if cmd == "start":
            if is_group:
                await _send_group_showcase(chat_id, pin=False)
            else:
                welcome_text = (
                    f"👋 **Главное меню BotMAX**\n\n"
                    f"Участвуйте в розыгрышах ценных призов с быстрой оплатой по СБП!\n"
                    f"Все билеты убывают из продажи в реальном времени.\n\n"
                    f"Выберите действие:"
                )
                kb = main_menu_keyboard(config.mini_app_url, bot_username, bot_id, user_id=user_id, username=username)
                await bot.send_message(chat_id=chat_id, text=welcome_text, attachments=[kb])

        # ------------------------------------------
        # /post, /showcase, /pin (Publish and Pin Showcase in Group)
        # ------------------------------------------
        elif cmd in ["post", "showcase", "pin"]:
            sent = await _send_group_showcase(chat_id, pin=True)
            if not is_group and user_id in config.admin_ids:
                # If admin called /post in private chat, broadcast to all registered groups
                active_chats = await db.get_active_chats()
                for grp in active_chats:
                    if grp.get("chat_id") != chat_id:
                        await _send_group_showcase(grp["chat_id"], pin=True)
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"📢 Витрина опубликована и закреплена в {len(active_chats)} подключенных группах!",
                )

        # ------------------------------------------
        # /lottery, /raffles, mention @bot
        # ------------------------------------------
        elif cmd in ["lottery", "raffles", "mention"]:
            if is_group:
                await _send_group_showcase(chat_id, pin=False)
            else:
                raffles = await lottery_service.get_active_raffles()
                if not raffles:
                    await bot.send_message(chat_id=chat_id, text="Пока нет активных розыгрышей. Загляните позже!")
                    return

                lines = ["🎁 **Актуальные игры и призовые лоты:**\n"]
                medal_map = {1: "🥇", 2: "🥈", 3: "🥉"}
                for r in raffles:
                    bar = _progress_bar(r.get("percent_sold", 0))
                    prizes = r.get("prizes", [])
                    lines.append(f"🎮 **{r['title']}**")
                    if prizes:
                        for p in prizes:
                            pl = p.get("place", 1)
                            lt = p.get("lot_number", pl)
                            pt = p.get("title", "")
                            m = medal_map.get(pl, f"🏅 {pl}м")
                            lines.append(f"  {m} {pl} место (Лот №{lt}): **{pt}**")
                    lines.append(
                        f"  💰 Билет: **{r['price_per_ticket']:.0f} ₽** | Осталось: **{r['available_tickets']}/{r['total_tickets']}**\n"
                        f"  Прогресс: {bar} {r.get('percent_sold', 0)}%\n"
                    )

                lines.append("\nНажмите на игру ниже или откройте мини-приложение:")
                kb = raffles_list_keyboard(raffles, config.mini_app_url, bot_username, bot_id)
                await bot.send_message(chat_id=chat_id, text="\n".join(lines), attachments=[kb])

        # ------------------------------------------
        # /tickets, /my_tickets
        # ------------------------------------------
        elif cmd in ["tickets", "my_tickets"]:
            tickets = await db.get_user_tickets(user_id)
            if not tickets:
                await bot.send_message(
                    chat_id=chat_id,
                    text="У вас пока нет купленных билетов 🎫\nОткройте мини-приложение, чтобы выбрать лоты и билеты!",
                    attachments=[main_menu_keyboard(config.mini_app_url, bot_username, bot_id)],
                )
                return

            by_raffle = {}
            for t in tickets:
                r_title = t["raffle_title"]
                by_raffle.setdefault(r_title, []).append(t)

            lines = [f"🎫 **Ваши билеты ({len(tickets)} шт.):**\n"]
            for r_title, t_list in by_raffle.items():
                t_nums = ", ".join(f"#{t['ticket_number']}" for t in t_list)
                status_badge = "🟢 В игре"
                if any(t["ticket_status"] == "winner" for t in t_list):
                    status_badge = "🏆 ВЫ ВЫИГРАЛИ!"
                lines.append(f"**{r_title}** [{status_badge}]\nНомера: {t_nums}\n")

            kb = main_menu_keyboard(config.mini_app_url, bot_username, bot_id)
            await bot.send_message(chat_id=chat_id, text="\n".join(lines), attachments=[kb])

        # ------------------------------------------
        # /help
        # ------------------------------------------
        elif cmd == "help":
            help_text = (
                "ℹ️ **Как работает BotMAX и оплата по СБП:**\n\n"
                "1. **Выбор билетов:**\n"
                "   В мини-приложении доступно интерактивное табло. Вы можете выбрать конкретные "
                "   номера билетов или довериться удаче («Случайный билет»).\n\n"
                "2. **Бронь и убытие билетов:**\n"
                "   При переходе к оплате выбранные билеты бронируются на 10 минут. "
                "   Другие участники не могут их занять. Если оплата не завершена за 10 минут, "
                "   билеты автоматически возвращаются в продажу.\n\n"
                "3. **Оплата через СБП:**\n"
                "   Генерируется динамический QR-код и платежная ссылка СБП (НСПК). "
                "   Вы можете отсканировать QR или открыть приложение любого мобильного банка РФ.\n\n"
                "4. **Честный розыгрыш:**\n"
                "   Как только все билеты раскуплены (или наступает время финала), "
                "   криптографический ГСЧ определяет выигрышный билет. "
                "   Бот мгновенно объявляет победителя!"
            )
            kb = main_menu_keyboard(config.mini_app_url, bot_username, bot_id)
            await bot.send_message(chat_id=chat_id, text=help_text, attachments=[kb])

        # ------------------------------------------
        # /admin
        # ------------------------------------------
        elif cmd == "admin":
            if user_id not in config.admin_ids:
                await bot.send_message(chat_id=chat_id, text="⛔ Доступ к панели администратора ограничен.")
                return

            raffles = await lottery_service.get_active_raffles()
            active_chats = await db.get_active_chats()
            total_revenue = sum(r["sold_tickets"] * r["price_per_ticket"] for r in raffles)
            total_sold = sum(r["sold_tickets"] for r in raffles)

            admin_text = (
                f"👑 **Панель администратора BotMAX**\n\n"
                f"📊 **Общая статистика:**\n"
                f"• Всего розыгрышей: {len(raffles)}\n"
                f"• Продано билетов: {total_sold} шт.\n"
                f"• Оборот СБП: {total_revenue:,.2f} ₽\n"
                f"• Подключенных групп/каналов: {len(active_chats)}\n\n"
                f"Веб-панель управления (в браузере):\n"
                f"🔗 {config.mini_app_url}/admin\n\n"
                f"Команды администратора в чате:\n"
                f"`/post` — опубликовать и закрепить витрину в текущей группе\n"
                f"`/draw <raffle_id>` — досрочно провести розыгрыш и объявить победителя\n"
            )
            await bot.send_message(chat_id=chat_id, text=admin_text)

        # ------------------------------------------
        # /draw <raffle_id>
        # ------------------------------------------
        elif cmd == "draw":
            if user_id not in config.admin_ids:
                return

            if not args:
                await bot.send_message(
                    chat_id=chat_id,
                    text="Использование: `/draw <raffle_id>` (например: `/draw raffle_lot_1_skovoroda`)",
                )
                return

            raffle_id = args[0].strip()
            result = await lottery_service.draw_raffle_winner(raffle_id=raffle_id, chat_id=chat_id)
            if not result["success"]:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Ошибка проведения розыгрыша: {result.get('error')}",
                )
                return

            await bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🎉 Розыгрыш **{raffle_id}** успешно проведен!\n"
                    f"Выигрышный билет: **#{result['winning_ticket_number']}**\n"
                    f"Победитель: @{result['winner_username']} (ID: {result['winner_user_id']})"
                ),
            )

    # ==========================================
    # 4. CALLBACK HANDLERS (INLINE BUTTONS)
    # ==========================================
    @dp.message_callback()
    async def on_callback(event: MessageCallback):
        """Handle inline button clicks in dialogs and group chats"""
        payload = event.callback.payload or ""
        logger.info(f"Received callback payload: {payload}")
        bot_username, bot_id = _get_bot_info()
        cb_user = getattr(event.callback, "user", None)
        cb_uid = getattr(cb_user, "user_id", None)
        cb_uname = getattr(cb_user, "username", "")

        if payload == "action:main_menu":
            kb = main_menu_keyboard(config.mini_app_url, bot_username, bot_id, user_id=cb_uid, username=cb_uname)
            await event.answer(
                new_text="👋 **Главное меню BotMAX**\n\nВыберите действие ниже:",
                attachments=[kb],
            )

        elif payload == "action:list_raffles":
            raffles = await lottery_service.get_active_raffles()
            lines = ["🎁 **Актуальные лоты розыгрыша:**\n"]
            for r in raffles:
                bar = _progress_bar(r.get("percent_sold", 0))
                lot_num = r.get("lot_number", 1)
                lines.append(
                    f"**Лот №{lot_num}: {r['title']}**\n"
                    f"💰 {r['price_per_ticket']:.0f} ₽ | Свободно: {r['available_tickets']}/{r['total_tickets']}\n"
                    f"{bar} {r.get('percent_sold', 0)}%\n"
                )
            kb = raffles_list_keyboard(raffles, config.mini_app_url, bot_username, bot_id)
            await event.answer(new_text="\n".join(lines), attachments=[kb])

        elif payload == "action:my_tickets":
            user_id = event.callback.user.user_id
            tickets = await db.get_user_tickets(user_id)
            kb = main_menu_keyboard(config.mini_app_url, bot_username, bot_id, user_id=cb_uid, username=cb_uname)
            if not tickets:
                await event.answer(
                    notification="У вас пока нет купленных билетов",
                    new_text="🎫 У вас пока нет билетов. Откройте мини-приложение, чтобы приобрести!",
                    attachments=[kb],
                )
            else:
                lines = [f"🎫 **Ваши билеты ({len(tickets)} шт.):**\n"]
                for t in tickets[:10]:
                    lines.append(f"• Билет **#{t['ticket_number']}** — {t['raffle_title']}")
                await event.answer(new_text="\n".join(lines), attachments=[kb])

        elif payload == "action:help":
            help_text = (
                "ℹ️ **Правила BotMAX:**\n\n"
                "• Оплата билетов производится через СБП любого российского банка.\n"
                "• Купленные билеты навсегда снимаются с продажи (убывают из пула).\n"
                "• Победитель определяется честным случайным розыгрышем.\n"
                "• Приз вручается победителю администрацией."
            )
            kb = main_menu_keyboard(config.mini_app_url, bot_username, bot_id)
            await event.answer(new_text=help_text, attachments=[kb])

        elif payload.startswith("raffle_info:"):
            raffle_id = payload.split(":", 1)[1]
            raffle = await lottery_service.get_raffle_details(raffle_id)
            if not raffle:
                await event.answer(notification="Розыгрыш не найден")
                return

            bar = _progress_bar(raffle.get("percent_sold", 0))
            lot_num = raffle.get("lot_number", 1)
            text = (
                f"🎁 **Лот №{lot_num}: {raffle['title']}**\n\n"
                f"{raffle.get('description', '')}\n\n"
                f"🎫 Всего билетов: **{raffle['total_tickets']}**\n"
                f"🟢 Доступно: **{raffle['available_tickets']}**\n"
                f"🔴 Выкуплено (убыло): **{raffle['sold_tickets']}**\n"
                f"💰 Стоимость 1 билета: **{raffle['price_per_ticket']:.0f} ₽**\n"
                f"📊 Заполнено: {bar} **{raffle['percent_sold']}%**"
            )
            kb = raffle_detail_keyboard(raffle_id, config.mini_app_url, bot_username, bot_id)
            await event.answer(new_text=text, attachments=[kb])
