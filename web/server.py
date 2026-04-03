from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.db import get_all_bookings, init_db

# Create FastAPI app
app = FastAPI(title="Business Bot API")

# Allow requests from browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/")
async def root():
    return {"status": "ok", "message": "Business Bot API is running"}

@app.get("/bookings")
async def bookings():
    data = await get_all_bookings()
    result = []
    for b in data:
        result.append({
            "name": b[0],
            "username": b[1],
            "service": b[2],
            "status": b[3],
            "created_at": b[4]
        })
    return result