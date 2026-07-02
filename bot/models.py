"""SQLAlchemy ORM models mirroring the krivoy_telefon_schema Postgres schema."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    Text,
    TypeDecorator,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

SCHEMA = "krivoy_telefon_schema"


class GUID(TypeDecorator):
    """Platform-independent UUID type: uses Postgres' native UUID in production, and a
    plain CHAR(32) in dialects without UUID support (e.g. SQLite, used only in tests)."""

    impl = CHAR
    cache_ok = True

    def __init__(self, as_uuid: bool = True, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        return value.hex

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


UUID = GUID


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "players"
    __table_args__ = {"schema": SCHEMA}

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    chains_completed: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[datetime] = mapped_column(server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="lobby")  # lobby | active | finished
    player_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)

    players: Mapped[list["SessionPlayer"]] = relationship(back_populates="session")
    chains: Mapped[list["Chain"]] = relationship(back_populates="session")


class SessionPlayer(Base):
    __tablename__ = "session_players"
    __table_args__ = {"schema": SCHEMA}

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.sessions.id"), primary_key=True
    )
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(f"{SCHEMA}.players.telegram_id"), primary_key=True
    )
    seat_order: Mapped[int] = mapped_column(Integer, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(server_default=func.now())

    session: Mapped["Session"] = relationship(back_populates="players")


class Chain(Base):
    __tablename__ = "chains"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.sessions.id"))
    owner_player_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(f"{SCHEMA}.players.telegram_id"))
    status: Mapped[str] = mapped_column(Text, default="in_progress")  # in_progress | completed

    session: Mapped["Session"] = relationship(back_populates="chains")
    entries: Mapped[list["Entry"]] = relationship(back_populates="chain", order_by="Entry.round_number")


class Entry(Base):
    __tablename__ = "entries"
    __table_args__ = (
        UniqueConstraint("chain_id", "round_number", name="uq_entry_chain_round"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chain_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.chains.id"))
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)  # text | drawing
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(f"{SCHEMA}.players.telegram_id"))
    content: Mapped[str] = mapped_column(Text, nullable=False)  # free text or Telegram file_id
    was_skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime] = mapped_column(server_default=func.now())

    chain: Mapped["Chain"] = relationship(back_populates="entries")
