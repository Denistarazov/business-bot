# Project: Business Bot

## Stack
- Telegram bot: aiogram 3.x, FSM states
- Web API: FastAPI + uvicorn, JWT auth
- DB: SQLite (dev) / PostgreSQL (prod) via `databases` + aiosqlite/asyncpg
- Deploy: Railway.app, Procfile: `web: python main.py`

## Architecture
- `main.py` — entry point, runs uvicorn only
- `web/server.py` — FastAPI app with lifespan (starts bot as asyncio task)
- `bot/main.py` — aiogram bot, dp + bot objects, FSM handlers
- `bot/scheduler.py` — APScheduler for reminders
- `database/db.py` — all DB queries, init_db() with safe migrations

## Key Patterns
- Bot starts inside FastAPI lifespan as `asyncio.create_task()`
- DB migrations use PRAGMA table_info() for SQLite, information_schema for PostgreSQL
- Auth: JWT tokens, roles: admin / superadmin
- Default admin: admin / admin123 (created in init_db if no admins)

## Env Variables
- BOT_TOKEN, SECRET_KEY, DATABASE_URL, PORT, BOT_USERNAME

## Common Issues Fixed
- `no such column` — use PRAGMA to check before ALTER TABLE
- Bot not starting — must use lifespan, NOT asyncio.gather from main.py
- Railway: single service runs both bot + web via lifespan
