import logging
import re
from typing import Optional, Literal, Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.api.deps import get_current_tg_id
from db.queries import upsert_reminder, get_reminders_for_user, delete_reminder, get_user, get_reminder

router = APIRouter()

_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
_Label   = Annotated[str, Field(min_length=1, max_length=100)]


class ReminderRequest(BaseModel):
    type:         Literal["water", "meal", "log"]
    label:        Optional[_Label]            = None
    time:         Optional[str]               = Field(None, max_length=5)
    times:        Optional[list[str]]         = Field(None, max_length=10)
    labels:       Optional[list[_Label]]      = Field(None, max_length=10)
    interval_min: Optional[int]               = Field(None, ge=15, le=480)
    night_mode:   bool                        = True
    utc_offset:   int                         = Field(default=3, ge=-12, le=14)
    active:       bool                        = True

    model_config = {"extra": "ignore"}

    @field_validator("time")
    @classmethod
    def _validate_time(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _TIME_RE.match(v):
            raise ValueError("Время должно быть в формате ЧЧ:ММ")
        return v

    @field_validator("times")
    @classmethod
    def _validate_times(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None:
            for t in v:
                if not _TIME_RE.match(t):
                    raise ValueError(f"Неверный формат времени: {t!r} — ожидается ЧЧ:ММ")
        return v


@router.get("/api/reminders")
async def get_reminders(tg_id: int = Depends(get_current_tg_id)):
    user = get_user(tg_id)
    if not user:
        return JSONResponse({"reminders": []})
    return JSONResponse({"reminders": get_reminders_for_user(user["id"])})


@router.post("/api/reminders")
async def save_reminder(body: ReminderRequest, tg_id: int = Depends(get_current_tg_id)):
    user = get_user(tg_id)
    if not user:
        return JSONResponse({"ok": False, "error": "Пользователь не найден"}, status_code=404)

    result = upsert_reminder(user["id"], tg_id, body.model_dump())
    if not result:
        return JSONResponse({"ok": False, "error": "Ошибка сохранения"}, status_code=500)

    try:
        from bot.scheduler import schedule_reminder
        schedule_reminder(result)
    except Exception as e:
        logging.warning("schedule_reminder failed: %s", e)

    return JSONResponse({"ok": True, "reminder": result})


@router.delete("/api/reminders/{reminder_id}")
async def remove_reminder(reminder_id: str, tg_id: int = Depends(get_current_tg_id)):
    reminder = get_reminder(reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Напоминание не найдено")
    if reminder.get("tg_id") != tg_id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    try:
        from bot.scheduler import unschedule_reminder
        unschedule_reminder(reminder_id)
    except Exception as e:
        logging.warning("unschedule_reminder failed: %s", e)

    ok = delete_reminder(reminder_id)
    return JSONResponse({"ok": ok})
