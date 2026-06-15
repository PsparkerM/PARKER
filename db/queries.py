import json
import logging
from datetime import datetime, timezone, timedelta
from db.client import get_client


def db_ping() -> bool:
    """Cheap liveness check for the database — used by /health/ready."""
    db = get_client()
    if not db:
        return False
    try:
        db.table("users").select("id").limit(1).execute()
        return True
    except Exception:
        logging.warning("db_ping failed", exc_info=True)
        return False


def upsert_user(tg_id: int, profile: dict) -> dict | None:
    db = get_client()
    if not db:
        return None
    try:
        data = {
            "tg_id":         tg_id,
            "name":          profile.get("name"),
            "goal":          profile.get("goal", "maintain"),
            "gender":        profile.get("gender", "male"),
            "age":           profile.get("age"),
            "height_cm":     profile.get("height_cm"),
            "weight_kg":     profile.get("weight_kg"),
            "body_fat_pct":  profile.get("body_fat_pct"),
            "waist_cm":      profile.get("waist_cm"),
            "hips_cm":       profile.get("hips_cm"),
            "chest_cm":      profile.get("chest_cm"),
            "thigh_cm":      profile.get("thigh_cm"),
            "schedule":      profile.get("schedule", "standard"),
            "health_issues":   profile.get("health_issues", []),
            "equipment":       profile.get("equipment", ["gym"]),
            "food_blacklist":  profile.get("food_blacklist", []),
        }
        result = (
            db.table("users")
            .upsert(data, on_conflict="tg_id")
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        logging.exception("upsert_user error")
        return None


def save_plan(user_id: str, plan_type: str, content: str, macros: dict) -> None:
    db = get_client()
    if not db:
        return
    try:
        db.table("plans").insert({
            "user_id": user_id,
            "type":    plan_type,
            "content": content,
            "macros":  macros,
        }).execute()
    except Exception:
        logging.exception("save_plan error")


def upsert_chat_history(user_id: str, history: list) -> None:
    db = get_client()
    if not db:
        return
    try:
        content = json.dumps(history, ensure_ascii=False)
        existing = (
            db.table("plans")
            .select("id")
            .eq("user_id", user_id)
            .eq("type", "chat_history")
            .execute()
        )
        if existing.data:
            db.table("plans").update({"content": content}).eq("id", existing.data[0]["id"]).execute()
        else:
            db.table("plans").insert({"user_id": user_id, "type": "chat_history", "content": content, "macros": {}}).execute()
    except Exception:
        logging.exception("upsert_chat_history error")


def get_chat_history(user_id: str) -> list:
    db = get_client()
    if not db:
        return []
    try:
        result = (
            db.table("plans")
            .select("content")
            .eq("user_id", user_id)
            .eq("type", "chat_history")
            .execute()
        )
        if result.data:
            return json.loads(result.data[0]["content"])
        return []
    except Exception:
        logging.warning("get_chat_history failed user_id=%s", user_id, exc_info=True)
        return []


def get_chat_summary(user_id: str) -> dict | None:
    """Return {summary: str, covered_count: int} or None if no summary stored yet."""
    db = get_client()
    if not db:
        return None
    try:
        result = (
            db.table("plans")
            .select("content,macros")
            .eq("user_id", user_id)
            .eq("type", "chat_summary")
            .execute()
        )
        if not result.data:
            return None
        row = result.data[0]
        return {
            "summary": row.get("content") or "",
            "covered_count": int((row.get("macros") or {}).get("covered_count") or 0),
        }
    except Exception:
        logging.warning("get_chat_summary failed user_id=%s", user_id, exc_info=True)
        return None


def upsert_chat_summary(user_id: str, summary: str, covered_count: int) -> None:
    db = get_client()
    if not db:
        return
    try:
        existing = (
            db.table("plans")
            .select("id")
            .eq("user_id", user_id)
            .eq("type", "chat_summary")
            .execute()
        )
        payload = {"content": summary, "macros": {"covered_count": covered_count}}
        if existing.data:
            db.table("plans").update(payload).eq("id", existing.data[0]["id"]).execute()
        else:
            db.table("plans").insert({"user_id": user_id, "type": "chat_summary", **payload}).execute()
    except Exception:
        logging.exception("upsert_chat_summary error")


def get_user_with_plans(tg_id: int) -> dict | None:
    db = get_client()
    if not db:
        return None
    try:
        user_res = (
            db.table("users")
            .select("*")
            .eq("tg_id", tg_id)
            .single()
            .execute()
        )
        if not user_res.data:
            return None
        user = user_res.data
        uid = user["id"]

        plans_res = (
            db.table("plans")
            .select("*")
            .eq("user_id", uid)
            .order("created_at", desc=True)
            .execute()
        )
        plans = plans_res.data or []

        nutrition = next((p for p in plans if p["type"] == "nutrition"), None)
        workout   = next((p for p in plans if p["type"] == "workout"), None)
        chat_hist = next((p for p in plans if p["type"] == "chat_history"), None)

        return {
            "profile": user,
            "macros":          nutrition["macros"] if nutrition else {},
            "nutrition_plan":  nutrition["content"] if nutrition else "",
            "workout_plan":    workout["content"] if workout else "",
            "chat_history":    json.loads(chat_hist["content"]) if chat_hist else [],
        }
    except Exception:
        logging.exception("get_user_with_plans error")
        return None


def get_all_users() -> list:
    db = get_client()
    if not db:
        return []
    try:
        result = db.table("users").select("*").order("created_at", desc=True).execute()
        return result.data or []
    except Exception:
        logging.exception("get_all_users error")
        return []


def upsert_reminder(user_id: str, tg_id: int, data: dict) -> dict | None:
    db = get_client()
    if not db:
        return None
    try:
        payload = {
            "user_id": user_id,
            "tg_id": tg_id,
            "type": data["type"],
            "label": data.get("label", ""),
            "time": data.get("time"),
            "times": data.get("times"),
            "labels": data.get("labels"),
            "interval_min": data.get("interval_min"),
            "night_mode": data.get("night_mode", True),
            "utc_offset": data.get("utc_offset", 3),
            "active": data.get("active", True),
        }
        # Upsert by (user_id, type) — never create duplicate reminders
        existing = db.table("reminders").select("id") \
            .eq("user_id", user_id).eq("type", data["type"]).execute()
        if existing.data:
            rid = existing.data[0]["id"]
            result = db.table("reminders").update(payload).eq("id", rid).execute()
        else:
            result = db.table("reminders").insert(payload).execute()
        return result.data[0] if result.data else None
    except Exception:
        logging.exception("upsert_reminder error")
        return None


def get_reminders_for_user(user_id: str) -> list:
    db = get_client()
    if not db:
        return []
    try:
        result = db.table("reminders").select("*").eq("user_id", user_id).execute()
        return result.data or []
    except Exception:
        logging.warning("get_reminders_for_user failed user_id=%s", user_id, exc_info=True)
        return []


def get_all_active_reminders() -> list:
    db = get_client()
    if not db:
        return []
    try:
        result = db.table("reminders").select("*").eq("active", True).execute()
        return result.data or []
    except Exception:
        logging.exception("get_all_active_reminders error")
        return []


def delete_reminder(reminder_id: str) -> bool:
    db = get_client()
    if not db:
        return False
    try:
        db.table("reminders").delete().eq("id", reminder_id).execute()
        return True
    except Exception:
        return False


def save_user_logs(user_id: str, logs_data: dict) -> None:
    db = get_client()
    if not db:
        return
    try:
        content = json.dumps(logs_data, ensure_ascii=False)
        existing = (
            db.table("plans")
            .select("id")
            .eq("user_id", user_id)
            .eq("type", "user_logs")
            .execute()
        )
        if existing.data:
            db.table("plans").update({"content": content}).eq("id", existing.data[0]["id"]).execute()
        else:
            db.table("plans").insert({"user_id": user_id, "type": "user_logs", "content": content, "macros": {}}).execute()
    except Exception:
        logging.exception("save_user_logs error")


def get_user_logs(user_id: str) -> dict:
    db = get_client()
    if not db:
        return {}
    try:
        result = (
            db.table("plans")
            .select("content")
            .eq("user_id", user_id)
            .eq("type", "user_logs")
            .execute()
        )
        if result.data:
            return json.loads(result.data[0]["content"])
        return {}
    except Exception:
        logging.warning("get_user_logs failed user_id=%s", user_id, exc_info=True)
        return {}


# ── Normalized daily_logs (migration 008) — dual-write target ──────────────────
# Best-effort: any failure (incl. table not yet created) is swallowed so the
# blob path (source of truth) is never affected.
_DAILY_LOG_COLS = (
    "weight_kg", "sleep_hours", "water_ml", "steps",
    "waist_cm", "hips_cm", "chest_cm", "thigh_cm", "arm_cm",
)
_daily_logs_disabled = False  # flips True if the table is missing → stop retrying


def upsert_daily_logs(user_id: str, rows: list[dict]) -> bool:
    """Bulk upsert normalized daily rows. rows: [{log_date, weight_kg, ...}].

    Idempotent on (user_id, log_date). Returns False (silently) if the table
    doesn't exist or any error occurs — callers must not depend on success.
    """
    global _daily_logs_disabled
    if _daily_logs_disabled:
        return False
    db = get_client()
    if not db or not rows:
        return False
    payload = []
    for r in rows:
        d = r.get("log_date")
        if not d:
            continue
        rec = {"user_id": user_id, "log_date": d, "updated_at": datetime.now(timezone.utc).isoformat()}
        for c in _DAILY_LOG_COLS:
            if r.get(c) is not None:
                rec[c] = r[c]
        payload.append(rec)
    if not payload:
        return False
    try:
        db.table("daily_logs").upsert(payload, on_conflict="user_id,log_date").execute()
        return True
    except Exception as e:
        # If the table isn't there yet, disable to avoid log spam every sync.
        msg = str(e).lower()
        if "daily_logs" in msg and ("does not exist" in msg or "not find" in msg or "schema cache" in msg):
            _daily_logs_disabled = True
            logging.warning("daily_logs table missing — dual-write disabled until next deploy")
        else:
            logging.warning("upsert_daily_logs failed", exc_info=True)
        return False


_USER_MUTABLE_FIELDS = {"name", "avatar", "avatar_data"}


def update_user_fields(tg_id: int, fields: dict) -> bool:
    """Update specific user fields. Only whitelisted columns are allowed."""
    db = get_client()
    if not db or not fields:
        return False
    safe = {k: v for k, v in fields.items() if k in _USER_MUTABLE_FIELDS}
    if not safe:
        logging.warning("update_user_fields: all fields stripped by whitelist, tg_id=%s", tg_id)
        return False
    try:
        db.table("users").update(safe).eq("tg_id", tg_id).execute()
        return True
    except Exception:
        logging.exception("update_user_fields error")
        return False


def update_plan_macros(user_id: str, macros: dict) -> bool:
    """Update the macros field of the latest nutrition plan for this user."""
    db = get_client()
    if not db or not macros:
        return False
    try:
        result = (
            db.table("plans")
            .select("id")
            .eq("user_id", user_id)
            .eq("type", "nutrition")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return False
        db.table("plans").update({"macros": macros}).eq("id", result.data[0]["id"]).execute()
        return True
    except Exception:
        logging.exception("update_plan_macros error user_id=%s", user_id)
        return False


def set_user_status(tg_id: int, status: str) -> bool:
    db = get_client()
    if not db:
        return False
    try:
        db.table("users").update({"status": status}).eq("tg_id", tg_id).execute()
        return True
    except Exception:
        logging.exception("set_user_status error")
        return False


def get_reminder(reminder_id: str) -> dict | None:
    db = get_client()
    if not db:
        return None
    try:
        result = db.table("reminders").select("*").eq("id", reminder_id).single().execute()
        return result.data
    except Exception:
        logging.debug("get_reminder failed id=%s", reminder_id, exc_info=True)
        return None


def get_user(tg_id: int) -> dict | None:
    db = get_client()
    if not db:
        return None
    try:
        result = (
            db.table("users")
            .select("*")
            .eq("tg_id", tg_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        logging.debug("get_user failed tg_id=%s", tg_id, exc_info=True)
        return None


def update_last_seen(tg_id: int) -> None:
    db = get_client()
    if not db:
        return
    try:
        db.table("users").update(
            {"last_seen": datetime.now(timezone.utc).isoformat()}
        ).eq("tg_id", tg_id).execute()
    except Exception:
        logging.exception("update_last_seen error")


def delete_user(tg_id: int) -> bool:
    db = get_client()
    if not db:
        return False
    try:
        user_res = db.table("users").select("id").eq("tg_id", tg_id).single().execute()
        if not user_res.data:
            return True
        uid = user_res.data["id"]
        db.table("plans").delete().eq("user_id", uid).execute()
        db.table("reminders").delete().eq("user_id", uid).execute()
        try:
            db.table("ai_usage").delete().eq("user_id", uid).execute()
        except Exception:
            pass
        db.table("users").delete().eq("tg_id", tg_id).execute()
        return True
    except Exception:
        logging.exception("delete_user error tg_id=%s", tg_id)
        return False


# ── AI usage (Supabase-backed, persists across deploys) ────────────────────

def atomic_increment_ai_calls(user_id: str) -> int:
    """Atomically increments today's AI call counter and returns the new count.

    Uses a PostgreSQL function (migration 005) so the increment is a single
    atomic INSERT … ON CONFLICT DO UPDATE, eliminating the read-modify-write
    race condition of the old approach.

    Returns 0 on DB error so callers treat it as "quota not consumed" and can
    still let the request through rather than silently block all AI calls.
    """
    from datetime import date
    db = get_client()
    if not db:
        return 0
    try:
        result = db.rpc(
            "increment_ai_calls",
            {"p_user_id": user_id, "p_date": date.today().isoformat()},
        ).execute()
        return result.data if isinstance(result.data, int) else 0
    except Exception:
        logging.exception("atomic_increment_ai_calls error user_id=%s", user_id)
        return 0


def get_ai_calls_today(user_id: str) -> int:
    """Read-only quota check (non-mutating). Used only for display/info endpoints."""
    from datetime import date
    db = get_client()
    if not db:
        return 0
    try:
        result = (
            db.table("ai_usage")
            .select("call_count")
            .eq("user_id", user_id)
            .eq("used_date", date.today().isoformat())
            .single()
            .execute()
        )
        return result.data["call_count"] if result.data else 0
    except Exception:
        return 0


# ── Subscriptions ──────────────────────────────────────────────────────────

def get_subscription(user_id: str) -> dict | None:
    db = get_client()
    if not db:
        return None
    try:
        result = (
            db.table("subscriptions")
            .select("*")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        logging.debug("get_subscription failed user_id=%s", user_id, exc_info=True)
        return None


def upsert_subscription(user_id: str, plan: str, charge_id: str, expires_at: datetime) -> dict | None:
    db = get_client()
    if not db:
        return None
    try:
        payload = {
            "user_id":            user_id,
            "plan":               plan,
            "status":             "active",
            "telegram_charge_id": charge_id,
            "starts_at":          datetime.now(timezone.utc).isoformat(),
            "expires_at":         expires_at.isoformat(),
        }
        result = (
            db.table("subscriptions")
            .upsert(payload, on_conflict="user_id")
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        logging.exception("upsert_subscription error user_id=%s", user_id)
        return None


def expire_old_subscriptions() -> int:
    """Mark expired active subscriptions and downgrade user status to free.
    Returns count of expired subscriptions."""
    db = get_client()
    if not db:
        return 0
    try:
        now = datetime.now(timezone.utc).isoformat()
        expired = (
            db.table("subscriptions")
            .select("user_id")
            .eq("status", "active")
            .lt("expires_at", now)
            .execute()
        )
        uids = [row["user_id"] for row in (expired.data or [])]
        if not uids:
            return 0
        # batch: два запроса вместо 2×N в цикле
        db.table("subscriptions").update({"status": "expired"}).in_("user_id", uids).execute()
        db.table("users").update({"status": "free"}).in_("id", uids).execute()
        return len(uids)
    except Exception:
        logging.exception("expire_old_subscriptions error")
        return 0
