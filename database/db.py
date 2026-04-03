import aiosqlite
import hashlib
import os

DB_PATH = "database/bot.db"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


async def init_db():
    """Create tables and run migrations"""
    os.makedirs("database", exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:

        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE,
                first_name TEXT,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Bookings table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                service TEXT,
                phone TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                scheduled_date TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (telegram_id)
            )
        """)

        # Admins table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                password_hash TEXT,
                role TEXT DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()

        # Migrations: add new columns if they don't exist
        for column, definition in [
            ("phone", "TEXT DEFAULT ''"),
            ("scheduled_date", "TEXT"),
            ("notes", "TEXT"),
        ]:
            try:
                await db.execute(f"ALTER TABLE bookings ADD COLUMN {column} {definition}")
                await db.commit()
            except Exception:
                pass  # Column already exists

        # Create default superadmin if no admins exist
        async with db.execute("SELECT COUNT(*) FROM admins") as cursor:
            count = (await cursor.fetchone())[0]

        if count == 0:
            await db.execute(
                "INSERT INTO admins (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", hash_password("admin123"), "superadmin")
            )
            await db.commit()
            print("Default admin created: login=admin, password=admin123")


# ─── Users ────────────────────────────────────────────────────────────────────

async def add_user(telegram_id: int, first_name: str, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, first_name, username) VALUES (?, ?, ?)",
            (telegram_id, first_name, username)
        )
        await db.commit()


# ─── Bookings ─────────────────────────────────────────────────────────────────

async def add_booking(user_id: int, service: str, phone: str = "") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO bookings (user_id, service, phone) VALUES (?, ?, ?)",
            (user_id, service, phone)
        )
        await db.commit()
        return cursor.lastrowid


async def get_all_bookings():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT bookings.id, users.first_name, users.username,
                   bookings.service, bookings.phone, bookings.status,
                   bookings.scheduled_date, bookings.notes, bookings.created_at
            FROM bookings
            JOIN users ON bookings.user_id = users.telegram_id
            ORDER BY bookings.created_at DESC
        """) as cursor:
            return await cursor.fetchall()


async def get_user_bookings(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT bookings.id, users.first_name, users.username,
                   bookings.service, bookings.phone, bookings.status,
                   bookings.scheduled_date, bookings.notes, bookings.created_at
            FROM bookings
            JOIN users ON bookings.user_id = users.telegram_id
            WHERE bookings.user_id = ?
            ORDER BY bookings.created_at DESC
        """, (telegram_id,)) as cursor:
            return await cursor.fetchall()


async def update_booking(booking_id: int, status: str, scheduled_date: str = None, notes: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE bookings SET status = ?, scheduled_date = ?, notes = ? WHERE id = ?",
            (status, scheduled_date, notes, booking_id)
        )
        await db.commit()


async def get_booking_user_id(booking_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM bookings WHERE id = ?", (booking_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


# ─── Admins ───────────────────────────────────────────────────────────────────

async def get_admin_by_username(username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, username, password_hash, role FROM admins WHERE username = ?",
            (username,)
        ) as cursor:
            return await cursor.fetchone()


async def get_all_admins():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, username, role, created_at FROM admins ORDER BY created_at"
        ) as cursor:
            return await cursor.fetchall()


async def add_admin(username: str, password: str, role: str = "admin"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO admins (username, password_hash, role) VALUES (?, ?, ?)",
            (username, hash_password(password), role)
        )
        await db.commit()


async def delete_admin(admin_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM admins WHERE id = ? AND role != 'superadmin'", (admin_id,))
        await db.commit()
