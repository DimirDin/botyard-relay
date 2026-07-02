from aiogram import Router

from bot.handlers.dm import router as dm_router
from bot.handlers.leaderboard import router as leaderboard_router
from bot.handlers.lobby import router as lobby_router
from bot.handlers.monetization import router as monetization_router


def build_root_router() -> Router:
    root = Router(name="root")
    root.include_router(lobby_router)
    root.include_router(dm_router)
    root.include_router(leaderboard_router)
    root.include_router(monetization_router)
    return root
