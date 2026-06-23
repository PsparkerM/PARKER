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
from bot.config import SUB_PLANS   # единый источник цен (см. bot/config.py)

router = APIRouter()
logger = logging.getLogger(__name__)


class InvoiceRequest(BaseModel):
    plan: Literal["monthly", "annual"] = "monthly"
    model_config = {"extra": "ignore"}


@router.post("/api/subscribe/invoice")
async def create_invoice(body: InvoiceRequest, tg_id: int = Depends(get_current_tg_id)):
    cfg = SUB_PLANS[body.plan]
    try:
        link = await bot.create_invoice_link(
            title=cfg["title"],
            description=cfg["description"],
            payload=f"parker_pro_{body.plan}_{tg_id}",
            currency="XTR",                                       # Telegram Stars
            prices=[LabeledPrice(label=cfg["title"], amount=cfg["stars"])],
            provider_token="",                                    # пусто = Звёзды
        )
        return JSONResponse({"url": link})
    except Exception:
        logger.exception("create_invoice failed tg_id=%s plan=%s", tg_id, body.plan)
        return JSONResponse({"error": "Не удалось создать счёт"}, status_code=502)
