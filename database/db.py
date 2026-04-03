"""
Database module — supports SQLite (local) and PostgreSQL (production).
Uses the 'databases' library for async queries.
"""
import databases
import hashlib
import os
import datetime

# ── Connection URL ────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///database/bot.db")

# Fix Railway postgres:// URL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

IS_POSTGRES = DATABASE_URL.startswith("postgresql")

database = databases.Database(DATABASE_URL)

# ── Time slots ────────────────────────────────────────────────────────────────
WORKING_HOURS = [f"{h:02d}:00" for h in range(9, 20)]  # 9:00 – 19:00


# ── Helpers ───────────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


# ── Init & migrations ─────────────────────────────────────────────────────────
async def init_db():
    os.makedirs("database", exist_ok=True)

    pk   = "BIGSERIAL" if IS_POSTGRES else "INTEGER"
    int_ = "BIGINT"    if IS_POSTGRES else "INTEGER"
    ts   = "NOW()"     if IS_POSTGRES else "CURRENT_TIMESTAMP"

    await database.execute(f"""
        CREATE TABLE IF NOT EXISTS users (
            id          {pk}  PRIMARY KEY,
            telegram_id {int_} UNIQUE NOT NULL,
            first_name  TEXT DEFAULT '',
            username    TEXT DEFAULT '',
            created_at  TIMESTAMP DEFAULT {ts}
        )
    """)

    await database.execute(f"""
        CREATE TABLE IF NOT EXISTS bookings (
            id             {pk}  PRIMARY KEY,
            user_id        {int_} NOT NULL,
            service        TEXT  NOT NULL,
            phone          TEXT  DEFAULT '',
            status         TEXT  DEFAULT 'pending',
            booking_date   TEXT,
            booking_time   TEXT,
            scheduled_date TEXT,
            notes          TEXT,
            reminder_sent  INTEGER DEFAULT 0,
            created_at     TIMESTAMP DEFAULT {ts}
        )
    """)

    await database.execute(f"""
        CREATE TABLE IF NOT EXISTS admins (
            id            {pk}  PRIMARY KEY,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT DEFAULT 'admin',
            telegram_id   {int_},
            created_at    TIMESTAMP DEFAULT {ts}
        )
    """)

    # Migrations — add columns silently if they don't exist
    ifne = "IF NOT EXISTS" if IS_POSTGRES else ""
    for col, definition in [
        ("booking_date",   "TEXT"),
        ("booking_time",   "TEXT"),
        ("reminder_sent",  "INTEGER DEFAULT 0"),
        ("scheduled_date", "TEXT"),
        ("notes",          "TEXT"),
        ("phone",          "TEXT DEFAULT ''"),
        (f"telegram_id",   f"{'BIGINT' if IS_POSTGRES else 'INTEGER'}"),
    ]:
        for table in (["bookings"] if col != "telegram_id" else ["admins"]):
            try:
                await database.execute(
                    f"ALTER TABLE {table} ADD COLUMN {ifne} {col} {definition}"
                )
            except Exception:
                pass

    # Default superadmin
    count = await database.fetch_val("SELECT COUNT(*) FROM admins")
    if not count:
        await database.execute(
            "INSERT INTO admins (username, password_hash, role) VALUES (:u, :p, :r)",
            {"u": "admin", "p": hash_password("admin123"), "r": "superadmin"},
        )
        print("✅ Default admin created — login: admin / password: admin123")


# ── Users ─────────────────────────────────────────────────────────────────────
async def add_user(telegram_id: int, first_name: str, username: str):
    await database.execute(
        """INSERT INTO users (telegram_id, first_name, username)
           VALUES (:tid, :fn, :un)
           ON CONFLICT (telegram_id) DO NOTHING""",
        {"tid": telegram_id, "fn": first_name, "un": username},
    )


async def get_all_user_ids() -> list[int]:
    rows = await database.fetch_all("SELECT telegram_id FROM users")
    return [r["telegram_id"] for r in rows]


async def get_users_count() -> int:
    return await database.fetch_val("SELECT COUNT(*) FROM users") or 0


# ── Bookings ──────────────────────────────────────────────────────────────────
async def add_booking(
    user_id: int,
    service: str,
    phone: str = "",
    booking_date: str = None,
    booking_time: str = None,
) -> int:
    return await database.execute(
        """INSERT INTO bookings (user_id, service, phone, booking_date, booking_time)
           VALUES (:uid, :svc, :phone, :date, :time)""",
        {"uid": user_id, "svc": service, "phone": phone,
         "date": booking_date, "time": booking_time},
    )


