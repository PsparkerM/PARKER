import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from bot.utils.calculators import compute_macros_for_profile
from bot.services.ai_service import generate_nutrition_plan, generate_workout_plan
from db.queries import upsert_user, save_plan

router = APIRouter()

REQUIRED_FIELDS = ["gender", "age", "height_cm", "weight_kg"]


@router.post("/api/profile")
async def create_profile(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Невалидный JSON")

    for field in REQUIRED_FIELDS:
        if field not in data:
            raise HTTPException(status_code=400, detail=f"Отсутствует поле: {field}")

    # Defaults for optional fields
    data.setdefault("goal", "maintain")
    data.setdefault("schedule", "standard")
    data.setdefault("health_issues", [])
    data.setdefault("equipment", ["gym"])

    try:
        macros = compute_macros_for_profile(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка расчёта КБЖУ: {e}")

    nutrition_plan, workout_plan = await _generate_plans(data, macros)

    tg_id = data.get("tg_id")
    if tg_id:
        user = upsert_user(int(tg_id), data)
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
