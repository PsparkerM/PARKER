import asyncio
import json
import logging
import re
from typing import Optional, Literal, Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import check_ai_quota, spawn_bg
from bot.services.ai_service import generate_chat_response, stream_chat_response, summarize_chat_history
from db.queries import (
    get_user, update_plan_macros, get_user_logs,
    get_chat_history, get_chat_summary, upsert_chat_summary,
)

_SUMMARIZE_THRESHOLD = 30      # начинаем сжимать когда история перевалила за 30 сообщений
_SUMMARIZE_LEAVE_LAST = 10     # сжимаем всё кроме последних 10 — они идут в API как живой контекст
_SUMMARIZE_FRESH_DELTA = 6     # если с прошлого summary прибавилось < 6 сообщений — не пересжимаем

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


async def _load_summary_text(user_id: str | None) -> str:
    if not user_id:
        return ""
    summary_row = await asyncio.to_thread(get_chat_summary, user_id)
    return (summary_row or {}).get("summary", "") if summary_row else ""


async def _maybe_refresh_summary(user_id: str, full_history: list, lang: str) -> None:
    """Background-friendly: re-summarize if history has grown enough since last summary."""
    if not user_id or len(full_history) <= _SUMMARIZE_THRESHOLD:
        return
    try:
        existing = await asyncio.to_thread(get_chat_summary, user_id)
        covered = (existing or {}).get("covered_count", 0)
        to_summarize_count = len(full_history) - _SUMMARIZE_LEAVE_LAST
        if to_summarize_count <= 0:
            return
        if covered and to_summarize_count - covered < _SUMMARIZE_FRESH_DELTA:
            return
        old_part = full_history[:to_summarize_count]
        summary = await summarize_chat_history(old_part, lang)
        if summary:
            await asyncio.to_thread(upsert_chat_summary, user_id, summary, to_summarize_count)
    except Exception:
        logging.exception("background summary refresh failed")


@router.post("/api/chat")
async def chat(req: ChatRequest, tg_id: int = Depends(check_ai_quota)):
    try:
        profile = await asyncio.to_thread(get_user, tg_id) or {}
        uid = profile.get("id")
        logs: dict = {}
        summary_text = ""
        if uid:
            try:
                logs = await asyncio.to_thread(get_user_logs, uid)
            except Exception:
                pass
            summary_text = await _load_summary_text(uid)

        history = [{"role": m.role, "content": m.content} for m in req.history]
        reply   = await generate_chat_response(
            req.message, history, profile,
            lang=req.lang or "ru", logs=logs,
            image_b64=req.image_b64, media_type=req.media_type or "image/jpeg",
            chat_summary=summary_text or None,
        )

        clean_reply, new_macros = _parse_set_targets(reply)

        if new_macros and uid:
            try:
                await asyncio.to_thread(update_plan_macros, uid, new_macros)
            except Exception:
                logging.warning("Failed to persist SET_TARGETS macros for tg_id=%s", tg_id)

        if uid:
            full_hist = history + [
                {"role": "user", "content": req.message},
                {"role": "assistant", "content": clean_reply},
            ]
            spawn_bg(_maybe_refresh_summary(uid, full_hist, req.lang or "ru"))

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


@router.post("/api/chat/stream")
async def chat_stream(req: ChatRequest, tg_id: int = Depends(check_ai_quota)):
    """Server-Sent Events stream of Arni's reply, token by token."""
    profile = await asyncio.to_thread(get_user, tg_id) or {}
    uid = profile.get("id")
    logs: dict = {}
    summary_text = ""
    if uid:
        try:
            logs = await asyncio.to_thread(get_user_logs, uid)
        except Exception:
            pass
        summary_text = await _load_summary_text(uid)
    history = [{"role": m.role, "content": m.content} for m in req.history]
    lang = req.lang or "ru"

    async def event_source():
        try:
            async for event_type, payload in stream_chat_response(
                req.message, history, profile,
                lang=lang, logs=logs,
                image_b64=req.image_b64, media_type=req.media_type or "image/jpeg",
                chat_summary=summary_text or None,
            ):
                if event_type == "chunk":
                    yield f"data: {json.dumps({'chunk': payload}, ensure_ascii=False)}\n\n"
                elif event_type == "error":
                    yield f"data: {json.dumps({'error': payload}, ensure_ascii=False)}\n\n"
                    return
                elif event_type == "done":
                    clean_reply, new_macros = _parse_set_targets(payload)
                    if new_macros and uid:
                        try:
                            await asyncio.to_thread(update_plan_macros, uid, new_macros)
                        except Exception:
                            logging.warning("Failed to persist SET_TARGETS for tg_id=%s", tg_id)
                    if uid:
                        full_hist = history + [
                            {"role": "user", "content": req.message},
                            {"role": "assistant", "content": clean_reply},
                        ]
                        spawn_bg(_maybe_refresh_summary(uid, full_hist, lang))
                    done = {"done": True, "reply": clean_reply}
                    if new_macros:
                        done["macros_updated"] = new_macros
                    yield f"data: {json.dumps(done, ensure_ascii=False)}\n\n"
        except Exception:
            logging.exception("chat_stream error")
            yield f"data: {json.dumps({'error': 'stream failed'})}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
