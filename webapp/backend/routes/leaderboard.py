"""Phase 4: HTTP leaderboard endpoint (mirrors the /leaders bot command)."""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from bot.db import get_session
from bot.models import Player

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("")
async def leaderboard(limit: int = 10):
    async with get_session() as db:
        res = await db.execute(
            select(Player).order_by(Player.chains_completed.desc()).limit(limit)
        )
        players = res.scalars().all()
    return [
        {
            "telegram_id": p.telegram_id,
            "display_name": p.display_name,
            "games_played": p.games_played,
            "chains_completed": p.chains_completed,
        }
        for p in players
    ]
