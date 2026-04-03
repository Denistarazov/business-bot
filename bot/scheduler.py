"""
Background scheduler — sends reminders 24h before bookings.
"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database.db import get_bookings_for_reminder, mark_reminder_sent

scheduler = AsyncIOScheduler(timezone="UTC")
_bot = None


def setup_scheduler(bot_instance):
    global _bot
    _bot = bot_instance
    scheduler.add_job(send_reminders, "interval", hours=1, id="reminders", replace_existing=True)
    scheduler.start()
    print("⏰ Reminder scheduler started")


async def send_reminders():
    if not _bot:
        return
    bookings = await get_bookings_for_reminder()
    for b in bookings:
        try:
            time_str = b["booking_time"] or "your scheduled time"
            msg = (
                f"⏰ *Reminder!*\n\n"
                f"You have a booking *tomorrow*:\n"
                f"💇 {b['service']}\n"
                f"🕐 {time_str}\n\n"
                f"📍 123 Main Street, New York\n"
                f"📞 +1 234 567 89\n\n"
                f"See you soon! 💈"
            )
            await _bot.send_message(b["user_id"], msg, parse_mode="Markdown")
            await mark_reminder_sent(b["id"])
            await asyncio.sleep(0.05)  # avoid Telegram rate limits
        except Exception as e:
            print(f"Reminder failed for user {b['user_id']}: {e}")
