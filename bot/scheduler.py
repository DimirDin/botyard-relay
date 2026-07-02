"""Background asyncio task that polls Redis for overdue lobby/round deadlines and
force-advances them, per the spec: 'a background asyncio task polls every 5-10s for
overdue deadlines and force-advances the round, marking any missing entries
was_skipped=true'.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from bot.config import settings
from bot.services.session_service import SessionService

logger = logging.getLogger(__name__)


class DeadlinePoller:
    def __init__(self, bot: Bot, service: SessionService):
        self.bot = bot
        self.service = service
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self.tick()
            except Exception:
                logger.exception("deadline poller tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=settings.deadline_poll_interval)
            except asyncio.TimeoutError:
                pass

    async def tick(self) -> None:
        redis = self.service.redis

        lobby_chats = [int(c) for c in await redis.smembers(SessionService.ACTIVE_LOBBIES)]
        for chat_id in lobby_chats:
            if await self.service.lobby_deadline_reached(chat_id):
                result = await self.service.close_lobby(chat_id)
                await self._dispatch_lobby_close(result)

        session_ids = [s.decode() if isinstance(s, bytes) else s for s in await redis.smembers(SessionService.ACTIVE_SESSIONS)]
        for sid in session_ids:
            if await self.service.round_deadline_reached(sid):
                result = await self.service.advance_round(sid)
                await self._dispatch_advance(result)

    async def _dispatch_lobby_close(self, result) -> None:
        for note in result.notifications:
            await self._safe_send_dm(note)
        for gnote in result.group_notifications:
            await self._safe_send_group(gnote)

    async def _dispatch_advance(self, result) -> None:
        for note in result.notifications:
            await self._safe_send_dm(note)
        for gnote in result.group_notifications:
            await self._safe_send_group(gnote)

    async def _safe_send_dm(self, note) -> None:
        try:
            if note.file_id:
                await self.bot.send_photo(note.player_id, note.file_id, caption=note.text)
            else:
                await self.bot.send_message(note.player_id, note.text)
        except Exception:
            logger.warning("failed to DM player %s", note.player_id, exc_info=True)

    async def _safe_send_group(self, gnote) -> None:
        from bot.keyboards import forward_story_keyboard

        try:
            kb = forward_story_keyboard(gnote.forward_button_entry_id) if gnote.forward_button_entry_id else None
            await self.bot.send_message(gnote.chat_id, gnote.text, reply_markup=kb)
        except Exception:
            logger.warning("failed to post to chat %s", gnote.chat_id, exc_info=True)
