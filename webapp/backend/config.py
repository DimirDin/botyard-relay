from __future__ import annotations

import os


class BackendSettings:
    bot_token: str = os.environ.get("BOT_TOKEN", "")
    storage_channel_id: str = os.environ.get("STORAGE_CHANNEL_ID", "")
    redis_host: str = os.environ.get("REDIS_HOST", "localhost")
    redis_port: int = int(os.environ.get("REDIS_PORT", "6379"))
    redis_db: int = int(os.environ.get("REDIS_DB", "0"))
    redis_password: str = os.environ.get("REDIS_PASSWORD", "")
    db_host: str = os.environ.get("DB_HOST", "localhost")
    db_port: int = int(os.environ.get("DB_PORT", "5432"))
    db_name: str = os.environ.get("DB_NAME", "botyard_relay")
    db_user: str = os.environ.get("DB_USER", "botyard")
    db_password: str = os.environ.get("DB_PASSWORD", "botyard")
    cors_origins: list[str] = os.environ.get("CORS_ORIGINS", "*").split(",")

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


settings = BackendSettings()
