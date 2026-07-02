"""Process-wide singletons: Redis client + SessionService, shared by handlers and the
background scheduler."""
from __future__ import annotations

from redis.asyncio import Redis

from bot.config import settings
from bot.db import get_session
from bot.services.session_service import SessionService

redis_client = Redis.from_url(settings.redis_url)
session_service = SessionService(redis=redis_client, session_factory=get_session)
