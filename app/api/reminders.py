import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from db.queries import upsert_reminder, get_reminders_for_user, delete_reminder, get_user

router = APIRouter()


@router.get("/api/reminders")
async def get_reminders(tg_id: int):
    user = get_user(tg_id)
    if not user:
        return JSONResponse({"reminders": []})
    return JSONResponse({"reminders": get_reminders_for_user(user["id"])})


@router.post("/api/reminders")
async def save_reminder(payload: dict):
    tg_id = payload.get("tg_id")
    if not tg_id:
        return JSONResponse({"ok": False, "error": "tg_id required"}, status_code=400)
    rtype = payload.get("type")
    if rtype not in ("water", "meal", "log"):
        return JSONResponse({"ok": False, "error": "invalid type"}, status_code=400)

    user = get_user(int(tg_id))
    if not user:
        return JSONResponse({"ok": False, "error": "user not found"}, status_code=404)

    result = upsert_reminder(user["id"], int(tg_id), payload)
    if not result:
        return JSONResponse({"ok": False, "error": "db error"}, status_code=500)

    # Re-schedule in the live scheduler
    try:
        from bot.scheduler import schedule_reminder
        schedule_reminder(result)
    except Exception as e:
        logging.warning("schedule_reminder failed: %s", e)

    return JSONResponse({"ok": True, "reminder": result})


@router.delete("/api/reminders/{reminder_id}")
async def remove_reminder(reminder_id: str):
    try:
        from bot.scheduler import unschedule_reminder
        unschedule_reminder(reminder_id)
    except Exception as e:
        logging.warning("unschedule_reminder failed: %s", e)
    ok = delete_reminder(reminder_id)
    return JSONResponse({"ok": ok})
