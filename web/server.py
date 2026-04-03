import asyncio
import datetime
import hashlib
import hmac
import os
import re
from typing import Optional

import jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database.db import (
    add_admin, delete_admin, get_admin_by_telegram_id, get_admin_by_username,
    get_all_admins, get_all_bookings, get_all_user_ids, get_booking_user_id,
    get_stats_by_day, get_stats_by_service, get_users_count,
    init_db, link_telegram_id, update_booking, verify_password, database,
)

# ── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY   = os.getenv("SECRET_KEY",   "change-this-secret-in-production")
BOT_TOKEN    = os.getenv("BOT_TOKEN",    "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")
ALGORITHM    = "HS256"

# Import bot directly to avoid set_bot timing issues
try:
    from bot.main import bot as _bot
except Exception:
    _bot = None


def set_bot(bot):
    global _bot
    _bot = bot


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Business Bot API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()


# ── Auth helpers ──────────────────────────────────────────────────────────────
def create_token(username: str, role: str) -> str:
    return jwt.encode(
        {"sub": username, "role": role,
         "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)},
        SECRET_KEY, algorithm=ALGORITHM,
    )


def verify_token(creds: HTTPAuthorizationCredentials = Depends(security)):
    try:
        return jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


def require_superadmin(payload=Depends(verify_token)):
    if payload.get("role") != "superadmin":
        raise HTTPException(403, "Superadmin access required")
    return payload


# ── Pydantic models ───────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


class UpdateBookingRequest(BaseModel):
    status: str
    scheduled_date: Optional[str] = None
    notes: Optional[str] = None


class AddAdminRequest(BaseModel):
    username: str
    password: str
    role: str = "admin"


class BroadcastRequest(BaseModel):
    message: str


class TelegramAuthRequest(BaseModel):
    id: int
    first_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


# ── Startup / shutdown ────────────────────────────────────────────────────────
@app.on_event("shutdown")
async def shutdown():
    try:
        await database.disconnect()
    except Exception:
        pass


# ── Public ────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    index = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"status": "ok", "version": "3.0.0"}


@app.get("/config")
async def config():
    return {"bot_username": BOT_USERNAME}


@app.post("/login")
async def login(req: LoginRequest):
    admin = await get_admin_by_username(req.username)
    if not admin or not verify_password(req.password, admin["password_hash"]):
        raise HTTPException(401, "Invalid username or password")
    token = create_token(admin["username"], admin["role"])
    return {"token": token, "username": admin["username"], "role": admin["role"]}


@app.post("/auth/telegram")
async def telegram_auth(req: TelegramAuthRequest):
    """Verify Telegram Login Widget data and issue JWT."""
    if not BOT_TOKEN:
        raise HTTPException(503, "Telegram auth not configured")

    # Verify hash
    data = {k: v for k, v in req.dict().items() if k != "hash" and v is not None}
    check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hashlib.sha256(BOT_TOKEN.encode()).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, req.hash):
        raise HTTPException(401, "Invalid Telegram auth data")

    # Check expiry (1 day)
    if datetime.datetime.utcnow().timestamp() - req.auth_date > 86400:
        raise HTTPException(401, "Auth data expired")

    admin = await get_admin_by_telegram_id(req.id)
    if not admin:
        raise HTTPException(403, "This Telegram account is not linked to any admin")

    token = create_token(admin["username"], admin["role"])
    return {"token": token, "username": admin["username"], "role": admin["role"]}


# ── Bookings ──────────────────────────────────────────────────────────────────
@app.get("/bookings")
async def get_bookings(payload=Depends(verify_token)):
    rows = await get_all_bookings()
    return [
        {
            "id":             r["id"],
            "name":           r["first_name"],
            "username":       r["username"],
            "service":        r["service"],
            "phone":          r["phone"],
            "status":         r["status"],
            "booking_date":   r["booking_date"],
            "booking_time":   r["booking_time"],
            "scheduled_date": r["scheduled_date"],
            "notes":          r["notes"],
            "created_at":     str(r["created_at"]),
        }
        for r in rows
    ]


