"""Central configuration for the Krivoy Telefon bot, loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str | None = None, required: bool = False) -> str:
    val = os.environ.get(name, default)
    if required and not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val or ""


@dataclass
class Settings:
    bot_token: str = field(default_factory=lambda: _env("BOT_TOKEN"))
    bot_username: str = field(default_factory=lambda: _env("BOT_USERNAME", "krivoy_telefon_bot"))

    redis_host: str = field(default_factory=lambda: _env("REDIS_HOST", "localhost"))
    redis_port: int = field(default_factory=lambda: int(_env("REDIS_PORT", "6379")))
    redis_db: int = field(default_factory=lambda: int(_env("REDIS_DB", "0")))
    redis_password: str = field(default_factory=lambda: _env("REDIS_PASSWORD", ""))

    db_host: str = field(default_factory=lambda: _env("DB_HOST", "localhost"))
    db_port: int = field(default_factory=lambda: int(_env("DB_PORT", "5432")))
    db_name: str = field(default_factory=lambda: _env("DB_NAME", "botyard_relay"))
    db_user: str = field(default_factory=lambda: _env("DB_USER", "botyard"))
    db_password: str = field(default_factory=lambda: _env("DB_PASSWORD", "botyard"))

    storage_channel_id: str = field(default_factory=lambda: _env("STORAGE_CHANNEL_ID", ""))

    webapp_url: str = field(default_factory=lambda: _env("WEBAPP_URL", "https://relay.botyard.site"))
    backend_internal_url: str = field(default_factory=lambda: _env("BACKEND_INTERNAL_URL", "http://backend:3013"))

    min_players: int = field(default_factory=lambda: int(_env("MIN_PLAYERS", "3")))
    max_players: int = field(default_factory=lambda: int(_env("MAX_PLAYERS", "8")))
    max_rounds: int = field(default_factory=lambda: int(_env("MAX_ROUNDS", "5")))
    lobby_window_seconds: int = field(default_factory=lambda: int(_env("LOBBY_WINDOW_SECONDS", "75")))
    round_window_seconds: int = field(default_factory=lambda: int(_env("ROUND_WINDOW_SECONDS", "75")))
    deadline_poll_interval: int = field(default_factory=lambda: int(_env("DEADLINE_POLL_INTERVAL", "7")))

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


settings = Settings()
