import logging
from typing import Optional, Literal, Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import check_ai_quota
from bot.services.ai_service import generate_chat_response
from db.queries import get_user

router = APIRouter()

_MAX_MSG_LEN  = 10_000
_MAX_HIST_LEN = 100


class ChatMessage(BaseModel):
    role:    Literal["user", "assistant"]
    content: Annotated[str, Field(max_length=_MAX_MSG_LEN)]

    model_config = {"extra": "ignore"}


class ChatRequest(BaseModel):
    message: Annotated[str, Field(min_length=1, max_length=_MAX_MSG_LEN)]
    history: list[ChatMessage] = Field(default=[], max_length=_MAX_HIST_LEN)
    lang:    Optional[Literal["ru", "en"]] = "ru"

    model_config = {"extra": "ignore"}


@router.post("/api/chat")
async def chat(req: ChatRequest, tg_id: int = Depends(check_ai_quota)):
    try:
        profile = get_user(tg_id) or {}
        history = [{"role": m.role, "content": m.content} for m in req.history]
        reply = await generate_chat_response(req.message, history, profile, lang=req.lang or "ru")
        return JSONResponse({"reply": reply})
    except Exception:
        logging.exception("chat error")
        return JSONResponse(
            {"reply": "Что-то пошло не так, попробуй ещё раз." if req.lang != "en" else "Something went wrong, try again."},
            status_code=500,
        )
