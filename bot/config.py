import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
WEBAPP_URL: str = os.getenv("WEBAPP_URL", "")
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
ADMIN_SECRET:           str = os.getenv("ADMIN_SECRET", "")
WEBHOOK_SECRET_TOKEN:   str = os.getenv("WEBHOOK_SECRET_TOKEN", "")
# Comma-separated list of Telegram IDs allowed to use admin bot commands
_raw = os.getenv("ADMIN_TG_IDS", "")
ADMIN_TG_IDS: set[int] = {int(x.strip()) for x in _raw.split(",") if x.strip().isdigit()}

MAINTENANCE_MODE: bool = os.getenv("MAINTENANCE_MODE", "").lower() in ("1", "true", "yes")

# ── Публичный запуск ────────────────────────────────────────────────────────
# Один момент истины для go-live: ровно в это время бот сам выходит из режима
# техработ (открывается ВСЕМ) и уходит масштабная рассылка о перезапуске.
# 09:00 МСК = 06:00 UTC. После наступления момента бот остаётся открытым даже
# при MAINTENANCE_MODE=true и переживает рестарты Railway (логика по времени).
# Можно переопределить через env LAUNCH_AT_UTC="2026-06-23T06:00:00+00:00".
def _parse_launch() -> datetime:
    raw = os.getenv("LAUNCH_AT_UTC", "").strip()
    if raw:
        try:
            dt = datetime.fromisoformat(raw)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime(2026, 6, 23, 6, 0, 0, tzinfo=timezone.utc)

LAUNCH_AT_UTC: datetime = _parse_launch()

# ── Telegram Stars подписка (валюта XTR) ────────────────────────────────────
# ЕДИНСТВЕННОЕ место, где задаётся цена. Меняй здесь или через .env —
# и бот, и Mini App (in-app покупка) подхватят значение автоматически.
SUB_MONTHLY_STARS: int = int(os.getenv("SUB_MONTHLY_STARS", "399"))   # ⭐ за месяц
SUB_ANNUAL_STARS:  int = int(os.getenv("SUB_ANNUAL_STARS",  "3990"))  # ⭐ за год
SUB_MONTHLY_DAYS:  int = int(os.getenv("SUB_MONTHLY_DAYS",  "30"))    # длительность мес. подписки
SUB_ANNUAL_DAYS:   int = int(os.getenv("SUB_ANNUAL_DAYS",   "365"))   # длительность год. подписки
# За сколько дней до окончания слать напоминание о продлении
SUB_RENEW_NOTIFY_DAYS: int = int(os.getenv("SUB_RENEW_NOTIFY_DAYS", "3"))

# Дневной лимит AI-запросов для Pro (потолок расхода на AI = ключевой рычаг
# себестоимости). Меняй здесь или через env. Free=5, VIP — без лимита.
PRO_AI_DAILY_LIMIT: int = int(os.getenv("PRO_AI_DAILY_LIMIT", "15"))

# Каталог планов — единый источник правды для bot/handlers/payment.py и
# app/api/subscribe.py. Чистые данные, без типов aiogram, чтобы импортировать
# можно было откуда угодно.
SUB_PLANS: dict[str, dict] = {
    "monthly": {
        "stars":       SUB_MONTHLY_STARS,
        "days":        SUB_MONTHLY_DAYS,
        "title":       "P.A.R.K.E.R. Pro — 1 месяц",
        "description": f"{PRO_AI_DAILY_LIMIT} AI-запросов в день, чат с Арни, разбор фото еды, адаптация плана",
    },
    "annual": {
        "stars":       SUB_ANNUAL_STARS,
        "days":        SUB_ANNUAL_DAYS,
        "title":       "P.A.R.K.E.R. Pro — 1 год",
        "description": f"{PRO_AI_DAILY_LIMIT} AI-запросов в день на целый год. Экономия 17% против месячной",
    },
}

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан")
