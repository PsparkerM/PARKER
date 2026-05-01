import json
import time
from fastapi import Depends, Header, HTTPException, Request

from bot.config import BOT_TOKEN
from bot.utils.telegram_auth import verify_telegram_init_data
from app.middleware.rate_limit import ai_daily_limit, ip_limiter, user_limiter
from app.middleware.access_log import log_security_event

_MAX_AGE         = 86_400  # 24 h — Telegram's recommended maximum
_AUTH_FAIL_LIMIT = 5       # bad-auth attempts per IP per minute
_API_RATE_LIMIT  = 100     # authenticated requests per user per minute


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

    return tg_id


async def check_ai_quota(tg_id: int = Depends(get_current_tg_id)) -> int:
    """
    Dependency for AI endpoints.
    Checks the user's daily Supabase-persisted quota and consumes one call.
    Raises 429 when exhausted.
    """
    from db.queries import get_user, get_ai_calls_today, increment_ai_calls

    user = get_user(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    status = (user.get("status") or "free").lower()
    limit  = ai_daily_limit(status)
    used   = get_ai_calls_today(user["id"])

    if used >= limit:
        log_security_event("AI_QUOTA_EXCEEDED", tg_id=tg_id, status=status, limit=limit, used=used)
        raise HTTPException(
            status_code=429,
            detail=f"Дневной лимит AI исчерпан ({limit}/день). Обновится завтра в полночь.",
            headers={"Retry-After": "86400"},
        )

    increment_ai_calls(user["id"])
    return tg_id
