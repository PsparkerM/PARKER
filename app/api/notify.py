import hmac
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import get_current_tg_id
from bot.bot_instance import bot
from bot.config import ADMIN_SECRET

router = APIRouter()

_MAX_TEXT = 4_096

_TEST_MSG = (
    "⚡ P.A.R.K.E.R. — тестовое напоминание!\n\n"
    "💧 Выпей воды\n"
    "🥗 Запиши приём пищи\n"
    "⚖️ Взвешивание работает!\n\n"
    "Напоминания настроены корректно ✓"
)

_TYPE_MESSAGES = {
    "food":       "🍽 Время покушать!\n\nЭто как будет выглядеть твоё напоминание о приёме пищи.\nНе забудь записать что съел в трекер.",
    "water":      "💧 Пора выпить воды!\n\nЭто пример напоминания о воде. Норма — 30 мл на кг веса.",
    "log":        "📏 Время взвешивания и замеров!\n\nЗапиши данные в трекер — Арни увидит динамику и подскажет если что-то не так.",
    "workout":    "💪 Пора тренироваться!\n\nЭто пример напоминания о тренировке. Открой план дня и вперёд.",
    "motivation": "🔥 Привет от Арни!\n\nКаждый день — шаг вперёд. Не сравнивай себя со вчерашним собой — побеждай сегодняшнего.",
}


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


@router.post("/api/notify/test")
async def send_test_notification(
    type: Optional[str] = None,
    tg_id: int = Depends(get_current_tg_id),
):
    """Any authenticated user can send themselves a test reminder.
    Optional `?type=<food|water|log|workout|motivation>` sends a type-specific preview."""
    text = _TYPE_MESSAGES.get((type or "").lower(), _TEST_MSG)
    try:
        await bot.send_message(chat_id=tg_id, text=text)
        return JSONResponse({"ok": True})
    except Exception as e:
        logging.warning("test notify error tg_id=%s: %s", tg_id, e)
        return JSONResponse({"ok": False, "error": "Не удалось отправить — убедись что бот не заблокирован"})
