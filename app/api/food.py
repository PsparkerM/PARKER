import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from bot.services.ai_service import calculate_food_macros

router = APIRouter()


class FoodRequest(BaseModel):
    text: str


@router.post("/api/food")
async def food_calc(req: FoodRequest):
    if not req.text.strip():
        return JSONResponse({"error": "Пустой запрос"}, status_code=400)
    try:
        result = await calculate_food_macros(req.text.strip())
        return JSONResponse(result)
    except Exception as e:
        logging.exception("food_calc error")
        return JSONResponse({"error": "Не удалось рассчитать КБЖУ"}, status_code=500)
