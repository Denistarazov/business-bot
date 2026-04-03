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
    print("🤖 Bot is running...")
    await dp.start_polling(bot)


async def run_web():
    port = int(os.getenv("PORT", 8080))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    await database.connect()
    await init_db()
    set_bot(bot)
    setup_scheduler(bot)
    print("🚀 Starting bot + web server...")
    await asyncio.gather(run_bot(), run_web())


if __name__ == "__main__":
    asyncio.run(main())
