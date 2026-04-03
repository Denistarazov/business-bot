import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from dotenv import load_dotenv
from database.db import init_db, add_user, add_booking, get_all_bookings, get_user_bookings

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ─── FSM States ───────────────────────────────────────────────────────────────

class BookingStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_confirmation = State()


# Temporary in-memory storage for booking flow
booking_data: dict = {}


# ─── Keyboards ────────────────────────────────────────────────────────────────

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Our services"), KeyboardButton(text="📞 Contacts")],
        [KeyboardButton(text="⭐ Reviews"),       KeyboardButton(text="📍 Location")],
        [KeyboardButton(text="🗂 My bookings"),   KeyboardButton(text="ℹ️ About us")],
    ],
    resize_keyboard=True
)

services_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💇 Haircut — $20",           callback_data="svc_haircut")],
        [InlineKeyboardButton(text="🧔 Beard trim — $15",        callback_data="svc_beard")],
        [InlineKeyboardButton(text="💈 Haircut + Beard — $30",   callback_data="svc_combo")],
        [InlineKeyboardButton(text="🧴 Hair treatment — $25",    callback_data="svc_treatment")],
        [InlineKeyboardButton(text="👑 VIP Full service — $60",  callback_data="svc_vip")],
    ]
)

phone_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Share my phone number", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)

SERVICES = {
    "svc_haircut":   "💇 Haircut — $20",
    "svc_beard":     "🧔 Beard trim — $15",
    "svc_combo":     "💈 Haircut + Beard — $30",
    "svc_treatment": "🧴 Hair treatment — $25",
    "svc_vip":       "👑 VIP Full service — $60",
}

STATUS_EMOJI = {
    "pending":      "🟡",
    "done":         "✅",
    "cancelled":    "❌",
    "rescheduled":  "📅",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Confirm booking", callback_data="confirm_booking"),
        InlineKeyboardButton(text="❌ Cancel",          callback_data="cancel_booking"),
    ]])


# ─── /start ───────────────────────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await add_user(
        telegram_id=message.from_user.id,
        first_name=message.from_user.first_name,
        username=message.from_user.username or ""
    )
    await message.answer(
        f"👋 Welcome, *{message.from_user.first_name}*!\n\n"
        "💈 *Elite Barbershop* — your premium grooming destination.\n\n"
        "📍 123 Main Street, New York\n"
        "🕐 Mon–Sat: 9:00 – 20:00\n\n"
        "Use the menu below to book a visit or learn more about us:",
        reply_markup=main_menu,
        parse_mode="Markdown"
    )


# ─── Menu buttons ─────────────────────────────────────────────────────────────

@dp.message(F.text == "📋 Our services")
async def show_services(message: Message):
    await message.answer(
        "✂️ *Our services:*\n\nChoose a service to book:",
        reply_markup=services_menu,
        parse_mode="Markdown"
    )


@dp.message(F.text == "📞 Contacts")
async def show_contacts(message: Message):
    await message.answer(
        "📞 *Contact us:*\n\n"
        "📱 Phone: +1 234 567 89\n"
        "📧 Email: barbershop@email.com\n"
        "📍 Address: 123 Main Street, New York\n"
        "🕐 Mon–Sat: 9:00 – 20:00\n"
        "🌐 Instagram: @elitebarbershop",
        parse_mode="Markdown"
    )


@dp.message(F.text == "⭐ Reviews")
async def show_reviews(message: Message):
    await message.answer(
        "⭐ *What our clients say:*\n\n"
        "⭐⭐⭐⭐⭐ *John M.*\n_Amazing work! Best haircut I've had in years._\n\n"
        "⭐⭐⭐⭐⭐ *Mike R.*\n_Friendly staff, great atmosphere, will be back!_\n\n"
        "⭐⭐⭐⭐⭐ *David K.*\n_Highly professional. Totally recommend!_\n\n"
        "⭐⭐⭐⭐⭐ *Alex T.*\n_The VIP service is worth every penny._",
        parse_mode="Markdown"
    )


@dp.message(F.text == "📍 Location")
async def show_location(message: Message):
    await message.answer("📍 *We are here:*\n123 Main Street, New York", parse_mode="Markdown")
    await message.answer_location(latitude=40.7128, longitude=-74.0060)


@dp.message(F.text == "ℹ️ About us")
async def show_about(message: Message):
    await message.answer(
        "💈 *Elite Barbershop*\n\n"
        "We've been in business since 2015, serving thousands of satisfied clients.\n\n"
        "Our team of professional barbers combines modern techniques with classic style "
        "to give you the perfect look every time.\n\n"
        "🏆 Awards:\n"
        "• Best Barbershop NYC 2022\n"
        "• Top Rated on Google ⭐ 4.9/5\n\n"
        "Book your visit today! 👇",
        reply_markup=services_menu,
        parse_mode="Markdown"
    )


