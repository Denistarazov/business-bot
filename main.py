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
        print("🤖 Bot started. Listening for messages...")
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Bot error: {e}")
        raise


async def run_web():
    """Run the FastAPI web server."""
    try:
        port = int(os.getenv("PORT", 8080))
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    except Exception as e:
        print(f"❌ Web server error: {e}")
        raise


async def main():
    """Initialize database and start both bot and web server on Railway."""
    print("=" * 70)
    print("🚀 STARTING BUSINESS BOT + WEB SERVER")
    print("=" * 70)

    # Initialize database
    print("📦 Connecting to database...")
    await database.connect()
    await init_db()
    print("✅ Database connected and initialized")

    # Setup bot
    set_bot(bot)
    setup_scheduler(bot)
    print("✅ Bot configured")

    port = int(os.getenv("PORT", 8080))
    print(f"✅ Web server will run on port {port}")
    print("=" * 70)

    # Run both bot and web server concurrently
    print("🎯 Starting both services...")
    try:
        await asyncio.gather(run_bot(), run_web())
    except KeyboardInterrupt:
        print("\n⏹️  Shutdown signal received")


if __name__ == "__main__":
    asyncio.run(main())
