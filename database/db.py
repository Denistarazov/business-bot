import aiosqlite

DB_PATH = "database/bot.db"

async def init_db():
    """Create tables if they don't exist"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE,
                first_name TEXT,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                service TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (telegram_id)
            )
        """)
        await db.commit()

async def add_user(telegram_id: int, first_name: str, username: str):
    """Save user to database"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (telegram_id, first_name, username)
            VALUES (?, ?, ?)
        """, (telegram_id, first_name, username))
        await db.commit()

async def add_booking(user_id: int, service: str):
    """Save booking to database"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO bookings (user_id, service)
            VALUES (?, ?)
        """, (user_id, service))
        await db.commit()

async def get_all_bookings():
    """Get all bookings"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT users.first_name, users.username, bookings.service, bookings.status, bookings.created_at
            FROM bookings
            JOIN users ON bookings.user_id = users.telegram_id
            ORDER BY bookings.created_at DESC
        """) as cursor:
            return await cursor.fetchall()
