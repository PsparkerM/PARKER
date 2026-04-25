import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from bot.services.ai_service import generate_chat_response

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    profile: Optional[dict] = None
    lang: Optional[str] = "ru"


@router.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        history = [{"role": m.role, "content": m.content} for m in req.history]
        reply = await generate_chat_response(req.message, history, req.profile or {}, lang=req.lang or "ru")
        return JSONResponse({"reply": reply})
    except Exception as e:
        logging.exception("chat error")
        return JSONResponse({"reply": "Something went wrong, try again." if req.lang == "en" else "Что-то пошло не так, попробуй ещё раз."}, status_code=500)
