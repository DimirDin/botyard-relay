# Кривой телефон (botyard-relay)

Telegram group-chat drawing-and-guessing relay game. See `PROJECT_CONTEXT.md` for the
full design/architecture writeup.

## Local development

### 1. State machine only (no Docker, no bot token needed)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
PYTHONPATH=. BOT_TOKEN=test pytest tests/ -v
```

This runs `tests/test_state_machine.py`, including a full simulated 3-player game
(lobby -> seed -> draw round -> guess round -> finale) against `fakeredis` + an
in-memory SQLite DB, with real DB assertions on the persisted chains/entries.

Requires Python 3.10+ (SQLAlchemy 2.0's `Mapped[...]` annotations need it). Tested with
3.12.

### 2. Full stack via Docker Compose

```bash
cp .env.example .env
# edit .env: at minimum set BOT_TOKEN (from @BotFather) and STORAGE_CHANNEL_ID
# (id of a private channel/group the bot is an admin of, used as drawing storage)
docker compose up --build
```

This starts, in order: `db` (Postgres), `redis`, `migrate` (runs Alembic migrations
once and exits), then `bot` (aiogram long-polling) and `web` (FastAPI + built Mini App,
exposed on `127.0.0.1:3013`).

To rerun migrations manually: `docker compose run --rm migrate`.

### 3. Mini App frontend dev loop

```bash
cd webapp/frontend
npm install
npm run dev       # local dev server on :5173
npm run build     # production build into dist/, served by the FastAPI backend
```

The Mini App only handles the "draw" step — it's opened via a `web_app` inline button
with `?sid=<session_id>&round=<n>` query params, reads Telegram `initData` from
`window.Telegram.WebApp`, and POSTs the finished PNG (base64) plus `initData` to
`POST /api/drawings`.

## Verifying the pieces

- **State machine**: `pytest tests/ -v` (see above) — this is the "actually simulate a
  3-player run" verification called for by the project spec.
- **initData validation**: `webapp/backend/auth.py:validate_init_data` implements the
  documented Telegram HMAC-SHA256 check; `webapp/backend/routes/drawings.py` calls it
  on every submission before trusting anything.
- **Drawing storage flow**: canvas PNG -> `POST /api/drawings` -> HMAC validated ->
  `bot/services/storage.py:store_drawing_bytes` uploads to `STORAGE_CHANNEL_ID` ->
  resulting `file_id` passed into `SessionService.submit_entry` -> persisted in
  `entries.content`.
- **Docker boot**: `docker compose up --build` should bring up all 4 services cleanly
  from a filled-in `.env` (not run in this sandbox — no Docker daemon available here;
  verified instead by running the bot/backend modules directly with `python -c "import
  bot.main"` / `import webapp.backend.main`, which both import cleanly, and by
  hand-inspecting the Dockerfile/compose file for the standard build/run problems).

## Commands

- `/relay` (group chat) — start a lobby
- `/mystats` (anywhere) — your games played / chains completed
- `/leaders` (anywhere) — top 10 by chains completed
- `/shop` (Phase 3 stub) — Telegram Stars invoice for a "themed starter phrase pack"
  (payment plumbing only; doesn't unlock anything yet)

## Repo layout

```
bot/                    aiogram 3 bot: lobby, DM handlers, state machine, scheduler
  services/
    session_service.py  the Redis+Postgres game state machine (Telegram-agnostic)
    storage.py          Telegram-as-CDN drawing storage
    moderation.py        profanity filter
webapp/
  backend/              FastAPI: initData validation, drawing intake, leaderboard API
  frontend/              React 18 + Vite Mini App (canvas draw step, "Скетчбук" design)
migrations/              Alembic migrations for krivoy_telefon_schema
tests/                   pytest state-machine simulation (fakeredis + sqlite)
docker-compose.yml, Dockerfile, .env.example, .github/workflows/deploy.yml
```
