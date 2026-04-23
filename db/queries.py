import logging
from db.client import get_client


def upsert_user(tg_id: int, profile: dict) -> dict | None:
    db = get_client()
    if not db:
        return None
    try:
        data = {
            "tg_id": tg_id,
            "goal":          profile.get("goal"),
            "gender":        profile.get("gender"),
            "age":           profile.get("age"),
            "height_cm":     profile.get("height_cm"),
            "weight_kg":     profile.get("weight_kg"),
            "body_fat_pct":  profile.get("body_fat_pct"),
            "waist_cm":      profile.get("waist_cm"),
            "hips_cm":       profile.get("hips_cm"),
            "chest_cm":      profile.get("chest_cm"),
            "thigh_cm":      profile.get("thigh_cm"),
            "schedule":      profile.get("schedule"),
            "health_issues": profile.get("health_issues", []),
            "equipment":     profile.get("equipment", []),
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
