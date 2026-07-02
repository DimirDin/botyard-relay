from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import settings
from bot.deps import redis_client, session_service
from bot.handlers import build_root_router
from bot.scheduler import DeadlinePoller

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(build_root_router())

    poller = DeadlinePoller(bot, session_service)
    poller.start()

    try:
        await dp.start_polling(bot)
    finally:
        await poller.stop()
        await redis_client.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
