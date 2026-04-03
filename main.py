import asyncio
import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()

from database.db import database, init_db
from bot.main import dp, bot
from bot.scheduler import setup_scheduler
from web.server import app, set_bot


async def run_bot():
    """Run the Telegram bot polling."""
    try:
        print("🤖 Bot starting...")
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Bot error: {e}")
        raise


async def run_web():
    """Run the FastAPI web server."""
    try:
        port = int(os.getenv("PORT", 8080))
        print(f"🌐 Web server starting on port {port}...")
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    except Exception as e:
        print(f"❌ Web server error: {e}")
        raise


async def main():
    """Initialize database and start both bot and web server."""
    print("=" * 60)
    print("🚀 Initializing database...")
    await database.connect()
    await init_db()
    set_bot(bot)
    setup_scheduler(bot)
    print("✅ Database initialized")
    print("=" * 60)

    # Create tasks for both bot and web server
    bot_task = asyncio.create_task(run_bot())
    web_task = asyncio.create_task(run_web())

    print("🎯 Both services starting...")

    # Wait for either task to complete (usually web server runs indefinitely)
    try:
        await asyncio.gather(bot_task, web_task)
    except KeyboardInterrupt:
        print("\n⏹️  Shutting down...")
        bot_task.cancel()
        web_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
