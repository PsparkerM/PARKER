import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from aiogram import Bot, Dispatcher
from aiogram.types import Update

from bot.config import BOT_TOKEN, WEBAPP_URL
from bot.handlers import start
from bot.handlers.start import set_bot_commands
from app.api.profile import router as profile_router
from app.api.chat import router as chat_router
from app.api.food import router as food_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
dp.include_router(start.router)

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if WEBAPP_URL:
        url = f"{WEBAPP_URL.rstrip('/')}{WEBHOOK_PATH}"
        await bot.set_webhook(url, drop_pending_updates=True)
        logging.info("Webhook set")
    else:
        logging.warning("WEBAPP_URL не задан — webhook не установлен")
    await set_bot_commands(bot)
    yield
    if WEBAPP_URL:
        await bot.delete_webhook()
    await bot.session.close()
    logging.info("Bot остановлен")


app = FastAPI(lifespan=lifespan)
app.include_router(profile_router)
app.include_router(chat_router)
app.include_router(food_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/")
async def serve_miniapp():
    with open("app/static/index.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/health")
async def health():
    return {"status": "ok", "bot": "P.A.R.K.E.R."}
