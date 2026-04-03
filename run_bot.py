"""
Run the Telegram bot locally (not on Railway).
Usage: python run_bot.py
"""
import asyncio
from dotenv import load_dotenv

load_dotenv()

from database.db import database, init_db
from bot.main import dp, bot
from bot.scheduler import setup_scheduler
from web.server import set_bot


async def main():
    """Initialize database and start bot polling."""
    print("=" * 60)
    print("🚀 Initializing database...")
    await database.connect()
    await init_db()
    set_bot(bot)
    setup_scheduler(bot)
    print("✅ Database initialized")
    print("=" * 60)
    print("🤖 Bot starting (polling Telegram)...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
