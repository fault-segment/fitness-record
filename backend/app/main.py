from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.database import init_db
from app.logging import setup_logging
from app.routers import auth, chat
from app.trace import TraceMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Application starting...")
    try:
        await init_db()
        logger.info("Database initialised")
    except Exception:
        logger.exception("Database initialisation failed")
        raise
    if not os.path.exists("data/food_chromadb"):
        from app.rag.data import FOOD_DATA
        from app.rag.store import init_food_db
        init_food_db(FOOD_DATA)
        logger.info("Seeded {} foods into Chroma", len(FOOD_DATA))
    # Whisper 暂时关闭，省内存
    # from app.routers.speech import _get_model
    # _get_model()
    # logger.info("Whisper model preloaded")
    logger.info("Application startup complete")
    yield


app = FastAPI(title="饮食助手", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TraceMiddleware)

app.include_router(auth.router)
app.include_router(chat.router)
# 语音接口暂时关闭
# app.include_router(speech.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.opt(exception=True).error(
        "Unhandled exception: {path}", path=request.url.path
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health")
async def health():
    return {"status": "ok"}
