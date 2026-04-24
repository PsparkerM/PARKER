import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from bot.bot_instance import bot

router = APIRouter()


@router.post("/api/notify")
async def send_notification(payload: dict):
    tg_id = payload.get("tg_id")
    text = payload.get("text", "").strip()
    if not tg_id or not text:
        return JSONResponse({"ok": False, "error": "tg_id and text required"}, status_code=400)
    if len(text) > 4096:
        text = text[:4093] + "..."
    try:
        await bot.send_message(chat_id=int(tg_id), text=text)
        return JSONResponse({"ok": True})
    except Exception as e:
        logging.warning("notify error tg_id=%s: %s", tg_id, e)
        return JSONResponse({"ok": False, "error": str(e)})
