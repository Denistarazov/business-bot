import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv

# Load token from .env file
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Create bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Handler for /start command
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(f"Hello, {message.from_user.first_name}! 👋\nI am a business bot. How can I help you?")

# Handler for /help command
@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Available commands:\n"
        "/start — start the bot\n"
        "/help — list of commands"
    )

# Handler for all text messages
@dp.message(F.text)
async def echo(message: Message):
    await message.answer(f"You wrote: {message.text}")

# Start bot
async def main():
    print("Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())