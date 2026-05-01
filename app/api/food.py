import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import check_ai_quota
from bot.services.ai_service import calculate_food_macros, calculate_food_macros_from_photo

router = APIRouter()

_ALLOWED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_MAX_B64_LEN = 6_700_000   # ~5 MB image as base64
_MAX_TEXT_LEN = 2_000


class FoodRequest(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=_MAX_TEXT_LEN)]

    model_config = {"extra": "ignore"}


class PhotoRequest(BaseModel):
    image_b64:  Annotated[str, Field(min_length=1, max_length=_MAX_B64_LEN)]
    media_type: str = "image/jpeg"

    model_config = {"extra": "ignore"}


@router.post("/api/food")
async def food_calc(req: FoodRequest, tg_id: int = Depends(check_ai_quota)):
    try:
        result = await calculate_food_macros(req.text.strip())
        return JSONResponse(result)
    except Exception:
        logging.exception("food_calc error")
        return JSONResponse({"error": "Не удалось рассчитать КБЖУ"}, status_code=500)


@router.post("/api/food/photo")
async def food_from_photo(req: PhotoRequest, tg_id: int = Depends(check_ai_quota)):
    if req.media_type not in _ALLOWED_MEDIA_TYPES:
        return JSONResponse({"error": f"Неподдерживаемый тип файла. Разрешены: {', '.join(_ALLOWED_MEDIA_TYPES)}"}, status_code=400)
    try:
        result = await calculate_food_macros_from_photo(req.image_b64, req.media_type)
        return JSONResponse(result)
    except Exception:
        logging.exception("food_photo error")
        return JSONResponse({"error": "Не удалось распознать еду на фото"}, status_code=500)
