import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from db.queries import get_user, save_user_logs, get_user_logs

router = APIRouter()


@router.post("/api/logs")
async def save_logs(payload: dict):
    """Save user food, weight and measurement logs for cross-device sync."""
    try:
        tg_id = payload.get("tg_id")
        if not tg_id:
            return JSONResponse({"ok": False, "error": "no tg_id"})
        user = get_user(int(tg_id))
        if not user:
            return JSONResponse({"ok": False, "error": "user not found"})
        save_user_logs(user["id"], {
            "food":        payload.get("food", []),
            "weight_logs": payload.get("weight_logs", []),
            "meas_logs":   payload.get("meas_logs", []),
        })
        return JSONResponse({"ok": True})
    except Exception as e:
        logging.exception("save_logs error")
        return JSONResponse({"ok": False, "error": str(e)})


@router.get("/api/logs")
async def load_logs(tg_id: int):
    """Load saved logs for cross-device sync."""
    try:
        user = get_user(tg_id)
        if not user:
            return JSONResponse({"found": False})
        data = get_user_logs(user["id"])
        return JSONResponse({"found": True, **data})
    except Exception as e:
        logging.exception("load_logs error")
        return JSONResponse({"found": False, "error": str(e)})
