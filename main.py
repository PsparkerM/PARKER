import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from aiogram import Bot, Dispatcher
from aiogram.types import Update

from bot.config import BOT_TOKEN, WEBAPP_URL
from bot.handlers import start
from bot.services.nutrition import compute_macros_for_profile
from bot.services.ai_service import generate_meal_plan

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
        webhook_url = f"{WEBAPP_URL.rstrip('/')}{WEBHOOK_PATH}"
        await bot.set_webhook(webhook_url, drop_pending_updates=True)
        logging.info("Webhook set: %s", webhook_url)
    else:
        logging.warning("WEBAPP_URL not set — bot won't receive Telegram updates")
    yield
    if WEBAPP_URL:
        await bot.delete_webhook()
    await bot.session.close()
    logging.info("Bot stopped")


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/")
async def serve_app():
    with open("app/static/index.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/profile")
async def create_profile(request: Request):
    data = await request.json()
    try:
        macros = compute_macros_for_profile(data)
        plan = await generate_meal_plan(data, macros)
        return JSONResponse({"macros": macros, "plan": plan})
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Отсутствует поле: {e}")
    except Exception as e:
        logging.exception("Profile generation error")
        raise HTTPException(status_code=500, detail=str(e))
