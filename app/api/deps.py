import asyncio
import json
import time
from datetime import date as _date
from fastapi import Depends, Header, HTTPException, Request

from bot.config import BOT_TOKEN
from bot.utils.telegram_auth import verify_telegram_init_data
from app.middleware.rate_limit import ai_daily_limit, ip_limiter, user_limiter
from app.middleware.access_log import log_security_event
from db.queries import update_last_seen, get_user, atomic_increment_ai_calls

_MAX_AGE         = 86_400  # 24 h — Telegram's recommended maximum
_AUTH_FAIL_LIMIT = 5       # bad-auth attempts per IP per minute
_API_RATE_LIMIT  = 100     # authenticated requests per user per minute

# In-memory fallback AI-counter, used ONLY when the DB-backed atomic counter is
# unavailable (returns 0). Prevents a DB outage from turning into unlimited
# (costly) AI usage. Per-process, resets daily. Not shared across instances —
# but a conservative per-process cap beats fail-open.
_fallback_ai_counter: dict[int, tuple[str, int]] = {}


def _fallback_increment_ai(tg_id: int) -> int:
    today = _date.today().isoformat()
    day, cnt = _fallback_ai_counter.get(tg_id, (today, 0))
    if day != today:
        cnt = 0
    cnt += 1
    _fallback_ai_counter[tg_id] = (today, cnt)
    return cnt


# Strong refs to fire-and-forget tasks. asyncio.create_task() alone does NOT keep
# a reference — without this the task can be GC'd mid-execution and silently vanish.
_bg_tasks: set[asyncio.Task] = set()


def spawn_bg(coro) -> asyncio.Task:
    """Fire-and-forget a coroutine while holding a strong reference until it finishes."""
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
    return task


def get_client_ip(request: Request) -> str:
    """Extract real client IP, honouring Railway's X-Forwarded-For header."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def get_current_tg_id(
    request: Request,
    x_telegram_init_data: str = Header(default="", alias="X-Telegram-Init-Data"),
) -> int:
    ip = get_client_ip(request)

    if not x_telegram_init_data:
        if not await ip_limiter.is_allowed(f"auth:{ip}", _AUTH_FAIL_LIMIT, 60):
            log_security_event("AUTH_BLOCKED", ip=ip, reason="rate_limit_missing_header")
            raise HTTPException(
                status_code=429,
                detail="Слишком много запросов. Подожди минуту.",
                headers={"Retry-After": "60"},
            )
        log_security_event("AUTH_FAILURE", ip=ip, reason="missing_header")
        raise HTTPException(status_code=401, detail="Missing authentication")

    params = verify_telegram_init_data(x_telegram_init_data, BOT_TOKEN)
    if not params:
        if not await ip_limiter.is_allowed(f"auth:{ip}", _AUTH_FAIL_LIMIT, 60):
            log_security_event("AUTH_BLOCKED", ip=ip, reason="rate_limit")
            raise HTTPException(
                status_code=429,
                detail="Слишком много попыток авторизации. Подожди минуту.",
                headers={"Retry-After": "60"},
            )
        log_security_event("AUTH_FAILURE", ip=ip, reason="invalid_signature")
        raise HTTPException(status_code=401, detail="Invalid initData signature")

    try:
        auth_ts = int(params["auth_date"])
        now_ts  = time.time()
        age     = now_ts - auth_ts
        if age < -30:
            log_security_event("AUTH_FAILURE", ip=ip, reason="future_auth_date", auth_date=auth_ts)
            raise HTTPException(status_code=401, detail="Invalid auth_date in initData")
        if age > _MAX_AGE:
            log_security_event("AUTH_FAILURE", ip=ip, reason="session_expired", age_sec=int(age))
            raise HTTPException(status_code=401, detail="Telegram session expired — reopen the app")
    except HTTPException:
        raise
    except (KeyError, ValueError, TypeError):
        log_security_event("AUTH_FAILURE", ip=ip, reason="missing_auth_date")
        raise HTTPException(status_code=401, detail="Missing auth_date in initData")

    try:
        tg_id = int(json.loads(params["user"])["id"])
    except (KeyError, json.JSONDecodeError, ValueError, TypeError):
        log_security_event("AUTH_FAILURE", ip=ip, reason="bad_user_field")
        raise HTTPException(status_code=401, detail="Cannot parse user from initData")

    if not await user_limiter.is_allowed(f"api:{tg_id}", _API_RATE_LIMIT, 60):
        log_security_event("RATE_LIMITED", tg_id=tg_id, ip=ip, path=request.url.path)
        raise HTTPException(
            status_code=429,
            detail="Слишком много запросов — подожди немного.",
            headers={"Retry-After": "60"},
        )

    spawn_bg(asyncio.to_thread(update_last_seen, tg_id))

    return tg_id


async def check_ai_quota(tg_id: int = Depends(get_current_tg_id)) -> int:
    """
    Dependency for AI endpoints.
    Atomically increments the daily Supabase-persisted counter and checks quota.
    Raises 429 when exhausted.

    Uses a single atomic DB operation (migration 005) to avoid the read→check→write
    race condition that previously allowed concurrent requests to exceed the limit.
    """
    user = await asyncio.to_thread(get_user, tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    status = (user.get("status") or "free").lower()
    limit  = ai_daily_limit(status)

    new_count = await asyncio.to_thread(atomic_increment_ai_calls, user["id"])

    # DB counter unavailable (0 = error/not configured) → fail-safe to an
    # in-memory cap instead of fail-open (which would allow unlimited AI spend).
    if new_count <= 0:
        new_count = _fallback_increment_ai(tg_id)

    if new_count > limit:
        log_security_event("AI_QUOTA_EXCEEDED", tg_id=tg_id, status=status, limit=limit, used=new_count)
        raise HTTPException(
            status_code=429,
            detail=f"Дневной лимит AI исчерпан ({limit}/день). Обновится завтра в полночь.",
            headers={"Retry-After": "86400"},
        )

    return tg_id
