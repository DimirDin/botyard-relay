"""initial krivoy_telefon_schema tables

Revision ID: 0001
Revises:
Create Date: 2026-07-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "krivoy_telefon_schema"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    op.create_table(
        "players",
        sa.Column("telegram_id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("games_played", sa.Integer(), server_default="0"),
        sa.Column("chains_completed", sa.Integer(), server_default="0"),
        sa.Column("first_seen", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema=SCHEMA,
    )

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="lobby"),
        sa.Column("player_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_index("ix_sessions_chat_id", "sessions", ["chat_id"], schema=SCHEMA)

    op.create_table(
        "session_players",
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.sessions.id"),
            primary_key=True,
        ),
        sa.Column(
            "player_id",
            sa.BigInteger(),
            sa.ForeignKey(f"{SCHEMA}.players.telegram_id"),
            primary_key=True,
        ),
        sa.Column("seat_order", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema=SCHEMA,
    )

    op.create_table(
        "chains",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.sessions.id")),
        sa.Column("owner_player_id", sa.BigInteger(), sa.ForeignKey(f"{SCHEMA}.players.telegram_id")),
        sa.Column("status", sa.Text(), server_default="in_progress"),
        schema=SCHEMA,
    )

    op.create_table(
        "entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chain_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.chains.id")),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("author_id", sa.BigInteger(), sa.ForeignKey(f"{SCHEMA}.players.telegram_id")),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("was_skipped", sa.Boolean(), server_default=sa.false()),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("chain_id", "round_number", name="uq_entry_chain_round"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("entries", schema=SCHEMA)
    op.drop_table("chains", schema=SCHEMA)
    op.drop_table("session_players", schema=SCHEMA)
    op.drop_index("ix_sessions_chat_id", table_name="sessions", schema=SCHEMA)
    op.drop_table("sessions", schema=SCHEMA)
    op.drop_table("players", schema=SCHEMA)
