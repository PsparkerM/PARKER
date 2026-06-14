"""In-app покупка Pro через Telegram Stars (tg.openInvoice).

Создаёт invoice-ссылку тем же форматом payload, что и бот, поэтому оплата
прилетает в существующий successful_payment-хендлер и активирует подписку.
"""
import logging
from typing import Literal

from aiogram.types import LabeledPrice
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import get_current_tg_id
from bot.bot_instance import bot

router = APIRouter()
logger = logging.getLogger(__name__)

# Должно совпадать с bot/handlers/payment.py
_PLANS = {
    "monthly": (299,  "P.A.R.K.E.R. Pro — 1 месяц",
                "50 AI-запросов в день, чат с Арни без лимитов, адаптация плана"),
    "annual":  (2990, "P.A.R.K.E.R. Pro — 1 год",
                "50 AI-запросов в день на целый год. Экономия 17% против месячной"),
}


class InvoiceRequest(BaseModel):
    plan: Literal["monthly", "annual"] = "monthly"
    model_config = {"extra": "ignore"}


@router.post("/api/subscribe/invoice")
async def create_invoice(body: InvoiceRequest, tg_id: int = Depends(get_current_tg_id)):
    stars, title, description = _PLANS[body.plan]
    try:
        link = await bot.create_invoice_link(
            title=title,
            description=description,
            payload=f"parker_pro_{body.plan}_{tg_id}",
            currency="XTR",
            prices=[LabeledPrice(label=title, amount=stars)],
            provider_token="",
        )
        return JSONResponse({"url": link})
    except Exception:
        logger.exception("create_invoice failed tg_id=%s plan=%s", tg_id, body.plan)
        return JSONResponse({"error": "Не удалось создать счёт"}, status_code=502)
