"""Core game state machine for Krivoy Telefon.

All session/round orchestration state lives in Redis under the `kt:` prefix (per the
project spec). Finished content (phrases, drawing file_ids, chain results) is persisted
immediately to Postgres as it's produced, so Redis only ever holds ephemeral
orchestration state and can be safely flushed/expired without losing game history.

This module is deliberately Telegram-agnostic: it never calls the Bot API directly.
Every public method returns plain dataclasses describing what should be sent to whom
("notifications"). A thin adapter in bot/handlers turns those into real aiogram calls.
This makes the entire state machine testable by calling these methods directly and
inspecting the returned notifications -- no live bot token or network needed.
"""
from __future__ import annotations

import json
import random
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

from redis.asyncio import Redis
from sqlalchemy import select, update

from bot.config import settings
from bot.models import Chain, Entry, Player, Session, SessionPlayer

PREFIX = "kt"


class RoundType(str, Enum):
    SEED = "seed"       # round 0: free-text phrase
    DRAW = "drawing"    # odd rounds >=1: draw the phrase/guess you were handed
    GUESS = "text"      # even rounds >=2: guess the drawing in text


def round_type_for(round_number: int) -> RoundType:
    if round_number == 0:
        return RoundType.SEED
    return RoundType.DRAW if round_number % 2 == 1 else RoundType.GUESS


@dataclass
class DirectNotification:
    """A DM to send to one player."""
    player_id: int
    text: str
    file_id: str | None = None  # if set, forward this drawing instead of / alongside text


@dataclass
class GroupNotification:
    """A message to post in the origin group chat."""
    chat_id: int
    text: str
    forward_button_entry_id: str | None = None  # entries.id, if a "forward story" button is needed


@dataclass
class StartLobbyResult:
    ok: bool
    reason: str = ""
    session_id: str | None = None


@dataclass
class JoinResult:
    ok: bool
    reason: str = ""
    player_count: int = 0


@dataclass
class LobbyCloseResult:
    started: bool
    session_id: str | None = None
    notifications: list[DirectNotification] = field(default_factory=list)
    group_notifications: list[GroupNotification] = field(default_factory=list)


@dataclass
class SubmitResult:
    ok: bool
    reason: str = ""
    round_complete: bool = False


@dataclass
class AdvanceResult:
    session_id: str
    finished: bool
    new_round: int | None = None
    notifications: list[DirectNotification] = field(default_factory=list)
    group_notifications: list[GroupNotification] = field(default_factory=list)
    skipped_players: list[int] = field(default_factory=list)


