import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()

from web.server import app


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    print(f"🚀 Starting web server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
