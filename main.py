import asyncio
import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()

from database.db import database, init_db
from web.server import app


async def main():
    """Initialize database and start web server (Railway only)."""
    print("=" * 60)
    print("🚀 Initializing database...")
    await database.connect()
    await init_db()
    print("✅ Database initialized")
    print("=" * 60)

    port = int(os.getenv("PORT", 8080))
    print(f"🌐 Starting web server on port {port}...")
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
