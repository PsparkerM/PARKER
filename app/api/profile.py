import logging
from typing import Optional, Annotated
from enum import Enum

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import check_ai_quota, get_current_tg_id, get_client_ip
from app.middleware.rate_limit import ip_limiter
from bot.utils.calculators import compute_macros_for_profile
from bot.services.ai_service import generate_nutrition_plan, generate_workout_plan
from db.queries import upsert_user, save_plan

router = APIRouter()


class GenderEnum(str, Enum):
    male   = "male"
    female = "female"


class GoalEnum(str, Enum):
    lose_weight   = "lose_weight"
    gain_muscle   = "gain_muscle"
    maintain      = "maintain"
    recomposition = "recomposition"


class ScheduleEnum(str, Enum):
    standard   = "standard"
    twelve_h   = "12h"
    sixteen_h  = "16h+"
    shift      = "shift"


class HealthIssue(str, Enum):
    none           = "none"
    back_problems  = "back_problems"
    knee_issues    = "knee_issues"
    hypertension   = "hypertension"


class Equipment(str, Enum):
    none      = "none"
    dumbbells = "dumbbells"
    barbell   = "barbell"
    gym       = "gym"
    pool      = "pool"


class ProfileRequest(BaseModel):
    gender:      GenderEnum
    age:         int   = Field(..., ge=10,  le=100)
    height_cm:   int   = Field(..., ge=100, le=250)
    weight_kg:   float = Field(..., ge=30,  le=300)
    goal:        GoalEnum    = GoalEnum.maintain
    schedule:    ScheduleEnum = ScheduleEnum.standard
    health_issues: list[HealthIssue]  = Field(default=[], max_length=10)
    equipment:     list[Equipment]    = Field(default=[Equipment.gym], max_length=10)
    body_fat_pct:  Optional[float]    = Field(None, ge=3,  le=60)
    waist_cm:      Optional[float]    = Field(None, ge=40, le=200)
    hips_cm:       Optional[float]    = Field(None, ge=40, le=200)
    chest_cm:      Optional[float]    = Field(None, ge=40, le=200)
    thigh_cm:      Optional[float]    = Field(None, ge=40, le=200)
    name:          Optional[Annotated[str, Field(max_length=100)]] = None

    model_config = {"extra": "ignore"}


@router.post("/api/profile")
async def create_profile(
    request: Request,
    body: ProfileRequest,
    tg_id: int = Depends(get_current_tg_id),
):
    # 50 onboarding submissions per IP per hour (office/team usage)
    ip = get_client_ip(request)
    if not await ip_limiter.is_allowed(f"register:{ip}", 50, 3600):
        raise HTTPException(
            status_code=429,
            detail="Слишком много попыток регистрации. Попробуй через час.",
            headers={"Retry-After": "3600"},
        )

    data = body.model_dump()

    try:
        macros = compute_macros_for_profile(data)
    except Exception:
        logging.exception("compute_macros error")
        raise HTTPException(status_code=400, detail="Ошибка расчёта КБЖУ")

    nutrition_plan, workout_plan = await _generate_plans(data, macros)

    user = upsert_user(tg_id, data)
    if user:
        uid = user.get("id")
        save_plan(uid, "nutrition", nutrition_plan, macros)
        save_plan(uid, "workout", workout_plan, {})

    return JSONResponse({
        "macros":         macros,
        "nutrition_plan": nutrition_plan,
        "workout_plan":   workout_plan,
    })


async def _generate_plans(data: dict, macros: dict):
    import asyncio
    nutrition, workout = await asyncio.gather(
        generate_nutrition_plan(data, macros),
        generate_workout_plan(data),
    )
    return nutrition, workout
