# PROJECT_CONTEXT.md — Кривой телефон (botyard-relay)

This file exists so a future session (human or agent) doesn't need to be re-briefed.
It mirrors the format used by sibling bots on the botyard platform.

## What this is

A Telegram bot + Mini App implementing a Gartic-Phone/Telestrations-style group
drawing-and-guessing relay game. Technical repo/subdomain name is "relay"
(`relay.botyard.site`); the bot presents itself to users as **"Кривой телефон"**.

It leans on Telegram's native **group chat** primitive — unlike most 2026-era
mini-apps (solo-clicker or 1v1), this game requires 3-8 people in the same chat.

## Game loop

1. `/relay` in a group -> inline "Я в деле" button -> 60-90s lobby window.
   - <3 players at window end: "Маловато людей, попробуйте ещё раз", lobby resets, no penalty.
   - Already-active session in that chat: refuses with "игра уже идёт".
2. **Round 0 (seed)**: bot DMs every joined player to write a free-text phrase in
   parallel. This is the player's own "book".
3. **Rounds 1..K**: every round, every book shifts to the next player (cyclic shift by
   1 seat). Task type alternates: odd rounds = draw the phrase/guess you were handed,
   even rounds (>=2) = guess the drawing in text. 60-90s per round; anyone who misses
   it gets `was_skipped=true` and the book moves on anyway.
   `K = min(N-1, 5)` — hard cap of 5 handoffs regardless of group size.
4. **Finale**: each finished book is posted to the group as a chain-card
   (phrase -> drawing -> phrase -> drawing...) with a "Переслать историю" button.

## Architecture

- **Bot** (`bot/`): aiogram 3. Owns group commands, lobby, deep-link to DM, and BOTH
  text-entry steps (writing a phrase / guessing a drawing) as plain DM messages — no
  Mini App needed for text steps.
- **Mini App** (`webapp/frontend/`): React 18 + Vite. ONLY used for the draw step —
  a canvas with pointer-event handling ("Скетчбук" design, see below).
- **Backend** (`webapp/backend/`): FastAPI. Receives finished drawings from the Mini
  App, validates Telegram `initData` via real HMAC verification
  (`webapp/backend/auth.py`), forwards the image to the storage channel, and calls into
  the same `SessionService` the bot uses to advance game state.
- **Session/round state**: Redis, key prefix `kt:`. See "Redis key map" below.
  A background asyncio task (`bot/scheduler.py: DeadlinePoller`) polls every
  `DEADLINE_POLL_INTERVAL` seconds (default 7s) for overdue lobby/round deadlines and
  force-advances them, marking any missing entries `was_skipped=true`.
- **Persistent results**: Postgres, schema `krivoy_telefon_schema`
  (`bot/models.py`, Alembic migrations in `migrations/`).

## Why the state machine is Telegram-agnostic