@dp.message(F.text == "🗂 My bookings")
async def show_my_bookings(message: Message):
    bookings = await get_user_bookings(message.from_user.id)
    if not bookings:
        await message.answer(
            "You have no bookings yet.\n\nTap *📋 Our services* to book your first visit! 💈",
            parse_mode="Markdown"
        )
        return

    text = "🗂 *Your bookings:*\n\n"
    for b in bookings:
        emoji = STATUS_EMOJI.get(b[5], "🟡")
        text += f"{emoji} *{b[3]}*\n"
        text += f"   Status: _{b[5]}_\n"
        if b[6]:
            text += f"   Scheduled: _{b[6]}_\n"
        if b[7]:
            text += f"   Note: _{b[7]}_\n"
        text += f"   Booked: _{b[8][:16]}_\n\n"

    await message.answer(text, parse_mode="Markdown")


# ─── Service selection ────────────────────────────────────────────────────────

@dp.callback_query(F.data.in_(SERVICES.keys()))
async def service_selected(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    service = SERVICES[callback.data]
    booking_data[callback.from_user.id] = {"service": service}
    await state.set_state(BookingStates.waiting_for_phone)
    await callback.message.answer(
        f"✅ You selected: *{service}*\n\n"
        "📱 Please share your phone number so we can confirm your booking.\n"
        "_You can also type it manually._",
        reply_markup=phone_keyboard,
        parse_mode="Markdown"
    )


# ─── Phone collection ─────────────────────────────────────────────────────────

async def process_phone(message: Message, state: FSMContext, phone: str):
    user_id = message.from_user.id
    if user_id not in booking_data:
        await state.clear()
        await message.answer("Something went wrong. Please start again.", reply_markup=main_menu)
        return

    booking_data[user_id]["phone"] = phone
    service = booking_data[user_id]["service"]

    await state.set_state(BookingStates.waiting_for_confirmation)
    await message.answer(
        "📋 *Booking summary:*\n\n"
        f"💇 Service: *{service}*\n"
        f"📱 Phone: *{phone}*\n\n"
        "Please confirm your booking:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    await message.answer("👇 Confirm or cancel:", reply_markup=confirm_keyboard())


@dp.message(BookingStates.waiting_for_phone, F.contact)
async def phone_shared(message: Message, state: FSMContext):
    await process_phone(message, state, message.contact.phone_number)


@dp.message(BookingStates.waiting_for_phone, F.text)
async def phone_typed(message: Message, state: FSMContext):
    await process_phone(message, state, message.text)


# ─── Booking confirmation ─────────────────────────────────────────────────────

@dp.callback_query(F.data == "confirm_booking")
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id

    if user_id not in booking_data:
        await state.clear()
        await callback.message.answer("Something went wrong. Please try again.", reply_markup=main_menu)
        return

    data = booking_data.pop(user_id)
    await add_booking(user_id=user_id, service=data["service"], phone=data.get("phone", ""))
    await state.clear()

    await callback.message.answer(
        "🎉 *Booking confirmed!*\n\n"
        f"💇 *{data['service']}*\n\n"
        "Our team will contact you shortly to confirm the exact time.\n\n"
        "📞 Or call us directly: *+1 234 567 89*\n"
        "💈 See you soon!",
        reply_markup=main_menu,
        parse_mode="Markdown"
    )


@dp.callback_query(F.data == "cancel_booking")
async def cancel_booking(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    booking_data.pop(callback.from_user.id, None)
    await state.clear()
    await callback.message.answer(
        "❌ Booking cancelled.\n\nNo worries — you can book anytime! 💈",
        reply_markup=main_menu
    )


# ─── Admin command ────────────────────────────────────────────────────────────

@dp.message(Command("bookings"))
async def admin_bookings(message: Message):
    bookings = await get_all_bookings()
    if not bookings:
        await message.answer("No bookings yet.")
        return

    text = "📋 *All bookings:*\n\n"
    for b in bookings:
        emoji = STATUS_EMOJI.get(b[5], "🟡")
        text += (
            f"{emoji} *{b[3]}*\n"
            f"   👤 {b[1]} (@{b[2] or 'no username'})\n"
            f"   📱 {b[4] or 'no phone'}\n"
            f"   Status: _{b[5]}_\n"
        )
        if b[6]:
            text += f"   Scheduled: _{b[6]}_\n"
        text += f"   🕐 _{b[8][:16]}_\n\n"

    await message.answer(text, parse_mode="Markdown")


# ─── Entry point ──────────────────────────────────────────────────────────────

async def main():
    await init_db()
    print("Bot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
