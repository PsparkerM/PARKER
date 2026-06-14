import asyncio
import logging
import re
from typing import Optional, Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, AfterValidator

from app.api.deps import get_current_tg_id
from db.queries import get_user, save_user_logs, get_user_logs, upsert_daily_logs

router = APIRouter()


def _daily_rows_from(merged: dict) -> list[dict]:
    """Assemble normalized per-day rows from the merged blob for daily_logs."""
    by_date: dict[str, dict] = {}

    def row(d):
        return by_date.setdefault(d, {"log_date": d})

    for e in merged.get("weight_logs") or []:
        d = e.get("date")
        if not d:
            continue
        r = row(d)
        if e.get("weight") is not None: r["weight_kg"]   = e["weight"]
        if e.get("sleep")  is not None: r["sleep_hours"] = e["sleep"]
    for e in merged.get("meas_logs") or []:
        d = e.get("date")
        if not d:
            continue
        r = row(d)
        for src, dst in (("waist", "waist_cm"), ("hips", "hips_cm"), ("chest", "chest_cm"),
                         ("thigh", "thigh_cm"), ("arm", "arm_cm")):
            if e.get(src) is not None:
                r[dst] = e[src]
    for e in merged.get("water") or []:
        if e.get("date") and e.get("ml"):
            row(e["date"])["water_ml"] = e["ml"]
    for e in merged.get("steps") or []:
        if e.get("date") and e.get("steps"):
            row(e["date"])["steps"] = e["steps"]

    # Only rows with at least one metric beyond log_date.
    rows = [r for r in by_date.values() if len(r) > 1]
    rows.sort(key=lambda r: r["log_date"])
    return rows[-365:]

_MAX_ENTRIES = 1_000
_MAX_TOMBSTONES = 1_000


def _merge_logs(existing: dict, incoming: dict) -> dict:
    """Server-side union merge so concurrent devices accumulate instead of
    overwriting, and deletions (tombstones) propagate instead of resurrecting.

    - food: union by `ts` (fallback date|text), minus deleted_food set
    - weight_logs / meas_logs: merge by `date`, newer non-null fields win
    - water / steps: by `date`, larger value wins
    - deleted_food: union of both sides (capped)
    """
    existing = existing or {}
    incoming = incoming or {}

    deleted = set(existing.get("deleted_food") or []) | set(incoming.get("deleted_food") or [])

    def _food_key(e):
        ts = e.get("ts")
        return ts if ts is not None else f"{e.get('date','')}|{e.get('text') or e.get('description') or e.get('name') or ''}"

    food = {}
    for src in (existing.get("food") or [], incoming.get("food") or []):
        for e in src:
            food[_food_key(e)] = e
    food_list = [e for e in food.values() if e.get("ts") not in deleted]
    food_list.sort(key=lambda e: e.get("ts") or 0)

    def _merge_by_date(key):
        acc = {}
        for src in (existing.get(key) or [], incoming.get(key) or []):
            for e in src:
                d = e.get("date")
                if not d:
                    continue
                cur = acc.get(d, {})
                merged = dict(cur)
                for k, v in e.items():
                    if v is not None:
                        merged[k] = v
                acc[d] = merged
        return sorted(acc.values(), key=lambda e: e.get("date", ""))

    def _merge_max(key, field):
        acc = {}
        for src in (existing.get(key) or [], incoming.get(key) or []):
            for e in src:
                d = e.get("date")
                if not d:
                    continue
                acc[d] = max(acc.get(d, 0), e.get(field, 0) or 0)
        return [{"date": d, field: v} for d, v in sorted(acc.items())]

    return {
        "food":        food_list[-_MAX_ENTRIES:],
        "weight_logs": _merge_by_date("weight_logs")[-_MAX_ENTRIES:],
        "meas_logs":   _merge_by_date("meas_logs")[-_MAX_ENTRIES:],
        "water":       _merge_max("water", "ml")[-365:],
        "steps":       _merge_max("steps", "steps")[-365:],
        "deleted_food": sorted(deleted)[-_MAX_TOMBSTONES:],
    }
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
    food:         list[FoodLogEntry]    = Field(default=[], max_length=_MAX_ENTRIES)
    weight_logs:  list[WeightLogEntry]  = Field(default=[], max_length=_MAX_ENTRIES)
    meas_logs:    list[MeasLogEntry]    = Field(default=[], max_length=_MAX_ENTRIES)
    water:        list[WaterEntry]      = Field(default=[], max_length=365)
    steps:        list[StepsEntry]      = Field(default=[], max_length=365)
    deleted_food: list[int]             = Field(default=[], max_length=_MAX_TOMBSTONES)

    model_config = {"extra": "ignore"}


@router.post("/api/logs")
async def save_logs(body: LogsRequest, tg_id: int = Depends(get_current_tg_id)):
    try:
        user = await asyncio.to_thread(get_user, tg_id)
        if not user:
            return JSONResponse({"ok": False, "error": "Пользователь не найден"})
        # Union-merge with what's already stored so multiple devices accumulate
        # and deletions propagate, instead of last-write-wins overwrite.
        existing = await asyncio.to_thread(get_user_logs, user["id"])
        merged = _merge_logs(existing, body.model_dump())
        await asyncio.to_thread(save_user_logs, user["id"], merged)
        # Dual-write to normalized daily_logs (best-effort; never affects the blob).
        try:
            await asyncio.to_thread(upsert_daily_logs, user["id"], _daily_rows_from(merged))
        except Exception:
            logging.warning("daily_logs dual-write skipped", exc_info=True)
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
