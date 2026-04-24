import json
import logging
from db.client import get_client


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
            "health_issues": profile.get("health_issues", []),
            "equipment":     profile.get("equipment", ["gym"]),
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
        return []


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
        return None
