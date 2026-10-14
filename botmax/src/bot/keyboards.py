"""Inline keyboards for MAX Messenger Bot (In-App Mini-App & Native Buttons Only)"""

from typing import List, Dict, Any, Optional
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.types import (
    CallbackButton,
    OpenAppButton,
    LinkButton,
)


def main_menu_keyboard(
    mini_app_url: str = "",
    bot_username: str = "se14443050_bot",
    bot_id: int = 471249415,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
) -> Any:
    """Main menu keyboard with Mini App launch directly inside MAX"""
    builder = InlineKeyboardBuilder()

    # Main action: Open Mini App inside MAX
    builder.row(
        OpenAppButton(
            text="🎰 Открыть лотерею (Мини-апп)",
            web_app=bot_username,
            contact_id=bot_id,
            payload=f"uid_{user_id}" if user_id else None,
        )
    )

    if mini_app_url and user_id:
        clean_url = f"{mini_app_url.rstrip('/')}/?user_id={user_id}&username={username or ''}"
        builder.row(
            LinkButton(
                text="🌐 Открыть в браузере",
                url=clean_url,
            )
        )

    # In-chat quick actions
    builder.row(
        CallbackButton(text="🎁 Призы и статус", payload="action:list_raffles"),
        CallbackButton(text="🎫 Мои билеты", payload="action:my_tickets"),
    )

    builder.row(
        CallbackButton(text="ℹ️ Правила и СБП", payload="action:help"),
    )

    return builder.as_markup()


def group_showcase_keyboard(
    mini_app_url: str = "",
    bot_username: str = "se14443050_bot",
    bot_id: int = 471249415,
) -> Any:
    """Showcase keyboard optimized for group chats and channels (In-App MAX only)"""
    builder = InlineKeyboardBuilder()

    # Main action: Open Mini App directly in MAX
    builder.row(
        OpenAppButton(
            text="🎰 Открыть витрину (Мини-апп)",
            web_app=bot_username,
            contact_id=bot_id,
        )
    )

    # Group actions
    builder.row(
        CallbackButton(text="🎁 Список призов", payload="action:list_raffles"),
        CallbackButton(text="ℹ️ Как играть и СБП", payload="action:help"),
    )

    return builder.as_markup()


def raffles_list_keyboard(
    raffles: List[Dict[str, Any]],
    mini_app_url: str = "",
    bot_username: str = "se14443050_bot",
    bot_id: int = 471249415,
) -> Any:
    """Keyboard listing available raffles with buttons to view details and launch Mini-App"""
    builder = InlineKeyboardBuilder()

    for r in raffles[:5]:  # Top active raffles
        percent = r.get("percent_sold", 0)
        rem = r.get("available_tickets", 0)
        builder.row(
            CallbackButton(
                text=f"{r['title'][:22]}... ({rem} шт | {percent}%)",
                payload=f"raffle_info:{r['id']}",
            )
        )

    builder.row(
        OpenAppButton(
            text="🎰 Открыть мини-приложение",
            web_app=bot_username,
            contact_id=bot_id,
        )
    )

    builder.row(
        CallbackButton(text="🔙 Назад в меню", payload="action:main_menu"),
    )

    return builder.as_markup()


def raffle_detail_keyboard(
    raffle_id: str,
    mini_app_url: str = "",
    bot_username: str = "se14443050_bot",
    bot_id: int = 471249415,
) -> Any:
    """Keyboard for specific raffle view with direct in-app launch"""
    builder = InlineKeyboardBuilder()

    builder.row(
        OpenAppButton(
            text="🎟️ Выбрать билеты в приложении",
            web_app=bot_username,
            contact_id=bot_id,
            payload=f"raffle_{raffle_id}",
        )
    )

    builder.row(
        CallbackButton(text="🎁 Все призы", payload="action:list_raffles"),
        CallbackButton(text="🔙 Главное меню", payload="action:main_menu"),
    )

    return builder.as_markup()
