"""Group-chat handlers: /relay command and the "Я в деле" join button."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message

from bot import texts
from bot.config import settings
from bot.deps import session_service
from bot.keyboards import join_lobby_keyboard

router = Router(name="lobby")


@router.message(Command("relay"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_relay(message: Message) -> None:
    result = await session_service.start_lobby(message.chat.id)
    if not result.ok:
        await message.reply(texts.LOBBY_ALREADY_RUNNING)
        return

    text = texts.LOBBY_OPEN.format(seconds=settings.lobby_window_seconds)
    await message.answer(text, reply_markup=join_lobby_keyboard(result.session_id))


@router.callback_query(F.data.startswith("join:"))
async def cb_join(callback: CallbackQuery) -> None:
    user = callback.from_user
    display_name = user.full_name or user.username or str(user.id)
    result = await session_service.join_lobby(
        chat_id=callback.message.chat.id,
        player_id=user.id,
        display_name=display_name,
        username=user.username,
    )
    if not result.ok:
        await callback.answer(result.reason, show_alert=True)
        return

    await callback.answer(texts.LOBBY_JOINED.format(name=display_name, count=result.player_count))

    # Try to proactively DM the player so we know we can reach them later; if this
    # fails (user never started a chat with the bot), the deep-link fallback in
    # cmd_start below is what actually gets used at round time.
    try:
        await callback.bot.send_message(
            user.id,
            "Ты записан(а) на Кривой телефон! Как только лобби закроется, я напишу тебе сюда.",
        )
    except Exception:
        await callback.message.answer(
            f"{display_name}, чтобы точно получать задания, открой чат со мной: "
            f"https://t.me/{settings.bot_username}?start=hello"
        )
