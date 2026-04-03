import asyncio
import datetime
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, KeyboardButton, Message,
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, ReplyKeyboardRemove,
)
from dotenv import load_dotenv

from database.db import (
    add_booking, add_user, get_all_bookings,
    get_available_slots, get_user_bookings, init_db,
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()


# ── FSM States ────────────────────────────────────────────────────────────────
class BookingStates(StatesGroup):
    waiting_for_date         = State()
    waiting_for_time         = State()
    waiting_for_phone        = State()
    waiting_for_confirmation = State()


booking_data: dict = {}  # temporary storage during booking flow

# ── Service catalogue ─────────────────────────────────────────────────────────
SERVICES = {
    "svc_haircut":   "💇 Haircut — $20",
    "svc_beard":     "🧔 Beard trim — $15",
    "svc_combo":     "💈 Haircut + Beard — $30",
    "svc_treatment": "🧴 Hair treatment — $25",
    "svc_vip":       "👑 VIP Full service — $60",
}

STATUS_EMOJI = {
    "pending":     "🟡",
    "done":        "✅",
    "cancelled":   "❌",
    "rescheduled": "📅",
}

# ── Static keyboards ──────────────────────────────────────────────────────────
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Our services"), KeyboardButton(text="📞 Contacts")],
        [KeyboardButton(text="⭐ Reviews"),       KeyboardButton(text="📍 Location")],
        [KeyboardButton(text="🗂 My bookings"),   KeyboardButton(text="ℹ️ About us")],
    ],
    resize_keyboard=True,
)

services_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=key)]
        for key, name in SERVICES.items()
    ]
)

phone_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Share my phone number", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)


# ── Dynamic keyboards ─────────────────────────────────────────────────────────
def date_keyboard() -> InlineKeyboardMarkup:
    """Next 7 working days (skip Sunday)."""
    buttons = []
    day = datetime.date.today() + datetime.timedelta(days=1)
    count = 0
    while count < 7:
        if day.weekday() != 6:  # skip Sunday
            label = day.strftime("%a %d %b")
            buttons.append([InlineKeyboardButton(text=label, callback_data=f"date_{day.isoformat()}")])
            count += 1
        day += datetime.timedelta(days=1)
    buttons.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_booking")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def time_keyboard(date: str) -> InlineKeyboardMarkup | None:
    """Available time slots for a given date."""
    slots = await get_available_slots(date)
    if not slots:
        return None
    row, buttons = [], []
    for slot in slots:
        row.append(InlineKeyboardButton(text=slot, callback_data=f"time_{slot}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([
        InlineKeyboardButton(text="⬅️ Back",    callback_data="back_to_date"),
        InlineKeyboardButton(text="❌ Cancel",  callback_data="cancel_booking"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Confirm", callback_data="confirm_booking"),
        InlineKeyboardButton(text="❌ Cancel",  callback_data="cancel_booking"),
    ]])


# ── /start ────────────────────────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    booking_data.pop(message.from_user.id, None)
    await add_user(
        telegram_id=message.from_user.id,
        first_name=message.from_user.first_name,
        username=message.from_user.username or "",
    )
    await message.answer(
        f"👋 Welcome, *{message.from_user.first_name}*!\n\n"
        "💈 *Elite Barbershop* — your premium grooming destination.\n\n"
        "📍 123 Main Street, New York\n"
        "🕐 Mon–Sat: 9:00 – 19:00\n\n"
        "Use the menu below to book your visit:",
        reply_markup=main_menu,
        parse_mode="Markdown",
    )


# ── Info buttons ──────────────────────────────────────────────────────────────
@dp.message(F.text == "📋 Our services")
async def show_services(message: Message):
    await message.answer(
        "✂️ *Our services:*\n\nTap a service to start booking:",
        reply_markup=services_menu,
        parse_mode="Markdown",
    )


