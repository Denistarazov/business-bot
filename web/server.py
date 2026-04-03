import os
import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt

from database.db import (
    get_all_bookings, init_db,
    get_admin_by_username, add_admin, get_all_admins, delete_admin,
    update_booking, get_booking_user_id,
    verify_password
)

# ─── Config ───────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-in-production-please")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

# Global bot instance (set from main.py)
_bot = None


def set_bot(bot):
    global _bot
    _bot = bot


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="Business Bot API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def create_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=TOKEN_EXPIRE_HOURS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired, please login again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_superadmin(payload=Depends(verify_token)):
    if payload.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return payload


# ─── Request models ───────────────────────────────────────────────────────────

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


# ─── Startup ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    await init_db()


# ─── Public endpoints ─────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "ok", "message": "Business Bot API is running", "version": "2.0.0"}


@app.post("/login")
async def login(request: LoginRequest):
    admin = await get_admin_by_username(request.username)
    if not admin or not verify_password(request.password, admin[2]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(admin[1], admin[3])
    return {
        "token": token,
        "username": admin[1],
        "role": admin[3]
    }


# ─── Protected: Bookings ──────────────────────────────────────────────────────

@app.get("/bookings")
async def get_bookings(payload=Depends(verify_token)):
    data = await get_all_bookings()
    return [
        {
            "id": b[0],
            "name": b[1],
            "username": b[2],
            "service": b[3],
            "phone": b[4],
            "status": b[5],
            "scheduled_date": b[6],
            "notes": b[7],
            "created_at": b[8],
        }
        for b in data
    ]


@app.put("/bookings/{booking_id}")
async def update_booking_endpoint(
    booking_id: int,
    request: UpdateBookingRequest,
    payload=Depends(verify_token)
):
    await update_booking(booking_id, request.status, request.scheduled_date, request.notes)

    # Notify user via Telegram bot
    if _bot:
        user_id = await get_booking_user_id(booking_id)
        if user_id:
            try:
                status_messages = {
                    "done": "✅ Your booking has been *completed*! Thank you for visiting us. We look forward to seeing you again! 💈",
                    "cancelled": "❌ Your booking has been *cancelled*.\nPlease contact us if you have any questions.\n📞 +1 234 567 89",
                    "rescheduled": f"📅 Your booking has been *rescheduled*.\nNew date: *{request.scheduled_date or 'TBD'}*\nWe will confirm the details shortly.",
                    "pending": "🟡 Your booking is now *pending* review. We will contact you soon!",
                }
                msg = status_messages.get(
                    request.status,
                    f"📋 Your booking status has been updated to: *{request.status}*"
                )
                if request.notes:
                    msg += f"\n\n📝 *Note from admin:* {request.notes}"

                await _bot.send_message(user_id, msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Failed to notify user {user_id}: {e}")

    return {"success": True}


# ─── Protected: Admins (superadmin only) ──────────────────────────────────────

@app.get("/admins")
async def list_admins(payload=Depends(require_superadmin)):
    data = await get_all_admins()
    return [
        {"id": a[0], "username": a[1], "role": a[2], "created_at": a[3]}
        for a in data
    ]


@app.post("/admins")
async def create_admin(request: AddAdminRequest, payload=Depends(require_superadmin)):
    try:
        await add_admin(request.username, request.password, request.role)
        return {"success": True}
    except Exception:
        raise HTTPException(status_code=400, detail="Username already exists")


@app.delete("/admins/{admin_id}")
async def remove_admin(admin_id: int, payload=Depends(require_superadmin)):
    await delete_admin(admin_id)
    return {"success": True}
