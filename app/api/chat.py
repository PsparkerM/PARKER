import asyncio
import logging
import re
from typing import Optional, Literal, Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import check_ai_quota
from bot.services.ai_service import generate_chat_response
from db.queries import get_user, update_plan_macros, get_user_logs

router = APIRouter()

_MAX_MSG_LEN  = 10_000
_MAX_HIST_LEN = 100

# Matches {{SET_TARGETS:calories=2500,protein=180,fat=70,carbs=250}}
_SET_TARGETS_RE = re.compile(r'\{\{SET_TARGETS:([^}]+)\}\}', re.IGNORECASE)


def _parse_set_targets(reply: str) -> tuple[str, dict | None]:
    """Extract {{SET_TARGETS:...}} command from Arni's reply.

    Returns (clean_reply_without_command, new_macros_dict_or_None).
    Strips the raw command string so users never see it in the chat.
    """
    m = _SET_TARGETS_RE.search(reply)
    if not m:
        return reply, None

    macros: dict[str, int] = {}
    for part in m.group(1).split(","):
        key, _, val = part.partition("=")
        try:
            macros[key.strip()] = int(val.strip())
        except ValueError:
            pass

    if "calories" not in macros:
        return _SET_TARGETS_RE.sub("", reply).strip(), None

    db_macros = {
        "calories":  macros.get("calories"),
        "protein_g": macros.get("protein"),
        "fat_g":     macros.get("fat"),
        "carb_g":    macros.get("carbs"),
    }
    # Remove None values so we don't overwrite existing fields with null
    db_macros = {k: v for k, v in db_macros.items() if v is not None}

    clean = _SET_TARGETS_RE.sub("", reply).strip()
    return clean, db_macros


class ChatMessage(BaseModel):
    role:    Literal["user", "assistant"]
    content: Annotated[str, Field(max_length=_MAX_MSG_LEN)]

    model_config = {"extra": "ignore"}


class ChatRequest(BaseModel):
    message:    Annotated[str, Field(min_length=1, max_length=_MAX_MSG_LEN)]
    history:    list[ChatMessage] = Field(default=[], max_length=_MAX_HIST_LEN)
    lang:       Optional[Literal["ru", "en"]] = "ru"
    image_b64:  Optional[str] = Field(None, max_length=5_000_000)
    media_type: Optional[str] = Field(None, max_length=30)

    model_config = {"extra": "ignore"}


@router.post("/api/chat")
async def chat(req: ChatRequest, tg_id: int = Depends(check_ai_quota)):
    try:
        profile = await asyncio.to_thread(get_user, tg_id) or {}
        logs: dict = {}
        if profile.get("id"):
            try:
                logs = await asyncio.to_thread(get_user_logs, profile["id"])
            except Exception:
                pass
        history = [{"role": m.role, "content": m.content} for m in req.history]
        reply   = await generate_chat_response(
            req.message, history, profile,
            lang=req.lang or "ru", logs=logs,
            image_b64=req.image_b64, media_type=req.media_type or "image/jpeg",
        )

        clean_reply, new_macros = _parse_set_targets(reply)

        if new_macros and profile.get("id"):
            try:
                await asyncio.to_thread(update_plan_macros, profile["id"], new_macros)
            except Exception:
                logging.warning("Failed to persist SET_TARGETS macros for tg_id=%s", tg_id)

        response: dict = {"reply": clean_reply}
        if new_macros:
            response["macros_updated"] = new_macros

        return JSONResponse(response)
    except Exception:
        logging.exception("chat error")
        return JSONResponse(
            {"reply": "Что-то пошло не так, попробуй ещё раз." if req.lang != "en" else "Something went wrong, try again."},
            status_code=500,
        )