`bot/services/session_service.py` (`SessionService`) never calls the Bot API directly.
Every public method returns `DirectNotification` / `GroupNotification` dataclasses
describing what should be sent to whom. Thin adapters
(`bot/scheduler.py`, `bot/handlers/dm.py`, `webapp/backend/routes/drawings.py`) turn
those into real aiogram calls. This is what let us write `tests/test_state_machine.py`
— a full 3-player lobby->rounds->finale simulation — without any live bot token,
network, or mocked Telegram client. Run it with `pytest tests/ -v`; it uses `fakeredis`
+ an in-memory SQLite DB (schema-translated from `krivoy_telefon_schema` via
SQLAlchemy's `schema_translate_map`, since SQLite has no real Postgres schemas).

## Redis key map (prefix `kt:`)

Global:
- `kt:active_lobbies` — set of chat_ids currently collecting players
- `kt:active_sessions` — set of session ids currently mid-game

Per chat:
- `kt:session:{chat_id}:state` — `""` / `lobby` / `active` (cleared on finish, NOT
  left as `finished`, so a fresh `/relay` works immediately)
- `kt:session:{chat_id}:sid` — current session id while lobby/active
- `kt:lobby:{chat_id}:players` / `:names` / `:deadline` — lobby collection state

Per session (`sid`):
- `kt:sess:{sid}:chat_id`, `:players` (seat-ordered JSON list), `:names`, `:max_round`
- `kt:session:{sid}:round` — current round number (0 = seed)
- `kt:session:{sid}:deadline` — unix timestamp for the current round's cutoff
- `kt:session:{sid}:pending` — set of player_ids who still owe this round's submission

Book/chain assignment is computed, not stored per-round: chain `i` is owned by seat
`i`; at round `r` it's held by seat `(i + r) % N`. Given a submitting player's seat
`s` and the current round `r`, their chain's owner seat is `(s - r) % N`.

## Database schema (`krivoy_telefon_schema`)

Exactly as specified: `players`, `sessions`, `session_players`, `chains`, `entries`.
See `bot/models.py` / `migrations/versions/0001_initial_schema.py`. UUID columns use a
custom cross-dialect `GUID` TypeDecorator (Postgres native UUID in prod, CHAR(32) under
SQLite in tests) — this is a testability shim, not a schema change; the deployed
Postgres columns are real `uuid`.

## Drawing storage: Telegram-as-CDN (deliberate, not a shortcut)

We do **not** run our own object storage. Every finished drawing gets forwarded to a
private internal Telegram channel/chat configured via `STORAGE_CHANNEL_ID`
(`bot/services/storage.py`), and only the resulting Telegram `file_id` is stored in
`entries.content`. Telegram is a free, already-durable, CDN-backed store for exactly
this shape of data (small images, referenced by opaque id, re-servable forever by
`file_id`). This keeps the whole stack to "bot + backend + Postgres + Redis" with zero
S3/MinIO/etc to operate.

## initData validation

`webapp/backend/auth.py: validate_init_data()` implements the documented Telegram Mini
App HMAC-SHA256 check (`secret = HMAC_SHA256("WebAppData", bot_token)`, then
`HMAC_SHA256(secret, data_check_string)` compared against the provided `hash`). This is
enforced on every `/api/drawings` POST before anything is trusted or persisted.

## Deep-link first contact

Bots cannot DM someone who has never opened a chat with them. The lobby join button
also nudges players toward `t.me/<bot_username>?start=hello` if the proactive DM fails
silently (the try/except in `bot/handlers/lobby.py:cb_join`). In practice, for the
in-group flow, players are told once to open a DM before/while joining.

## Moderation

`bot/services/moderation.py` runs a basic profanity filter (Russian + English root
list, leetspeak-normalized) on every free-text phrase/guess submission before it's
accepted, in both the DM path (`bot/handlers/dm.py`) — drawings are explicitly NOT
moderated yet; that's a documented future phase, not an oversight.

## Design language: "Скетчбук" (Sketchbook)

Implemented in `webapp/frontend/src/styles.css` / `App.tsx` / `DrawingCanvas.tsx`:
- Paper background: muted beige-gray ruled/grid notebook look, not pure white
  (`--paper-bg: #ece7da`, repeating linear-gradient ruled lines).
- Torn-paper cards: irregular `clip-path` polygon edges (not `border-radius`), each
  card gets a random-ish `--tilt` rotation (1-2deg) via inline CSS var.
- Fonts: "Caveat"/"Kalam" (Google Fonts) for headings/names (`.handwritten`), "Kalam"
  as the body sans too (kept the notebook feel consistent).
- Palette: bright marker/highlighter colors (`--marker-pink #ff2d78`,
  `--marker-yellow`, `--marker-green`, `--marker-blue`, `--marker-orange`,
  `--marker-purple`). Explicitly avoids terracotta/dark-olive (reserved for a
  different botyard channel's branding).
- Reveal animation: `.reveal-stroke` does an SVG `stroke-dashoffset` draw-on over
  0.8s, meant for the finale chain-card drawing reveals (not "pop in instantly").
- Respects `env(safe-area-inset-top, 44px)` / bottom via CSS vars in `:root`.
- No `display:contents` + animation combo used anywhere (platform hard rule).
- `tg.openInvoice()` isn't used yet (no MVP monetization needs it), but if it ever is,
  call it with an 80ms delay per platform convention — noted here for whoever adds it.

## Build phases (status)

- **Phase 1 — text-only MVP (state machine)**: DONE and verified. `/relay` ->
  lobby -> seed -> rotating rounds -> finale, fully backed by Redis+Postgres, proven by
  `tests/test_state_machine.py` (7 tests: refuse-double-session, lobby-too-few-resets,
  round-type alternation, full 3-player run to finale w/ DB assertions,
  missed-deadline force-advance marks `was_skipped`, duplicate-submit rejection,
  8-player lobby cap).
- **Phase 2 — Mini App draw step**: DONE. Canvas (`webapp/frontend/src/DrawingCanvas.tsx`)
  with pointer events + palette + line width, alternating round types wired through
  `SessionService`/`round_type_for()`, `initData` HMAC validation
  (`webapp/backend/auth.py`), Telegram-channel storage flow
  (`bot/services/storage.py`, `webapp/backend/routes/drawings.py`). A DM-photo fallback
  path also exists (`bot/handlers/dm.py: dm_photo`) for players who'd rather just send
  a photo instead of using the canvas.
- **Phase 3 — Stars monetization (stub, minimal by design)**:
  `bot/handlers/monetization.py` — `/shop` sends an `XTR`-currency invoice for a
  "themed starter phrase pack"; pre-checkout auto-approves; successful-payment handler
  acknowledges but doesn't unlock anything real yet. Not wired into the game loop.
  "Early replay" payload is defined but has no cooldown mechanic to shorten (none
  exists yet), so it's pure plumbing.
- **Phase 4 — history/leaderboard (minimal)**: `/mystats` and `/leaders` bot commands
  (`bot/handlers/leaderboard.py`) plus an equivalent HTTP endpoint
  (`webapp/backend/routes/leaderboard.py: GET /api/leaderboard`), both reading
  `players.games_played` / `players.chains_completed`.

## What's stubbed / explicitly out of scope

- Drawing content moderation (documented, not implemented — profanity filter only
  covers text).
- Stars monetization doesn't unlock any real perk yet (see Phase 3 above).
- No rate limiting / anti-spam beyond the profanity filter and the one-submission-per-
  round guard.
- No retry/backoff around Telegram API calls in the scheduler beyond a bare
  try/except-and-log (`bot/scheduler.py`).
- Frontend has no automated tests (manual `npm run build` type-checks + bundles
  cleanly; canvas interaction was not run against a real device).

## Running locally

See `README.md` for the full walkthrough. Short version:

```
cp .env.example .env   # fill in BOT_TOKEN at minimum for a real run
docker compose up --build
```

For state-machine-only verification with no Docker/Telegram/Postgres at all:

```
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
PYTHONPATH=. BOT_TOKEN=test pytest tests/ -v
```

Note: the SQLAlchemy `Mapped[str | None]` style annotations used throughout
`bot/models.py` require Python 3.10+ at runtime (SQLAlchemy 2.0 resolves them via
`typing.get_type_hints`). The Docker image uses `python:3.11-slim`. Locally, use
Python 3.10+ (this repo was developed/tested against 3.12) — plain 3.9 will fail with
`ArgumentError: Could not resolve all types within mapped annotation`.
