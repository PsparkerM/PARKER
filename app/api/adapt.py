import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.api.deps import check_ai_quota
from bot.services.ai_service import generate_weekly_adaptation
from db.queries import get_user, get_user_logs, get_user_with_plans

router = APIRouter()


@router.post("/api/adapt")
async def adapt_plan(tg_id: int = Depends(check_ai_quota)):
    """Weekly plan adaptation — all data loaded from DB, nothing trusted from client."""
    try:
        user = get_user(tg_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        logs_data = get_user_logs(user["id"])
        weight_logs = logs_data.get("weight_logs", [])
        food_logs   = logs_data.get("food", [])

        user_with_plans = get_user_with_plans(tg_id)
        macros = user_with_plans.get("macros", {}) if user_with_plans else {}

        result = await generate_weekly_adaptation(user, weight_logs, food_logs, macros)
        return JSONResponse(result)
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("adapt error")
        return JSONResponse({"error": "Не удалось сформировать рекомендации"}, status_code=500)