class SessionService:
    def __init__(self, redis: Redis, session_factory):
        self.redis = redis
        self.session_factory = session_factory  # bot.db.get_session (async context manager)

    # ---------- key helpers ----------
    @staticmethod
    def k_chat_state(chat_id: int) -> str:
        return f"{PREFIX}:session:{chat_id}:state"

    @staticmethod
    def k_chat_sid(chat_id: int) -> str:
        return f"{PREFIX}:session:{chat_id}:sid"

    @staticmethod
    def k_lobby_players(chat_id: int) -> str:
        return f"{PREFIX}:lobby:{chat_id}:players"

    @staticmethod
    def k_lobby_names(chat_id: int) -> str:
        return f"{PREFIX}:lobby:{chat_id}:names"

    @staticmethod
    def k_lobby_deadline(chat_id: int) -> str:
        return f"{PREFIX}:lobby:{chat_id}:deadline"

    @staticmethod
    def k_sess_chat(sid: str) -> str:
        return f"{PREFIX}:sess:{sid}:chat_id"

    @staticmethod
    def k_sess_players(sid: str) -> str:
        return f"{PREFIX}:sess:{sid}:players"

    @staticmethod
    def k_sess_names(sid: str) -> str:
        return f"{PREFIX}:sess:{sid}:names"

    @staticmethod
    def k_sess_round(sid: str) -> str:
        return f"{PREFIX}:session:{sid}:round"

    @staticmethod
    def k_sess_deadline(sid: str) -> str:
        return f"{PREFIX}:session:{sid}:deadline"

    @staticmethod
    def k_sess_pending(sid: str) -> str:
        return f"{PREFIX}:session:{sid}:pending"

    @staticmethod
    def k_sess_max_round(sid: str) -> str:
        return f"{PREFIX}:sess:{sid}:max_round"

    ACTIVE_LOBBIES = f"{PREFIX}:active_lobbies"
    ACTIVE_SESSIONS = f"{PREFIX}:active_sessions"

    # ---------- lobby ----------
    async def start_lobby(self, chat_id: int) -> StartLobbyResult:
        state = await self.redis.get(self.k_chat_state(chat_id))
        if state and state.decode() not in ("", "finished"):
            return StartLobbyResult(ok=False, reason="игра уже идёт")

        sid = str(uuid.uuid4())
        async with self.session_factory() as db:
            db.add(Session(id=uuid.UUID(sid), chat_id=chat_id, status="lobby"))

        pipe = self.redis.pipeline()
        pipe.set(self.k_chat_state(chat_id), "lobby")
        pipe.set(self.k_chat_sid(chat_id), sid)
        pipe.delete(self.k_lobby_players(chat_id))
        pipe.delete(self.k_lobby_names(chat_id))
        pipe.set(self.k_lobby_deadline(chat_id), time.time() + settings.lobby_window_seconds)
        pipe.sadd(self.ACTIVE_LOBBIES, chat_id)
        await pipe.execute()
        return StartLobbyResult(ok=True, session_id=sid)

    async def join_lobby(self, chat_id: int, player_id: int, display_name: str, username: str | None) -> JoinResult:
        state = await self.redis.get(self.k_chat_state(chat_id))
        if not state or state.decode() != "lobby":
            return JoinResult(ok=False, reason="Лобби сейчас не открыто.")

        count = await self.redis.scard(self.k_lobby_players(chat_id))
        already_in = await self.redis.sismember(self.k_lobby_players(chat_id), player_id)
        if not already_in and count >= settings.max_players:
            return JoinResult(ok=False, reason="Уже набрали максимум игроков.", player_count=count)

        await self.redis.sadd(self.k_lobby_players(chat_id), player_id)
        await self.redis.hset(self.k_lobby_names(chat_id), str(player_id), display_name)

        await self._upsert_player(player_id, display_name, username)

        new_count = await self.redis.scard(self.k_lobby_players(chat_id))
        return JoinResult(ok=True, player_count=new_count)

    async def _upsert_player(self, player_id: int, display_name: str, username: str | None) -> None:
        async with self.session_factory() as db:
            existing = await db.get(Player, player_id)
            if existing is None:
                db.add(Player(telegram_id=player_id, username=username, display_name=display_name))
            else:
                existing.display_name = display_name
                existing.username = username

    async def lobby_deadline_reached(self, chat_id: int) -> bool:
        deadline = await self.redis.get(self.k_lobby_deadline(chat_id))
        if deadline is None:
            return False
        return time.time() >= float(deadline)

    async def close_lobby(self, chat_id: int) -> LobbyCloseResult:
        """Called when the lobby window elapses. Starts the game if >=min_players,
        otherwise resets so /relay can be tried again with no penalty."""
        sid = await self.redis.get(self.k_chat_sid(chat_id))
        sid = sid.decode() if sid else None
        player_ids = [int(p) for p in await self.redis.smembers(self.k_lobby_players(chat_id))]
        names_raw = await self.redis.hgetall(self.k_lobby_names(chat_id))
        names = {int(k): v.decode() if isinstance(v, bytes) else v for k, v in names_raw.items()}

        await self.redis.srem(self.ACTIVE_LOBBIES, chat_id)

        if len(player_ids) < settings.min_players:
            await self._reset_chat(chat_id)
            async with self.session_factory() as db:
                if sid:
                    await db.execute(
                        update(Session).where(Session.id == uuid.UUID(sid)).values(status="finished")
                    )
            return LobbyCloseResult(
                started=False,
                group_notifications=[
                    GroupNotification(chat_id=chat_id, text="Маловато людей, попробуйте ещё раз")
                ],
            )

        random.shuffle(player_ids)
        return await self._start_session(chat_id, sid, player_ids, names)

    async def _start_session(self, chat_id: int, sid: str, player_ids: list[int], names: dict[int, str]) -> LobbyCloseResult:
        n = len(player_ids)
        max_round = min(n - 1, settings.max_rounds)

        async with self.session_factory() as db:
            db_session = await db.get(Session, uuid.UUID(sid))
            db_session.status = "active"
            db_session.player_count = n
            db_session.started_at = _now()
            for seat, pid in enumerate(player_ids):
                db.add(SessionPlayer(session_id=uuid.UUID(sid), player_id=pid, seat_order=seat))
                db.add(Chain(id=uuid.uuid4(), session_id=uuid.UUID(sid), owner_player_id=pid, status="in_progress"))
                p = await db.get(Player, pid)
                if p:
                    p.games_played = (p.games_played or 0) + 1

        pipe = self.redis.pipeline()
        pipe.set(self.k_chat_state(chat_id), "active")
        pipe.set(self.k_sess_chat(sid), chat_id)
        pipe.set(self.k_sess_players(sid), json.dumps(player_ids))
        pipe.set(self.k_sess_max_round(sid), max_round)
        pipe.set(self.k_sess_round(sid), 0)
        pipe.delete(self.k_sess_names(sid))
        if names:
            pipe.hset(self.k_sess_names(sid), mapping={str(k): v for k, v in names.items()})
        pipe.delete(self.k_sess_pending(sid))
        pipe.sadd(self.k_sess_pending(sid), *player_ids)
        pipe.set(self.k_sess_deadline(sid), time.time() + settings.round_window_seconds)
        pipe.sadd(self.ACTIVE_SESSIONS, sid)
        await pipe.execute()

        notifications = [
            DirectNotification(
                player_id=pid,
                text=(
                    "Игра началась! Придумай любую фразу — с неё начнётся твоя книга "
                    "\"Кривого телефона\". Просто напиши её мне сюда."
                ),
            )
            for pid in player_ids
        ]
        group_notifications = [
            GroupNotification(
                chat_id=chat_id,
                text=f"Игра началась! Участники ({n}): "
                + ", ".join(names.get(pid, str(pid)) for pid in player_ids)
                + f"\nКаждому пишу в личку — жду первые фразы (раунды: {max_round}).",
            )
        ]
        return LobbyCloseResult(started=True, session_id=sid, notifications=notifications, group_notifications=group_notifications)

    async def _reset_chat(self, chat_id: int) -> None:
        pipe = self.redis.pipeline()
        pipe.delete(self.k_chat_state(chat_id))
        pipe.delete(self.k_chat_sid(chat_id))
        pipe.delete(self.k_lobby_players(chat_id))
        pipe.delete(self.k_lobby_names(chat_id))
        pipe.delete(self.k_lobby_deadline(chat_id))
        await pipe.execute()

    # ---------- rounds ----------
    async def get_player_session(self, player_id: int) -> str | None:
        """Find the active session (if any) this player currently belongs to, by
        scanning active sessions' player sets. Fine at this scale (few concurrent games)."""
        sids = await self.redis.smembers(self.ACTIVE_SESSIONS)
        for raw in sids:
            sid = raw.decode() if isinstance(raw, bytes) else raw
            players_raw = await self.redis.get(self.k_sess_players(sid))
            if not players_raw:
                continue
            players = json.loads(players_raw)
            if player_id in players:
                return sid
        return None

    async def current_round(self, sid: str) -> int:
        val = await self.redis.get(self.k_sess_round(sid))
        return int(val) if val is not None else 0

    async def _seat_of(self, sid: str, player_id: int) -> int:
        players_raw = await self.redis.get(self.k_sess_players(sid))
        players = json.loads(players_raw)
        return players.index(player_id)

    async def _chain_id_for_owner_seat(self, sid: str, owner_seat: int) -> uuid.UUID:
        players_raw = await self.redis.get(self.k_sess_players(sid))
        players = json.loads(players_raw)
        owner_id = players[owner_seat]
        async with self.session_factory() as db:
            res = await db.execute(
                select(Chain).where(Chain.session_id == uuid.UUID(sid), Chain.owner_player_id == owner_id)
            )
            chain = res.scalar_one()
            return chain.id

    async def get_current_task(self, sid: str, player_id: int) -> dict | None:
        """What should this player DM-submit right now? Returns a dict with the
        round type and the previous entry's content (the phrase to draw, or the
        drawing file_id to guess), or None for round 0 (free choice)."""
        round_number = await self.current_round(sid)
        rtype = round_type_for(round_number)
        seat = await self._seat_of(sid, player_id)
        n_raw = await self.redis.get(self.k_sess_players(sid))
        n = len(json.loads(n_raw))
        owner_seat = (seat - round_number) % n
        chain_id = await self._chain_id_for_owner_seat(sid, owner_seat)

        if round_number == 0:
            return {"round": 0, "type": rtype.value, "prev": None, "chain_id": str(chain_id)}

        async with self.session_factory() as db:
            res = await db.execute(
                select(Entry).where(Entry.chain_id == chain_id, Entry.round_number == round_number - 1)
            )
            prev = res.scalar_one_or_none()
        return {
            "round": round_number,
            "type": rtype.value,
            "prev": {"type": prev.type, "content": prev.content} if prev else None,
            "chain_id": str(chain_id),
        }

    async def submit_entry(self, sid: str, player_id: int, content: str, entry_type: str | None = None) -> SubmitResult:
        round_number = await self.current_round(sid)
        is_pending = await self.redis.sismember(self.k_sess_pending(sid), player_id)
        if not is_pending:
            return SubmitResult(ok=False, reason="Ты уже отправил(а) ход в этом раунде, жди остальных.")

        rtype = round_type_for(round_number)
        resolved_type = entry_type or ("drawing" if rtype == RoundType.DRAW else "text")

        seat = await self._seat_of(sid, player_id)
        n_raw = await self.redis.get(self.k_sess_players(sid))
        n = len(json.loads(n_raw))
        owner_seat = (seat - round_number) % n
        chain_id = await self._chain_id_for_owner_seat(sid, owner_seat)

        async with self.session_factory() as db:
            db.add(
                Entry(
                    chain_id=chain_id,
                    round_number=round_number,
                    type=resolved_type,
                    author_id=player_id,
                    content=content,
                    was_skipped=False,
                )
            )

        await self.redis.srem(self.k_sess_pending(sid), player_id)
        remaining = await self.redis.scard(self.k_sess_pending(sid))
        return SubmitResult(ok=True, round_complete=remaining == 0)

    async def round_deadline_reached(self, sid: str) -> bool:
        deadline = await self.redis.get(self.k_sess_deadline(sid))
        if deadline is None:
            return False
        return time.time() >= float(deadline)

    async def advance_round(self, sid: str) -> AdvanceResult:
        """Force-advance: mark any still-pending players as skipped, move to the next
        round (or finalize the session if max_round reached)."""
        round_number = await self.current_round(sid)
        max_round = int(await self.redis.get(self.k_sess_max_round(sid)))
        players_raw = await self.redis.get(self.k_sess_players(sid))
        players = json.loads(players_raw)
        n = len(players)

        pending = [int(p) for p in await self.redis.smembers(self.k_sess_pending(sid))]
        for pid in pending:
            seat = players.index(pid)
            owner_seat = (seat - round_number) % n
            chain_id = await self._chain_id_for_owner_seat(sid, owner_seat)
            rtype = round_type_for(round_number)
            resolved_type = "drawing" if rtype == RoundType.DRAW else "text"
            async with self.session_factory() as db:
                db.add(
                    Entry(
                        chain_id=chain_id,
                        round_number=round_number,
                        type=resolved_type,
                        author_id=pid,
                        content="",
                        was_skipped=True,
                    )
                )

        next_round = round_number + 1
        if next_round > max_round:
            return await self._finalize(sid)

        pipe = self.redis.pipeline()
        pipe.set(self.k_sess_round(sid), next_round)
        pipe.delete(self.k_sess_pending(sid))
        pipe.sadd(self.k_sess_pending(sid), *players)
        pipe.set(self.k_sess_deadline(sid), time.time() + settings.round_window_seconds)
        await pipe.execute()

        rtype = round_type_for(next_round)
        names_raw = await self.redis.hgetall(self.k_sess_names(sid))
        names = {int(k): (v.decode() if isinstance(v, bytes) else v) for k, v in names_raw.items()}
        notifications = []
        for pid in players:
            task = await self.get_current_task(sid, pid)
            if rtype == RoundType.DRAW:
                prompt = f"Нарисуй фразу: «{task['prev']['content']}»" if task["prev"] else "Нарисуй что-нибудь!"
            else:
                prompt = "Угадай текстом, что здесь нарисовано, и опиши это фразой." if task["prev"] else ""
            notifications.append(DirectNotification(
                player_id=pid,
                text=prompt,
                file_id=task["prev"]["content"] if task["prev"] and task["prev"]["type"] == "drawing" else None,
            ))

        chat_id_raw = await self.redis.get(self.k_sess_chat(sid))
        chat_id = int(chat_id_raw)
        group_notifications = [
            GroupNotification(chat_id=chat_id, text=f"Раунд {next_round}/{max_round} начался, всем отправлены новые задания в личку.")
        ]

        return AdvanceResult(
            session_id=sid,
            finished=False,
            new_round=next_round,
            notifications=notifications,
            group_notifications=group_notifications,
            skipped_players=pending,
        )

    async def maybe_advance_if_complete(self, sid: str) -> AdvanceResult | None:
        remaining = await self.redis.scard(self.k_sess_pending(sid))
        if remaining == 0:
            return await self.advance_round(sid)
        return None

    async def _finalize(self, sid: str) -> AdvanceResult:
        chat_id_raw = await self.redis.get(self.k_sess_chat(sid))
        chat_id = int(chat_id_raw)

        group_notifications = []
        async with self.session_factory() as db:
            res = await db.execute(select(Chain).where(Chain.session_id == uuid.UUID(sid)))
            chains = res.scalars().all()
            for chain in chains:
                entries_res = await db.execute(
                    select(Entry).where(Entry.chain_id == chain.id).order_by(Entry.round_number)
                )
                entries = entries_res.scalars().all()
                owner = await db.get(Player, chain.owner_player_id)
                owner_name = owner.display_name if owner else str(chain.owner_player_id)
                lines = [f"Книга: {owner_name}"]
                for e in entries:
                    if e.was_skipped:
                        lines.append(f"Раунд {e.round_number}: (пропущено)")
                    elif e.type == "text":
                        lines.append(f"Раунд {e.round_number} (текст): {e.content}")
                    else:
                        lines.append(f"Раунд {e.round_number} (рисунок): [file_id={e.content}]")
                chain.status = "completed"
                owner.chains_completed = (owner.chains_completed or 0) + 1
                group_notifications.append(
                    GroupNotification(chat_id=chat_id, text="\n".join(lines), forward_button_entry_id=str(chain.id))
                )

            db_session = await db.get(Session, uuid.UUID(sid))
            db_session.status = "finished"
            db_session.finished_at = _now()

        await self.redis.srem(self.ACTIVE_SESSIONS, sid)
        await self._reset_chat(chat_id)

        return AdvanceResult(session_id=sid, finished=True, group_notifications=group_notifications)


def _now():
    import datetime

    return datetime.datetime.now(datetime.timezone.utc)
