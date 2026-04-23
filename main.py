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
from app.api.admin import router as admin_router
from app.api.adapt import router as adapt_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
dp.include_router(start.router)

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"


async def _test_ai_on_startup():
    from bot.config import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY:
        logging.critical("=" * 60)
        logging.critical("❌  ANTHROPIC_API_KEY НЕ ЗАДАН!")
        logging.critical("    AI не будет работать. Добавь переменную в Railway:")
        logging.critical("    Settings → Variables → ANTHROPIC_API_KEY = sk-ant-...")
        logging.critical("=" * 60)
        return
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=15.0)
        msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}],
        )
        logging.info("✅  Claude AI: OK — %s", msg.content[0].text.strip())
    except anthropic.AuthenticationError:
        logging.critical("❌  ANTHROPIC_API_KEY НЕВЕРНЫЙ — AuthenticationError. Обнови ключ на console.anthropic.com")
    except anthropic.RateLimitError:
        logging.warning("⚠️  Claude: RateLimitError — нет кредитов или превышен лимит")
    except Exception as e:
        logging.error("❌  Claude test failed: %s — %s", type(e).__name__, e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _test_ai_on_startup()
    if WEBAPP_URL:
        url = f"{WEBAPP_URL.rstrip('/')}{WEBHOOK_PATH}"
        await bot.set_webhook(url, drop_pending_updates=True)
        logging.info("Webhook set: %s", url[:50] + "...")
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
app.include_router(admin_router)
app.include_router(adapt_router)
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


@app.get("/debug/ai")
async def debug_ai():
    import anthropic as _ant
    from bot.config import ANTHROPIC_API_KEY
    info = {
        "anthropic_sdk": _ant.__version__,
        "key_set": bool(ANTHROPIC_API_KEY),
        "key_prefix": ANTHROPIC_API_KEY[:12] + "..." if ANTHROPIC_API_KEY else "EMPTY",
    }
    if not ANTHROPIC_API_KEY:
        return {**info, "status": "error",
                "fix": "Set ANTHROPIC_API_KEY in Railway → Variables"}
    try:
        client = _ant.AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=15.0)
        msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=20,
            messages=[{"role": "user", "content": "скажи 'ок'"}],
        )
        return {**info, "status": "ok", "reply": msg.content[0].text.strip()}
    except _ant.AuthenticationError as e:
        return {**info, "status": "error", "error": "AuthenticationError",
                "detail": str(e), "fix": "API key invalid — get new one at console.anthropic.com"}
    except _ant.RateLimitError as e:
        return {**info, "status": "error", "error": "RateLimitError",
                "detail": str(e), "fix": "Add credits at console.anthropic.com/billing"}
    except Exception as e:
        return {**info, "status": "error", "error": type(e).__name__, "detail": str(e)}