async def get_all_bookings() -> list:
    return await database.fetch_all("""
        SELECT b.id, u.first_name, u.username, b.service, b.phone,
               b.status, b.booking_date, b.booking_time,
               b.scheduled_date, b.notes, b.created_at
        FROM bookings b
        JOIN users u ON b.user_id = u.telegram_id
        ORDER BY b.created_at DESC
    """)


async def get_user_bookings(telegram_id: int) -> list:
    return await database.fetch_all(
        """SELECT b.id, u.first_name, u.username, b.service, b.phone,
                  b.status, b.booking_date, b.booking_time,
                  b.scheduled_date, b.notes, b.created_at
           FROM bookings b
           JOIN users u ON b.user_id = u.telegram_id
           WHERE b.user_id = :tid
           ORDER BY b.created_at DESC""",
        {"tid": telegram_id},
    )


async def update_booking(
    booking_id: int,
    status: str,
    scheduled_date: str = None,
    notes: str = None,
):
    await database.execute(
        "UPDATE bookings SET status=:s, scheduled_date=:sd, notes=:n WHERE id=:id",
        {"s": status, "sd": scheduled_date, "n": notes, "id": booking_id},
    )


async def get_booking_user_id(booking_id: int):
    row = await database.fetch_one(
        "SELECT user_id FROM bookings WHERE id=:id", {"id": booking_id}
    )
    return row["user_id"] if row else None


# ── Time slots ────────────────────────────────────────────────────────────────
async def get_booked_slots(date: str) -> list[str]:
    rows = await database.fetch_all(
        """SELECT booking_time FROM bookings
           WHERE booking_date = :date AND status NOT IN ('cancelled')""",
        {"date": date},
    )
    return [r["booking_time"] for r in rows if r["booking_time"]]


async def get_available_slots(date: str) -> list[str]:
    booked = await get_booked_slots(date)
    return [t for t in WORKING_HOURS if t not in booked]


# ── Reminders ─────────────────────────────────────────────────────────────────
async def get_bookings_for_reminder() -> list:
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    return await database.fetch_all(
        """SELECT b.id, b.user_id, b.service, b.booking_time
           FROM bookings b
           WHERE b.booking_date = :tomorrow
             AND b.reminder_sent = 0
             AND b.status = 'pending'""",
        {"tomorrow": tomorrow},
    )


async def mark_reminder_sent(booking_id: int):
    await database.execute(
        "UPDATE bookings SET reminder_sent=1 WHERE id=:id", {"id": booking_id}
    )


# ── Statistics ────────────────────────────────────────────────────────────────
async def get_stats_by_day(days: int = 30) -> list:
    start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    return await database.fetch_all(
        """SELECT date(created_at) AS day, COUNT(*) AS count
           FROM bookings
           WHERE date(created_at) >= :start
           GROUP BY day ORDER BY day""",
        {"start": start},
    )


async def get_stats_by_service() -> list:
    return await database.fetch_all(
        """SELECT service, COUNT(*) AS count
           FROM bookings
           GROUP BY service ORDER BY count DESC LIMIT 10"""
    )


# ── Admins ────────────────────────────────────────────────────────────────────
async def get_admin_by_username(username: str):
    return await database.fetch_one(
        "SELECT id, username, password_hash, role, telegram_id FROM admins WHERE username=:u",
        {"u": username},
    )


async def get_admin_by_telegram_id(telegram_id: int):
    return await database.fetch_one(
        "SELECT id, username, role FROM admins WHERE telegram_id=:tid",
        {"tid": telegram_id},
    )


async def get_all_admins() -> list:
    return await database.fetch_all(
        "SELECT id, username, role, telegram_id, created_at FROM admins ORDER BY created_at"
    )


async def add_admin(username: str, password: str, role: str = "admin"):
    await database.execute(
        "INSERT INTO admins (username, password_hash, role) VALUES (:u, :p, :r)",
        {"u": username, "p": hash_password(password), "r": role},
    )


async def delete_admin(admin_id: int):
    await database.execute(
        "DELETE FROM admins WHERE id=:id AND role != 'superadmin'", {"id": admin_id}
    )


async def link_telegram_id(admin_id: int, telegram_id: int):
    await database.execute(
        "UPDATE admins SET telegram_id=:tid WHERE id=:id",
        {"tid": telegram_id, "id": admin_id},
    )
