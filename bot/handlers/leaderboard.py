"""Phase 4: personal book history + chains_completed leaderboard."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select

from bot.db import get_session
from bot.models import Player

router = Router(name="leaderboard")


@router.message(Command("mystats"))
async def cmd_mystats(message: Message) -> None:
    async with get_session() as db:
        player = await db.get(Player, message.from_user.id)
    if not player:
        await message.answer("Ты ещё не играл(а) в Кривой телефон.")
        return
    await message.answer(
        f"📊 {player.display_name}\n"
        f"Игр сыграно: {player.games_played}\n"
        f"Книг завершено (твоих цепочек, где ты был(а) первым автором): {player.chains_completed}"
    )


@router.message(Command("leaders"))
async def cmd_leaders(message: Message) -> None:
    async with get_session() as db:
        res = await db.execute(
            select(Player).order_by(Player.chains_completed.desc()).limit(10)
        )
        top = res.scalars().all()
    if not top:
        await message.answer("Пока никто не завершил ни одной книги.")
        return
    lines = ["🏆 Топ по завершённым книгам:"]
    for i, p in enumerate(top, start=1):
        lines.append(f"{i}. {p.display_name} — {p.chains_completed}")
    await message.answer("\n".join(lines))
