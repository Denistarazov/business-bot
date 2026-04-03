import asyncio
import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()

from bot.main import dp, bot
from database.db import init_db
from web.server import app, set_bot


async def run_bot():
    print("Bot is running...")
    await dp.start_polling(bot)


async def run_web():
    port = int(os.getenv("PORT", 8080))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    await init_db()
    set_bot(bot)  # Give web server access to bot for notifications
    await asyncio.gather(run_bot(), run_web())


if __name__ == "__main__":
    asyncio.run(main())
