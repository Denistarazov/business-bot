import asyncio
import os
import threading
import uvicorn
from dotenv import load_dotenv

load_dotenv()

from database.db import database, init_db
from bot.main import dp, bot
from bot.scheduler import setup_scheduler
from web.server import app, set_bot


async def run_bot():
    """Run the Telegram bot polling."""
    print("🤖 Bot is running...")
    await dp.start_polling(bot)


def run_web_sync():
    """Run uvicorn in a sync context."""
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


async def main():
    """Initialize database and start both bot and web server."""
    await database.connect()
    await init_db()
    set_bot(bot)
    setup_scheduler(bot)
    print("🚀 Starting bot + web server...")

    # Start web server in a separate thread (it blocks)
    web_thread = threading.Thread(target=run_web_sync, daemon=True)
    web_thread.start()

    # Give web server time to start
    await asyncio.sleep(1)

    # Run bot in main event loop
    await run_bot()


if __name__ == "__main__":
    asyncio.run(main())
