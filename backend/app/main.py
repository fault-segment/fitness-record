from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import auth, chat, speech


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Seed food DB if empty
    if not os.path.exists("data/food_chromadb"):
        from app.rag.data import FOOD_DATA
        from app.rag.store import init_food_db
        init_food_db(FOOD_DATA)
    yield


app = FastAPI(title="饮食助手", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(speech.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
