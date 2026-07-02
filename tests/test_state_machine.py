"""End-to-end simulation of a 3-player Krivoy Telefon session, driven directly against
SessionService (no Telegram/network involved) -- this is the "actually simulate a
3-player run" verification called for in the project spec.

Players: Alice (111), Bob (222), Carol (333). With N=3, max_round = min(N-1, 5) = 2.
Round 0: everyone writes a seed phrase.
Round 1: books rotate by one seat, everyone draws the phrase they were handed.
Round 2: books rotate again, everyone writes a text guess for the drawing they see.
Round 2 is the last round (max_round=2), so after it the session finalizes.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from bot.models import Chain, Entry, Session
from bot.services.session_service import RoundType, round_type_for


ALICE, BOB, CAROL = 111, 222, 333


async def _run_full_lobby(service, chat_id=-100):
    start = await service.start_lobby(chat_id)
    assert start.ok

    for pid, name in [(ALICE, "Alice"), (BOB, "Bob"), (CAROL, "Carol")]:
        joined = await service.join_lobby(chat_id, pid, name, username=name.lower())
        assert joined.ok

    close = await service.close_lobby(chat_id)
    assert close.started
    return close.session_id


@pytest.mark.asyncio
async def test_relay_refuses_second_session_while_active(service):
    chat_id = -200
    first = await service.start_lobby(chat_id)
    assert first.ok

    second = await service.start_lobby(chat_id)
    assert not second.ok
    assert second.reason == "игра уже идёт"


@pytest.mark.asyncio
async def test_lobby_resets_below_minimum_players(service):
    chat_id = -300
    await service.start_lobby(chat_id)
    await service.join_lobby(chat_id, ALICE, "Alice", "alice")
    # only 1 player joined, min_players default is 3

    close = await service.close_lobby(chat_id)
    assert not close.started
    assert close.group_notifications[0].text == "Маловато людей, попробуйте ещё раз"

    # chat state must be cleared so /relay can be retried with no penalty
    state = await service.redis.get(service.k_chat_state(chat_id))
    assert state is None

    retry = await service.start_lobby(chat_id)
    assert retry.ok


@pytest.mark.asyncio
async def test_round_type_alternation():
    assert round_type_for(0) == RoundType.SEED
    assert round_type_for(1) == RoundType.DRAW
    assert round_type_for(2) == RoundType.GUESS
    assert round_type_for(3) == RoundType.DRAW
    assert round_type_for(4) == RoundType.GUESS


@pytest.mark.asyncio
async def test_full_three_player_relay(service):
    chat_id = -400
    sid = await _run_full_lobby(service, chat_id)

    max_round = int(await service.redis.get(service.k_sess_max_round(sid)))
    assert max_round == 2  # min(N-1, 5) = min(2, 5)

    # ---- Round 0: seed phrases ----
    assert await service.current_round(sid) == 0
    seed_phrases = {ALICE: "кот в шляпе", BOB: "летающий бутерброд", CAROL: "динозавр на роликах"}
    last_advance = None
    for pid, phrase in seed_phrases.items():
        result = await service.submit_entry(sid, pid, phrase)
        assert result.ok
        if result.round_complete:
            last_advance = await service.maybe_advance_if_complete(sid)

    assert last_advance is not None
    assert last_advance.finished is False
    assert last_advance.new_round == 1
    assert await service.current_round(sid) == 1

    # ---- Round 1: draw the handed-off phrase ----
    for pid in (ALICE, BOB, CAROL):
        task = await service.get_current_task(sid, pid)
        assert task["type"] == "drawing"
        assert task["prev"]["type"] == "text"
        assert task["prev"]["content"] in seed_phrases.values()

    last_advance = None
    for pid in (ALICE, BOB, CAROL):
        result = await service.submit_entry(sid, pid, f"file_id_drawing_by_{pid}", entry_type="drawing")
        assert result.ok
        if result.round_complete:
            last_advance = await service.maybe_advance_if_complete(sid)

    assert last_advance.new_round == 2
    assert await service.current_round(sid) == 2

    # ---- Round 2 (final round): guess the drawing in text ----
    for pid in (ALICE, BOB, CAROL):
        task = await service.get_current_task(sid, pid)
        assert task["type"] == "text"
        assert task["prev"]["type"] == "drawing"

    last_advance = None
    for pid in (ALICE, BOB, CAROL):
        result = await service.submit_entry(sid, pid, f"guess_by_{pid}")
        assert result.ok
        if result.round_complete:
            last_advance = await service.maybe_advance_if_complete(sid)

    assert last_advance.finished is True
    # 3 chains should each get a finale group notification with a forward button
    assert len(last_advance.group_notifications) == 3
    for gnote in last_advance.group_notifications:
        assert gnote.forward_button_entry_id is not None

    # chat state cleared so a brand new /relay can be started immediately
    state = await service.redis.get(service.k_chat_state(chat_id))
    assert state is None
    restart = await service.start_lobby(chat_id)
    assert restart.ok

    # ---- verify persisted DB state ----
    async with service.session_factory() as db:
        db_session = await db.get(Session, uuid.UUID(sid))
        assert db_session.status == "finished"
        assert db_session.player_count == 3

        chains_res = await db.execute(select(Chain).where(Chain.session_id == uuid.UUID(sid)))
        chains = chains_res.scalars().all()
        assert len(chains) == 3
        for chain in chains:
            assert chain.status == "completed"

            entries_res = await db.execute(
                select(Entry).where(Entry.chain_id == chain.id).order_by(Entry.round_number)
            )
            entries = entries_res.scalars().all()
            # 3 rounds: 0 (seed text), 1 (drawing), 2 (guess text)
            assert [e.round_number for e in entries] == [0, 1, 2]
            assert entries[0].type == "text"
            assert entries[1].type == "drawing"
            assert entries[2].type == "text"
            assert all(not e.was_skipped for e in entries)


@pytest.mark.asyncio
async def test_missed_deadline_marks_was_skipped_and_force_advances(service):
    chat_id = -500
    sid = await _run_full_lobby(service, chat_id)

    # Only Alice and Bob submit their seed phrase; Carol misses the window entirely.
    await service.submit_entry(sid, ALICE, "фраза алисы")
    await service.submit_entry(sid, BOB, "фраза боба")

    # force the deadline into the past and force-advance, as the background poller would
    await service.redis.set(service.k_sess_deadline(sid), 0)
    assert await service.round_deadline_reached(sid)

    advance = await service.advance_round(sid)
    assert advance.finished is False
    assert advance.new_round == 1
    assert CAROL in advance.skipped_players

    async with service.session_factory() as db:
        chains_res = await db.execute(select(Chain).where(Chain.session_id == uuid.UUID(sid)))
        chains = chains_res.scalars().all()
        carol_chain = next(c for c in chains if c.owner_player_id == CAROL)
        entries_res = await db.execute(
            select(Entry).where(Entry.chain_id == carol_chain.id, Entry.round_number == 0)
        )
        carol_round0 = entries_res.scalar_one()
        assert carol_round0.was_skipped is True
        assert carol_round0.content == ""


@pytest.mark.asyncio
async def test_double_submit_rejected(service):
    chat_id = -600
    sid = await _run_full_lobby(service, chat_id)

    first = await service.submit_entry(sid, ALICE, "первая фраза")
    assert first.ok

    second = await service.submit_entry(sid, ALICE, "вторая попытка")
    assert not second.ok
    assert "уже отправил" in second.reason


@pytest.mark.asyncio
async def test_lobby_full_rejects_extra_players(service):
    chat_id = -700
    await service.start_lobby(chat_id)
    for i in range(8):
        result = await service.join_lobby(chat_id, 1000 + i, f"P{i}", None)
        assert result.ok

    overflow = await service.join_lobby(chat_id, 9999, "Overflow", None)
    assert not overflow.ok
