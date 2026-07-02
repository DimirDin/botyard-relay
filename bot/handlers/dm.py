"""Private-chat handlers: /start deep-link, free-text phrase/guess submission, and the
photo fallback for the drawing step (in case a player can't/won't use the Mini App
canvas -- they can just send a photo of a hand-drawn doodle instead)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot import texts
from bot.deps import session_service
from bot.keyboards import draw_webapp_keyboard
from bot.services.moderation import moderate
from bot.services.session_service import RoundType, round_type_for
from bot.services.storage import relay_drawing_file_id

router = Router(name="dm")


@router.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: Message, command: CommandObject) -> None:
    await message.answer(
        "Привет! Я «Кривой телефон» 🎨 — бот для игры в групповом чате: одна фраза, "
        "испорченная цепочкой рисунков и пересказов. Позови меня командой /relay в свою "
        "группу, чтобы начать."
    )


@router.message(F.chat.type == "private", F.text, ~F.text.startswith("/"))
async def dm_text(message: Message) -> None:
    sid = await session_service.get_player_session(message.from_user.id)
    if not sid:
        await message.answer(
            "У тебя сейчас нет активной игры. Позови меня командой /relay в групповой чат."
        )
        return

    round_number = await session_service.current_round(sid)
    rtype = round_type_for(round_number)
    if rtype == RoundType.DRAW:
        await message.answer(
            "В этом раунде нужно рисовать, а не писать текст.",
            reply_markup=draw_webapp_keyboard(sid, round_number),
        )
        return

    allowed, reason = moderate(message.text)
    if not allowed:
        await message.answer(reason)
        return

    result = await session_service.submit_entry(sid, message.from_user.id, message.text)
    if not result.ok:
        await message.answer(result.reason)
        return

    await message.answer(texts.SUBMIT_ACCEPTED)

    if result.round_complete:
        advance = await session_service.maybe_advance_if_complete(sid)
        if advance:
            await _dispatch(message, advance)


@router.message(F.chat.type == "private", F.photo)
async def dm_photo(message: Message) -> None:
    """Fallback drawing path: a player just sends a photo instead of using the canvas
    Mini App. We relay it into the storage channel and record its new file_id."""
    sid = await session_service.get_player_session(message.from_user.id)
    if not sid:
        return
    round_number = await session_service.current_round(sid)
    rtype = round_type_for(round_number)
    if rtype != RoundType.DRAW:
        await message.answer("Сейчас не раунд рисования — напиши текстом.")
        return

    source_file_id = message.photo[-1].file_id
    stored_file_id = await relay_drawing_file_id(
        message.bot, source_file_id, caption=f"draw:{message.from_user.id}:{sid}:{round_number}"
    )
    result = await session_service.submit_entry(sid, message.from_user.id, stored_file_id, entry_type="drawing")
    if not result.ok:
        await message.answer(result.reason)
        return

    await message.answer(texts.SUBMIT_ACCEPTED)
    if result.round_complete:
        advance = await session_service.maybe_advance_if_complete(sid)
        if advance:
            await _dispatch(message, advance)


async def _dispatch(message: Message, advance) -> None:
    from bot.keyboards import forward_story_keyboard

    for note in advance.notifications:
        try:
            if note.file_id:
                await message.bot.send_photo(note.player_id, note.file_id, caption=note.text)
            else:
                await message.bot.send_message(note.player_id, note.text)
        except Exception:
            pass
    for gnote in advance.group_notifications:
        kb = forward_story_keyboard(gnote.forward_button_entry_id) if gnote.forward_button_entry_id else None
        try:
            await message.bot.send_message(gnote.chat_id, gnote.text, reply_markup=kb)
        except Exception:
            pass
