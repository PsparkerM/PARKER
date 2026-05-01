import hmac
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from aiogram import Dispatcher
from aiogram.types import Update

from bot.config import BOT_TOKEN, WEBAPP_URL, WEBHOOK_SECRET_TOKEN
from bot.bot_instance import bot
from bot.handlers import start
from bot.handlers.start import set_bot_commands
from app.api.profile import router as profile_router
from app.api.chat import router as chat_router
from app.api.food import router as food_router
from app.api.admin import router as admin_router
from app.api.adapt import router as adapt_router
from app.api.user import router as user_router
from app.api.notify import router as notify_router
from app.api.reminders import router as reminders_router
from app.api.logs import router as logs_router
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.access_log import AccessLogMiddleware

# ── Logging setup ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
# Security events always at WARNING+ — ensure they're never filtered
logging.getLogger("parker.security").setLevel(logging.WARNING)

dp = Dispatcher()
dp.include_router(start.router)

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

# ── Request body size limits ──────────────────────────────────────────────
_UPLOAD_PATHS  = {"/api/food/photo"}
_UPLOAD_LIMIT  = 10 * 1_024 * 1_024   # 10 MB — image uploads
_DEFAULT_LIMIT =  1 * 1_024 * 1_024   # 1 MB  — all other API routes


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: ASGIApp) -> Response:
        cl = request.headers.get("content-length")
        if cl:
            limit = _UPLOAD_LIMIT if request.url.path in _UPLOAD_PATHS else _DEFAULT_LIMIT
            if int(cl) > limit:
                return JSONResponse(
                    {"error": "Request body too large"},
                    status_code=413,
                )
        return await call_next(request)


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
    # AI test + reminders scheduler запускаем в фоне
    asyncio.create_task(_test_ai_on_startup())
    from bot.scheduler import scheduler, load_all_reminders
    scheduler.start()
    asyncio.create_task(load_all_reminders())

    if not WEBHOOK_SECRET_TOKEN:
        logging.warning(
            "⚠️  WEBHOOK_SECRET_TOKEN не задан — входящие Telegram updates не проверяются по подписи. "
            "Добавь WEBHOOK_SECRET_TOKEN в Railway Variables."
        )

    if WEBAPP_URL:
        url = f"{WEBAPP_URL.rstrip('/')}{WEBHOOK_PATH}"
        try:
            await bot.set_webhook(
                url,
                drop_pending_updates=False,
                secret_token=WEBHOOK_SECRET_TOKEN or None,
            )
            logging.info("✅ Webhook set: %s...", url[:60])
        except Exception as e:
            logging.error("❌ set_webhook FAILED: %s", e)
    else:
        logging.warning("WEBAPP_URL не задан — webhook не установлен")

    try:
        await set_bot_commands(bot)
    except Exception as e:
        logging.warning("set_bot_commands failed: %s", e)

    yield

    # НЕ удаляем вебхук при остановке — Railway делает rolling deploy,
    # старый инстанс не должен удалять вебхук пока новый его уже установил
    from bot.scheduler import scheduler
    if scheduler.running:
        scheduler.shutdown(wait=False)
    try:
        await bot.session.close()
    except Exception:
        pass
    logging.info("Bot остановлен")


app = FastAPI(lifespan=lifespan)

# Middleware execution order is LIFO — last added runs first on request.
# Desired order (outermost → innermost):
#   AccessLog → SecurityHeaders → BodySizeLimit → CORS → route handler

# CORS: strict allowlist — only the Railway deployment domain.
# Falls back to same-origin-only when WEBAPP_URL is not set.
_cors_origins = [WEBAPP_URL.rstrip("/")] if WEBAPP_URL else []
if not _cors_origins:
    logging.warning("WEBAPP_URL not set — CORS will block cross-origin requests")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Telegram-Init-Data"],
    max_age=600,
)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AccessLogMiddleware)

app.include_router(profile_router)
app.include_router(chat_router)
app.include_router(food_router)
app.include_router(admin_router)
app.include_router(adapt_router)
app.include_router(user_router)
app.include_router(notify_router)
app.include_router(reminders_router)
app.include_router(logs_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    if WEBHOOK_SECRET_TOKEN:
        token = request.headers.get("x-telegram-bot-api-secret-token", "")
        if not token or not hmac.compare_digest(token, WEBHOOK_SECRET_TOKEN):
            return JSONResponse({"error": "forbidden"}, status_code=403)
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


@app.get("/debug/webhook")
async def debug_webhook(request: Request):
    from bot.config import ADMIN_SECRET
    secret = request.query_params.get("secret", "")
    if not ADMIN_SECRET or not hmac.compare_digest(secret, ADMIN_SECRET):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    try:
        info = await bot.get_webhook_info()
        # Return URL length only — never expose the token itself
        return {
            "webhook_url_len": len(info.url),
            "pending_updates": info.pending_update_count,
            "last_error": info.last_error_message,
            "last_error_date": str(info.last_error_date) if info.last_error_date else None,
            "webapp_url_set": bool(WEBAPP_URL),
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/reset-webhook")
async def reset_webhook(request: Request):
    from bot.config import ADMIN_SECRET
    if not ADMIN_SECRET:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    secret = request.query_params.get("secret", "")
    if not hmac.compare_digest(secret, ADMIN_SECRET):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if not WEBAPP_URL:
        return JSONResponse({"error": "WEBAPP_URL not set"}, status_code=500)
    drop = request.query_params.get("drop", "false").lower() == "true"
    url = f"{WEBAPP_URL.rstrip('/')}{WEBHOOK_PATH}"
    try:
        await bot.set_webhook(
            url,
            drop_pending_updates=drop,
            secret_token=WEBHOOK_SECRET_TOKEN or None,
        )
        info = await bot.get_webhook_info()
        return {"ok": True, "dropped_pending": drop, "webhook_url_len": len(info.url), "pending_updates": info.pending_update_count}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/debug/reminders")
async def debug_reminders(request: Request):
    from bot.config import ADMIN_SECRET
    secret = request.query_params.get("secret", "")
    if not ADMIN_SECRET or not hmac.compare_digest(secret, ADMIN_SECRET):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    from bot.scheduler import scheduler
    from db.queries import get_all_active_reminders
    jobs = [{"id": j.id, "next": str(j.next_run_time)} for j in scheduler.get_jobs()]
    try:
        db_rows = get_all_active_reminders()
    except Exception as e:
        db_rows = [{"error": str(e)}]
    return {"scheduled_jobs": jobs, "db_reminders": db_rows}


@app.get("/debug/ai")
async def debug_ai(request: Request):
    from bot.config import ADMIN_SECRET, ANTHROPIC_API_KEY
    secret = request.query_params.get("secret", "")
    if not ADMIN_SECRET or not hmac.compare_digest(secret, ADMIN_SECRET):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    import anthropic as _ant
    info = {"anthropic_sdk": _ant.__version__, "key_set": bool(ANTHROPIC_API_KEY)}
    if not ANTHROPIC_API_KEY:
        return {**info, "status": "error", "fix": "Set ANTHROPIC_API_KEY in Railway → Variables"}
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
                "fix": "API key invalid — get new one at console.anthropic.com"}
    except _ant.RateLimitError as e:
        return {**info, "status": "error", "error": "RateLimitError",
                "fix": "Add credits at console.anthropic.com/billing"}
    except Exception as e:
        return {**info, "status": "error", "error": type(e).__name__, "detail": str(e)}
