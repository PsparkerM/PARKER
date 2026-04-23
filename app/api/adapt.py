import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from bot.services.ai_service import generate_weekly_adaptation

router = APIRouter()


class AdaptRequest(BaseModel):
    profile: dict
    logs: list         # weight/sleep/water entries
    food_logs: list    # food entries
    current_macros: Optional[dict] = None


@router.post("/api/adapt")
async def adapt_plan(req: AdaptRequest):
    try:
        result = await generate_weekly_adaptation(
            req.profile, req.logs, req.food_logs, req.current_macros or {}
        )
        return JSONResponse(result)
    except Exception as e:
        logging.exception("adapt error")
        return JSONResponse({"error": "Не удалось сформировать рекомендации"}, status_code=500)