@dp.message(F.text == "📞 Contacts")
async def show_contacts(message: Message):
    await message.answer(
        "📞 *Contact us:*\n\n"
        "📱 Phone: +1 234 567 89\n"
        "📧 Email: barbershop@email.com\n"
        "📍 Address: 123 Main Street, New York\n"
        "🕐 Mon–Sat: 9:00 – 19:00\n"
        "📸 Instagram: @elitebarbershop",
        parse_mode="Markdown",
    )


@dp.message(F.text == "⭐ Reviews")
async def show_reviews(message: Message):
    await message.answer(
        "⭐ *What our clients say:*\n\n"
        "⭐⭐⭐⭐⭐ *John M.*\n_Best haircut I've ever had!_\n\n"
        "⭐⭐⭐⭐⭐ *Mike R.*\n_Friendly staff, great atmosphere._\n\n"
        "⭐⭐⭐⭐⭐ *David K.*\n_Totally professional. Will be back!_\n\n"
        "⭐⭐⭐⭐⭐ *Alex T.*\n_The VIP service is worth every penny._",
        parse_mode="Markdown",
    )


@dp.message(F.text == "📍 Location")
async def show_location(message: Message):
    await message.answer("📍 *We are here:*\n123 Main Street, New York", parse_mode="Markdown")
    await message.answer_location(latitude=40.7128, longitude=-74.0060)


@dp.message(F.text == "ℹ️ About us")
async def show_about(message: Message):
    await message.answer(
        "💈 *Elite Barbershop*\n\n"
        "Serving our community since 2015 with premium grooming services.\n\n"
        "🏆 *Awards:*\n"
        "• Best Barbershop NYC 2022\n"
        "• Google Rating ⭐ 4.9/5\n\n"
        "Book your visit now! 👇",
        reply_markup=services_menu,
        parse_mode="Markdown",
    )


@dp.message(F.text == "🗂 My bookings")
async def show_my_bookings(message: Message):
    bookings = await get_user_bookings(message.from_user.id)
    if not bookings:
        await message.answer(
            "You have no bookings yet.\n\nTap *📋 Our services* to book your first visit! 💈",
            parse_mode="Markdown",
        )
        return

    text = "🗂 *Your bookings:*\n\n"
    for b in bookings:
        emoji = STATUS_EMOJI.get(b["status"], "🟡")
        text += f"{emoji} *{b['service']}*\n"
        if b["booking_date"]:
            text += f"   📅 {b['booking_date']} at {b['booking_time'] or '—'}\n"
        text += f"   Status: _{b['status']}_\n"
        if b["notes"]:
            text += f"   Note: _{b['notes']}_\n"
        text += "\n"

    await message.answer(text, parse_mode="Markdown")


