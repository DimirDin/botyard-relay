"""Test harness: an in-memory SQLite DB (schema-translated from krivoy_telefon_schema)
and a fakeredis client, wired into a real SessionService instance -- so the state
machine tests exercise the exact same code that runs in production, with no live
Postgres/Redis/Telegram required."""
from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.models import SCHEMA, Base


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        execution_options={"schema_translate_map": {SCHEMA: None}},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine):
    maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)

    @asynccontextmanager
    async def factory():
        async with maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return factory


@pytest_asyncio.fixture
async def fake_redis():
    import fakeredis.aioredis

    redis = fakeredis.aioredis.FakeRedis()
    yield redis
    await redis.aclose()


@pytest_asyncio.fixture
async def service(fake_redis, session_factory):
    from bot.services.session_service import SessionService

    return SessionService(redis=fake_redis, session_factory=session_factory)
