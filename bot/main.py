import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dotenv import load_dotenv
from database.db import init_db, add_user, add_booking, get_all_bookings

# Load token from .env file
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Create bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Reply keyboard
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Our services"), KeyboardButton(text="📞 Contacts")],
        [KeyboardButton(text="⭐ Reviews"), KeyboardButton(text="📍 Location")]
    ],
    resize_keyboard=True
)

# Inline keyboard
services_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💇 Haircut — $20", callback_data="service_haircut")],
        [InlineKeyboardButton(text="🧔 Beard trim — $15", callback_data="service_beard")],
        [InlineKeyboardButton(text="📅 Book now", callback_data="service_book")]
    ]
)

# /start command — saves user to database
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await add_user(
        telegram_id=message.from_user.id,
        first_name=message.from_user.first_name,
        username=message.from_user.username or ""
    )
    await message.answer(
        f"Hello, {message.from_user.first_name}! 👋\nWelcome to our barbershop bot!",
        reply_markup=main_menu
    )

# Services button
@dp.message(F.text == "📋 Our services")
async def show_services(message: Message):
    await message.answer("Choose a service:", reply_markup=services_menu)

# Contacts button
@dp.message(F.text == "📞 Contacts")
async def show_contacts(message: Message):
    await message.answer("📞 Phone: +1 234 567 89\n📧 Email: barbershop@email.com")

# Reviews button
@dp.message(F.text == "⭐ Reviews")
async def show_reviews(message: Message):
    await message.answer("⭐⭐⭐⭐⭐ Great place!\n— John\n\n⭐⭐⭐⭐⭐ Best haircut ever!\n— Mike")

# Location button
@dp.message(F.text == "📍 Location")
async def show_location(message: Message):
    await message.answer("📍 123 Main Street, New York")

# Inline button handlers
@dp.callback_query(F.data == "service_haircut")
async def haircut_callback(callback: CallbackQuery):
    await callback.answer()
    await add_booking(user_id=callback.from_user.id, service="Haircut — $20")
    await callback.message.answer("✅ Haircut booked! We will contact you soon.")

@dp.callback_query(F.data == "service_beard")
async def beard_callback(callback: CallbackQuery):
    await callback.answer()
    await add_booking(user_id=callback.from_user.id, service="Beard trim — $15")
    await callback.message.answer("✅ Beard trim booked! We will contact you soon.")

@dp.callback_query(F.data == "service_book")
async def book_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("To book, please call: +1 234 567 89 📞")

# /bookings command — show all bookings
@dp.message(Command("bookings"))
async def show_bookings(message: Message):
    bookings = await get_all_bookings()
    if not bookings:
        await message.answer("No bookings yet.")
        return
    text = "📋 All bookings:\n\n"
    for b in bookings:
        text += f"👤 {b[0]} (@{b[1]})\n💇 {b[2]}\n📌 Status: {b[3]}\n🕐 {b[4]}\n\n"
    await message.answer(text)

# Start bot
async def main():
    await init_db()
    print("Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