# ── Step 1: Service selected ──────────────────────────────────────────────────
@dp.callback_query(F.data.in_(SERVICES.keys()))
async def service_selected(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    service = SERVICES[callback.data]
    booking_data[callback.from_user.id] = {"service": service}
    await state.set_state(BookingStates.waiting_for_date)
    await callback.message.answer(
        f"✅ *{service}*\n\n📅 Choose a date for your visit:",
        reply_markup=date_keyboard(),
        parse_mode="Markdown",
    )


# ── Step 2: Date selected ─────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("date_"))
async def date_selected(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    date = callback.data.replace("date_", "")
    booking_data[callback.from_user.id]["date"] = date

    kb = await time_keyboard(date)
    if not kb:
        await callback.message.answer(
            f"😔 No available slots for *{date}*.\nPlease choose another date:",
            reply_markup=date_keyboard(),
            parse_mode="Markdown",
        )
        return

    await state.set_state(BookingStates.waiting_for_time)
    formatted = datetime.date.fromisoformat(date).strftime("%A, %d %B")
    await callback.message.answer(
        f"📅 *{formatted}*\n\n🕐 Choose a time slot:",
        reply_markup=kb,
        parse_mode="Markdown",
    )


# ── Back to date ──────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "back_to_date")
async def back_to_date(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(BookingStates.waiting_for_date)
    await callback.message.answer("📅 Choose a date:", reply_markup=date_keyboard())


# ── Step 3: Time selected ─────────────────────────────────────────────────────
@dp.callback_query(F.data.startswith("time_"))
async def time_selected(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    time = callback.data.replace("time_", "")
    booking_data[callback.from_user.id]["time"] = time
    await state.set_state(BookingStates.waiting_for_phone)
    await callback.message.answer(
        f"🕐 *{time}* — great!\n\n"
        "📱 Please share your phone number so we can confirm your booking.\n"
        "_You can also type it manually._",
        reply_markup=phone_keyboard,
        parse_mode="Markdown",
    )


# ── Step 4: Phone ─────────────────────────────────────────────────────────────
async def _process_phone(message: Message, state: FSMContext, phone: str):
    uid = message.from_user.id
    if uid not in booking_data:
        await state.clear()
        await message.answer("Something went wrong. Please start again.", reply_markup=main_menu)
        return
    booking_data[uid]["phone"] = phone
    d = booking_data[uid]
    date_fmt = datetime.date.fromisoformat(d["date"]).strftime("%A, %d %B")
    await state.set_state(BookingStates.waiting_for_confirmation)
    await message.answer(
        "📋 *Booking summary:*\n\n"
        f"💇 *{d['service']}*\n"
        f"📅 {date_fmt} at {d['time']}\n"
        f"📱 {phone}\n\n"
        "Confirm your booking?",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    await message.answer("👇", reply_markup=confirm_keyboard())


@dp.message(BookingStates.waiting_for_phone, F.contact)
async def phone_shared(message: Message, state: FSMContext):
    await _process_phone(message, state, message.contact.phone_number)


@dp.message(BookingStates.waiting_for_phone, F.text)
async def phone_typed(message: Message, state: FSMContext):
    await _process_phone(message, state, message.text)


# ── Step 5: Confirm ───────────────────────────────────────────────────────────
@dp.callback_query(F.data == "confirm_booking")
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    uid = callback.from_user.id
    if uid not in booking_data:
        await state.clear()
        await callback.message.answer("Something went wrong. Please try again.", reply_markup=main_menu)
        return

    d = booking_data.pop(uid)
    await add_booking(
        user_id=uid,
        service=d["service"],
        phone=d.get("phone", ""),
        booking_date=d.get("date"),
        booking_time=d.get("time"),
    )
    await state.clear()

    date_fmt = datetime.date.fromisoformat(d["date"]).strftime("%A, %d %B")
    await callback.message.answer(
        "🎉 *Booking confirmed!*\n\n"
        f"💇 *{d['service']}*\n"
        f"📅 {date_fmt} at {d['time']}\n\n"
        "We will send you a reminder the day before.\n"
        "📞 Questions? Call us: *+1 234 567 89*\n\n"
        "See you soon! 💈",
        reply_markup=main_menu,
        parse_mode="Markdown",
    )


# ── Cancel ────────────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "cancel_booking")
async def cancel_booking(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    booking_data.pop(callback.from_user.id, None)
    await state.clear()
    await callback.message.answer(
        "❌ Booking cancelled.\n\nFeel free to book again anytime! 💈",
        reply_markup=main_menu,
    )


# ── Admin: /bookings ──────────────────────────────────────────────────────────
@dp.message(Command("bookings"))
async def admin_bookings(message: Message):
    bookings = await get_all_bookings()
    if not bookings:
        await message.answer("No bookings yet.")
        return

    text = "📋 *All bookings:*\n\n"
    for b in bookings:
        emoji = STATUS_EMOJI.get(b["status"], "🟡")
        text += (
            f"{emoji} *{b['service']}*\n"
            f"   👤 {b['first_name']} (@{b['username'] or '—'})\n"
            f"   📱 {b['phone'] or '—'}\n"
        )
        if b["booking_date"]:
            text += f"   📅 {b['booking_date']} {b['booking_time'] or ''}\n"
        text += f"   Status: _{b['status']}_\n\n"

    await message.answer(text, parse_mode="Markdown")


# ── Entry point ───────────────────────────────────────────────────────────────
async def main():
    from database.db import database
    await database.connect()
    await init_db()
    print("🤖 Bot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
