import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import check_ai_quota, get_current_tg_id
from bot.services.ai_service import generate_weekly_adaptation
from bot.utils.calculators import CALORIE_FLOOR
from db.queries import get_user, get_user_logs, get_user_with_plans, update_plan_macros

router = APIRouter()


def _propose_macros(current: dict, calorie_adjust: int, gender: str) -> dict | None:
    """New macros from a signed calorie delta.

    Keeps protein and fat stable (don't sacrifice protein on a cut) and routes
    the calorie change into carbs. Clamped to the safe calorie floor.
    """
    cur_cal = current.get("calories")
    if not cur_cal or not calorie_adjust:
        return None
    floor = CALORIE_FLOOR.get(gender, 1200)
    new_cal = max(floor, int(cur_cal) + int(calorie_adjust))
    delta = new_cal - int(cur_cal)
    if delta == 0:
        return None
    protein = int(current.get("protein_g", 0))
    fat = int(current.get("fat_g", 0))
    carb = max(0, int(current.get("carb_g", 0)) + round(delta / 4))
    return {"calories": new_cal, "protein_g": protein, "fat_g": fat, "carb_g": carb}


@router.post("/api/adapt")
async def adapt_plan(tg_id: int = Depends(check_ai_quota)):
    """Weekly plan adaptation — all data loaded from DB, nothing trusted from client."""
    try:
        user = await asyncio.to_thread(get_user, tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        logs_data, user_with_plans = await asyncio.gather(
            asyncio.to_thread(get_user_logs, user["id"]),
            asyncio.to_thread(get_user_with_plans, tg_id),
        )
        weight_logs = logs_data.get("weight_logs", [])
        food_logs   = logs_data.get("food", [])
        macros      = user_with_plans.get("macros", {}) if user_with_plans else {}

        result = await generate_weekly_adaptation(user, weight_logs, food_logs, macros)

        # Предложить новые цели, чтобы их можно было применить в один тап.
        proposed = _propose_macros(macros, result.get("calorie_adjust", 0), user.get("gender", "male"))
        if proposed:
            result["current_macros"] = macros
            result["new_macros"] = proposed
        return JSONResponse(result)
    except HTTPException:
        raise
    except Exception:
        logging.exception("adapt error")
        return JSONResponse({"error": "Не удалось сформировать рекомендации"}, status_code=500)


class ApplyMacros(BaseModel):
    calories:  Annotated[int, Field(ge=1000, le=6000)]
    protein_g: Annotated[int, Field(ge=0,    le=500)]
    fat_g:     Annotated[int, Field(ge=0,    le=400)]
    carb_g:    Annotated[int, Field(ge=0,    le=900)]

    model_config = {"extra": "ignore"}


@router.post("/api/adapt/apply")
async def apply_adaptation(body: ApplyMacros, tg_id: int = Depends(get_current_tg_id)):
    """Persist adaptation-proposed macros as the new nutrition targets."""
    try:
        user = await asyncio.to_thread(get_user, tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        macros = body.model_dump()
        ok = await asyncio.to_thread(update_plan_macros, user["id"], macros)
        if not ok:
            return JSONResponse({"ok": False, "error": "Нет активного плана"}, status_code=404)
        return JSONResponse({"ok": True, "macros": macros})
    except HTTPException:
        raise
    except Exception:
        logging.exception("apply_adaptation error")
        return JSONResponse({"ok": False, "error": "Не удалось применить"}, status_code=500)
