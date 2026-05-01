import hmac
import logging
from typing import Annotated

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from bot.bot_instance import bot
from bot.config import ADMIN_SECRET

router = APIRouter()

_MAX_TEXT = 4_096


class NotifyRequest(BaseModel):
    secret: str
    tg_id:  int  = Field(..., ge=1)
    text:   Annotated[str, Field(min_length=1, max_length=_MAX_TEXT)]

    model_config = {"extra": "ignore"}


@router.post("/api/notify")
async def send_notification(body: NotifyRequest):
    if not ADMIN_SECRET or not hmac.compare_digest(body.secret, ADMIN_SECRET):
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
    try:
        await bot.send_message(chat_id=body.tg_id, text=body.text)
        return JSONResponse({"ok": True})
    except Exception as e:
        logging.warning("notify error tg_id=%s: %s", body.tg_id, e)
        return JSONResponse({"ok": False, "error": "Не удалось отправить сообщение"})
