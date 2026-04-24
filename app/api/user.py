import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from db.queries import get_user_with_plans, upsert_chat_history, get_user

router = APIRouter()


@router.get("/api/user")
async def load_user(tg_id: int):
    """Cross-device sync: load profile + plans + chat history for a tg_id."""
    try:
        data = get_user_with_plans(tg_id)
        if not data:
            return JSONResponse({"found": False})
        return JSONResponse({"found": True, **data})
    except Exception as e:
        logging.exception("load_user error")
        return JSONResponse({"found": False, "error": str(e)})


@router.post("/api/chat/history")
async def save_chat_history(payload: dict):
    """Save chat history to server for cross-device sync."""
    try:
        tg_id = payload.get("tg_id")
        history = payload.get("history", [])
        if not tg_id:
            return JSONResponse({"ok": False, "error": "no tg_id"})
        user = get_user(int(tg_id))
        if not user:
            return JSONResponse({"ok": False, "error": "user not found"})
        upsert_chat_history(user["id"], history)
        return JSONResponse({"ok": True})
    except Exception as e:
        logging.exception("save_chat_history error")
        return JSONResponse({"ok": False, "error": str(e)})