@app.put("/bookings/{booking_id}")
async def update_booking_endpoint(
    booking_id: int,
    req: UpdateBookingRequest,
    payload=Depends(verify_token),
):
    await update_booking(booking_id, req.status, req.scheduled_date, req.notes)

    # Notify user via bot
    if _bot:
        uid = await get_booking_user_id(booking_id)
        if uid:
            try:
                msgs = {
                    "done":        "✅ Your booking has been *completed*! Thank you for visiting us. 💈",
                    "cancelled":   "❌ Your booking has been *cancelled*.\n📞 Call us: +1 234 567 89",
                    "rescheduled": f"📅 Your booking has been *rescheduled* to: *{req.scheduled_date or 'TBD'}*",
                    "pending":     "🟡 Your booking is *pending* review. We'll contact you soon!",
                }
                msg = msgs.get(req.status, f"📋 Booking status updated: *{req.status}*")
                if req.notes:
                    msg += f"\n\n📝 *Note:* {req.notes}"
                await _bot.send_message(uid, msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Notification failed for {uid}: {e}")

    return {"success": True}


# ── Statistics ────────────────────────────────────────────────────────────────
@app.get("/stats")
async def get_stats(payload=Depends(verify_token)):
    by_day     = await get_stats_by_day(30)
    by_service = await get_stats_by_service()
    users_count = await get_users_count()

    # Revenue: extract $ price from service name
    def extract_price(service: str) -> float:
        m = re.search(r"\$(\d+)", service)
        return float(m.group(1)) if m else 0

    all_bookings = await get_all_bookings()
    total_revenue = sum(extract_price(b["service"]) for b in all_bookings)
    done_revenue  = sum(extract_price(b["service"]) for b in all_bookings if b["status"] == "done")

    return {
        "by_day":        [{"day": str(r["day"]), "count": r["count"]} for r in by_day],
        "by_service":    [{"service": r["service"], "count": r["count"]} for r in by_service],
        "users_count":   users_count,
        "total_revenue": total_revenue,
        "done_revenue":  done_revenue,
    }


# ── Broadcast ─────────────────────────────────────────────────────────────────
@app.post("/broadcast")
async def broadcast(req: BroadcastRequest, payload=Depends(verify_token)):
    if not _bot:
        raise HTTPException(503, "Bot not available")

    user_ids = await get_all_user_ids()
    sent = failed = 0

    for uid in user_ids:
        try:
            await _bot.send_message(uid, req.message, parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.05)  # Telegram rate limit
        except Exception:
            failed += 1

    return {"sent": sent, "failed": failed, "total": len(user_ids)}


# ── Admins ────────────────────────────────────────────────────────────────────
@app.get("/admins")
async def list_admins(payload=Depends(require_superadmin)):
    rows = await get_all_admins()
    return [
        {"id": r["id"], "username": r["username"], "role": r["role"],
         "telegram_id": r["telegram_id"], "created_at": str(r["created_at"])}
        for r in rows
    ]


@app.post("/admins")
async def create_admin(req: AddAdminRequest, payload=Depends(require_superadmin)):
    try:
        await add_admin(req.username, req.password, req.role)
        return {"success": True}
    except Exception:
        raise HTTPException(400, "Username already exists")


@app.delete("/admins/{admin_id}")
async def remove_admin(admin_id: int, payload=Depends(require_superadmin)):
    await delete_admin(admin_id)
    return {"success": True}


@app.post("/admins/{admin_id}/link-telegram")
async def link_admin_telegram(
    admin_id: int,
    req: TelegramAuthRequest,
    payload=Depends(require_superadmin),
):
    """Link a Telegram account to an admin."""
    await link_telegram_id(admin_id, req.id)
    return {"success": True}
