"""Drawing storage via the "Telegram-as-CDN" trick.

We do not run our own object storage. Every finished drawing (submitted either through
the Mini App canvas as a PNG upload, or later forwarded from the DM chat) gets sent to a
private internal Telegram channel/chat (STORAGE_CHANNEL_ID). Telegram assigns that upload
a permanent `file_id`/`file_unique_id`, which we store in `entries.content`. Telegram is
free, already-durable, CDN-backed storage for exactly this shape of data -- reusing it
here is a deliberate architectural choice, not a shortcut (see PROJECT_CONTEXT.md).
"""
from __future__ import annotations

from aiogram import Bot
from aiogram.types import BufferedInputFile

from bot.config import settings


async def store_drawing_bytes(bot: Bot, png_bytes: bytes, caption: str = "") -> str:
    """Uploads drawing bytes to the storage channel and returns the resulting file_id."""
    if not settings.storage_channel_id:
        raise RuntimeError("STORAGE_CHANNEL_ID is not configured")
    message = await bot.send_photo(
        chat_id=settings.storage_channel_id,
        photo=BufferedInputFile(png_bytes, filename="drawing.png"),
        caption=caption,
    )
    return message.photo[-1].file_id


async def relay_drawing_file_id(bot: Bot, source_file_id: str, caption: str = "") -> str:
    """Re-uploads an existing Telegram file (e.g. a photo sent directly in DM as a
    fallback drawing method) into the storage channel, returning the new stable file_id."""
    if not settings.storage_channel_id:
        raise RuntimeError("STORAGE_CHANNEL_ID is not configured")
    message = await bot.send_photo(
        chat_id=settings.storage_channel_id,
        photo=source_file_id,
        caption=caption,
    )
    return message.photo[-1].file_id
