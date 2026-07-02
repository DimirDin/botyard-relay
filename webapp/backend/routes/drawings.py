"""Receives finished drawings from the Mini App canvas.

Flow: validate initData -> decode the submitted PNG -> forward it into the private
storage channel (Telegram-as-CDN, see bot/services/storage.py) -> record the resulting
file_id as this round's entry in Redis/Postgres via the shared SessionService -> tell the
Mini App whether the round is now complete so it can show a "waiting for others" state.
"""
from __future__ import annotations

import base64

from aiogram import Bot
from fastapi import APIRouter, Form, HTTPException

from bot.config import settings as bot_settings
from bot.deps import session_service
from bot.services.storage import store_drawing_bytes
from webapp.backend.auth import parse_user, validate_init_data
from webapp.backend.config import settings

router = APIRouter(prefix="/api/drawings", tags=["drawings"])

_bot: Bot | None = None


def _get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=settings.bot_token)
    return _bot


@router.post("")
async def submit_drawing(
    init_data: str = Form(..., alias="initData"),
    session_id: str = Form(..., alias="sessionId"),
    image_base64: str = Form(..., alias="imageBase64"),
):
    data = validate_init_data(init_data, bot_settings.bot_token)
    user = parse_user(data)

    try:
        header, b64 = image_base64.split(",", 1) if "," in image_base64 else ("", image_base64)
        png_bytes = base64.b64decode(b64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid image encoding") from exc

    if len(png_bytes) > 6_000_000:
        raise HTTPException(status_code=413, detail="drawing too large")

    round_number = await session_service.current_round(session_id)
    file_id = await store_drawing_bytes(
        _get_bot(), png_bytes, caption=f"draw:{user.id}:{session_id}:{round_number}"
    )

    result = await session_service.submit_entry(session_id, user.id, file_id, entry_type="drawing")
    if not result.ok:
        raise HTTPException(status_code=409, detail=result.reason)

    if result.round_complete:
        await session_service.maybe_advance_if_complete(session_id)

    return {"ok": True, "file_id": file_id, "round_complete": result.round_complete}
