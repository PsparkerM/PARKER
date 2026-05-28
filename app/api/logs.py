import asyncio
import logging
import re
from typing import Optional, Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, AfterValidator

from app.api.deps import get_current_tg_id
from db.queries import get_user, save_user_logs, get_user_logs

router = APIRouter()

_MAX_ENTRIES = 1_000
_DATE_RE = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$")


def _validate_date(v: str) -> str:
    if not _DATE_RE.match(v):
        raise ValueError("Дата должна быть в формате YYYY-MM-DD")
    return v


_DateStr = Annotated[str, Field(max_length=10), AfterValidator(_validate_date)]


class MacroTotals(BaseModel):
    calories:  float = Field(ge=0, le=10_000)
    protein_g: float = Field(ge=0, le=500)
    fat_g:     float = Field(ge=0, le=500)
    carb_g:    float = Field(ge=0, le=1_000)

    model_config = {"extra": "ignore"}


class FoodItem(BaseModel):
    description: Optional[Annotated[str, Field(max_length=500)]] = None
    calories:  float = Field(ge=0, le=10_000)
    protein_g: float = Field(ge=0, le=500)
    fat_g:     float = Field(ge=0, le=500)
    carb_g:    float = Field(ge=0, le=1_000)

    model_config = {"extra": "ignore"}


class FoodLogEntry(BaseModel):
    ts:          Optional[int]            = Field(None, ge=0)
    date:        _DateStr
    text:        Optional[Annotated[str, Field(max_length=500)]] = None
    description: Optional[Annotated[str, Field(max_length=500)]] = None
    name:        Optional[Annotated[str, Field(max_length=500)]] = None
    items:       list[FoodItem]           = Field(default=[], max_length=50)
    total:       Optional[MacroTotals]    = None

    model_config = {"extra": "ignore"}


class WeightLogEntry(BaseModel):
    date:   _DateStr
    ts:     Optional[int]   = Field(None, ge=0)
    weight: Optional[float] = Field(None, ge=20,  le=400)
    sleep:  Optional[float] = Field(None, ge=0,   le=24)

    model_config = {"extra": "ignore"}


class MeasLogEntry(BaseModel):
    date:  _DateStr
    waist: Optional[float] = Field(None, ge=40, le=200)
    hips:  Optional[float] = Field(None, ge=40, le=200)
    chest: Optional[float] = Field(None, ge=40, le=200)
    thigh: Optional[float] = Field(None, ge=40, le=200)
    arm:   Optional[float] = Field(None, ge=10, le=100)

    model_config = {"extra": "ignore"}


class WaterEntry(BaseModel):
    date: _DateStr
    ml:   int = Field(ge=0, le=10_000)

    model_config = {"extra": "ignore"}


class StepsEntry(BaseModel):
    date:  _DateStr
    steps: int = Field(ge=0, le=100_000)

    model_config = {"extra": "ignore"}


class LogsRequest(BaseModel):
    food:        list[FoodLogEntry]    = Field(default=[], max_length=_MAX_ENTRIES)
    weight_logs: list[WeightLogEntry]  = Field(default=[], max_length=_MAX_ENTRIES)
    meas_logs:   list[MeasLogEntry]    = Field(default=[], max_length=_MAX_ENTRIES)
    water:       list[WaterEntry]      = Field(default=[], max_length=365)
    steps:       list[StepsEntry]      = Field(default=[], max_length=365)

    model_config = {"extra": "ignore"}


@router.post("/api/logs")
async def save_logs(body: LogsRequest, tg_id: int = Depends(get_current_tg_id)):
    try:
        user = await asyncio.to_thread(get_user, tg_id)
        if not user:
            return JSONResponse({"ok": False, "error": "Пользователь не найден"})
        await asyncio.to_thread(save_user_logs, user["id"], body.model_dump())
        return JSONResponse({"ok": True})
    except Exception:
        logging.exception("save_logs error")
        return JSONResponse({"ok": False, "error": "Не удалось сохранить данные"})


@router.get("/api/logs")
async def load_logs(tg_id: int = Depends(get_current_tg_id)):
    try:
        user = await asyncio.to_thread(get_user, tg_id)
        if not user:
            return JSONResponse({"found": False})
        data = await asyncio.to_thread(get_user_logs, user["id"])
        return JSONResponse({"found": True, **data})
    except Exception:
        logging.exception("load_logs error")
        return JSONResponse({"found": False, "error": "Не удалось загрузить данные"})
