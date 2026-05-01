import logging
from typing import Optional, Literal, Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import get_current_tg_id
from db.queries import get_user_with_plans, upsert_chat_history, get_user, update_user_fields

router = APIRouter()

_PROFILE_PUBLIC_FIELDS = {
    "tg_id", "name", "goal", "gender", "age", "height_cm", "weight_kg",
    "body_fat_pct", "waist_cm", "hips_cm", "chest_cm", "thigh_cm",
    "schedule", "health_issues", "equipment", "status",
    "avatar", "avatar_data", "badge", "created_at", "updated_at",
}

_MAX_AVATAR_DATA = 5_000_000   # ~3.75 MB image as base64


class UserUpdateRequest(BaseModel):
    name:        Optional[Annotated[str, Field(min_length=1, max_length=100)]] = None
    avatar:      Optional[Annotated[str, Field(max_length=10)]] = None   # single emoji
    avatar_data: Optional[Annotated[str, Field(max_length=_MAX_AVATAR_DATA)]] = None

    model_config = {"extra": "ignore"}


class HistoryMessage(BaseModel):
    role:    Literal["user", "assistant"]
    content: Annotated[str, Field(max_length=10_000)]

    model_config = {"extra": "ignore"}


class ChatHistoryRequest(BaseModel):
    history: list[HistoryMessage] = Field(default=[], max_length=100)

    model_config = {"extra": "ignore"}


@router.get("/api/user")
async def load_user(tg_id: int = Depends(get_current_tg_id)):
    try:
        data = get_user_with_plans(tg_id)
        if not data:
            return JSONResponse({"found": False})
        if isinstance(data.get("profile"), dict):
            data["profile"] = {k: v for k, v in data["profile"].items() if k in _PROFILE_PUBLIC_FIELDS}
        return JSONResponse({"found": True, **data})
    except Exception:
        logging.exception("load_user error")
        return JSONResponse({"found": False, "error": "Не удалось загрузить профиль"})


@router.post("/api/user/update")
async def update_user_data(body: UserUpdateRequest, tg_id: int = Depends(get_current_tg_id)):
    try:
        fields = body.model_dump(exclude_none=True)
        if not fields:
            return JSONResponse({"ok": False, "error": "Нет данных для обновления"})
        ok = update_user_fields(tg_id, fields)
        return JSONResponse({"ok": ok})
    except Exception:
        logging.exception("update_user_data error")
        return JSONResponse({"ok": False, "error": "Не удалось обновить профиль"})


@router.post("/api/chat/history")
async def save_chat_history(body: ChatHistoryRequest, tg_id: int = Depends(get_current_tg_id)):
    try:
        user = get_user(tg_id)
        if not user:
            return JSONResponse({"ok": False, "error": "Пользователь не найден"})
        history = [{"role": m.role, "content": m.content} for m in body.history]
        upsert_chat_history(user["id"], history)
        return JSONResponse({"ok": True})
    except Exception:
        logging.exception("save_chat_history error")
        return JSONResponse({"ok": False, "error": "Не удалось сохранить историю"})
