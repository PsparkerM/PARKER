import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from bot.services.ai_service import calculate_food_macros, calculate_food_macros_from_photo

router = APIRouter()


class FoodRequest(BaseModel):
    text: str


class PhotoRequest(BaseModel):
    image_b64: str          # base64-encoded image
    media_type: str = "image/jpeg"


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


@router.post("/api/food/photo")
async def food_from_photo(req: PhotoRequest):
    if not req.image_b64:
        return JSONResponse({"error": "Нет изображения"}, status_code=400)
    try:
        result = await calculate_food_macros_from_photo(req.image_b64, req.media_type)
        return JSONResponse(result)
    except Exception as e:
        logging.exception("food_photo error")
        return JSONResponse({"error": "Не удалось распознать еду на фото"}, status_code=500)
