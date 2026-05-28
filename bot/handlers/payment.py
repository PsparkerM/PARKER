import logging
from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery,
)

from db.queries import get_user, get_subscription, upsert_subscription, set_user_status

logger = logging.getLogger(__name__)
router = Router()

# Stars pricing:
#   Monthly  — 299 Stars  (~300 руб / ~$3-4)
#   Annual   — 2990 Stars (~2990 руб / ~$30-40, экономия ~17%)
MONTHLY_STARS = 299
ANNUAL_STARS  = 2990

MONTHLY_DAYS  = 30
ANNUAL_DAYS   = 365


def _sub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"📅 Месяц — {MONTHLY_STARS} ⭐",
            callback_data="sub:monthly",
        )],
        [InlineKeyboardButton(
            text=f"📆 Год — {ANNUAL_STARS} ⭐  (экономия 17%)",
            callback_data="sub:annual",
        )],
    ])


@router.message(Command("subscribe", "подписка"))
@router.message(F.text.lower().in_({"подписка", "/подписка", "subscribe", "pro", "прайс", "цена"}))
async def cmd_subscribe(message: Message) -> None:
    user = get_user(message.from_user.id)
    status = (user or {}).get("status", "free")

    if status in ("pro", "vip"):
        sub = get_subscription(user["id"]) if user else None
        expires_str = ""
        if sub and sub.get("expires_at"):
            expires_str = f"\nАктивна до: *{sub['expires_at'][:10]}*"
        await message.answer(
            f"✅ У тебя уже активна подписка *Pro*!{expires_str}\n\n"
            "50 AI-запросов в день — без ограничений.",
            parse_mode="Markdown",
        )
        return

    await message.answer(
        "🚀 *P.A.R.K.E.R. Pro*\n\n"
        "• 50 AI-запросов в день (вместо 5)\n"
        "• Неограниченный чат с Арни\n"
        "• Анализ прогресса и адаптация плана\n\n"
        "Оплата через *Telegram Stars* — безопасно, без карты.\n"
        "Выбери период:",
        reply_markup=_sub_keyboard(),
        parse_mode="Markdown",
    )


@router.callback_query(F.data.startswith("sub:"))
async def sub_plan_callback(callback: CallbackQuery) -> None:
    plan = callback.data.split(":")[1]

    if plan == "monthly":
        stars       = MONTHLY_STARS
        title       = "P.A.R.K.E.R. Pro — 1 месяц"
        description = "50 AI-запросов в день, чат с Арни без лимитов, адаптация плана"
    else:
        stars       = ANNUAL_STARS
        title       = "P.A.R.K.E.R. Pro — 1 год"
        description = "50 AI-запросов в день на целый год. Экономия 17% против месячной"

    await callback.answer()
    await callback.message.answer_invoice(
        title=title,
        description=description,
        payload=f"parker_pro_{plan}_{callback.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=title, amount=stars)],
        provider_token="",
    )


@router.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message) -> None:
    payment   = message.successful_payment
    payload   = payment.invoice_payload       # parker_pro_monthly_123456
    charge_id = payment.telegram_payment_charge_id

    parts = payload.split("_")
    plan  = parts[2] if len(parts) > 2 else "monthly"
    days  = ANNUAL_DAYS if plan == "annual" else MONTHLY_DAYS

    user = get_user(message.from_user.id)
    if not user:
        logger.error("successful_payment: user not found tg_id=%s", message.from_user.id)
        await message.answer("Оплата получена! Обратись к @support для активации.")
        return

    expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    upsert_subscription(user["id"], plan, charge_id, expires_at)
    set_user_status(message.from_user.id, "pro")

    period = "1 год" if plan == "annual" else "30 дней"
    logger.info(
        "subscription activated tg_id=%s plan=%s charge=%s expires=%s",
        message.from_user.id, plan, charge_id, expires_at.date(),
    )
    await message.answer(
        f"🎉 Спасибо! Подписка *P.A.R.K.E.R. Pro* активирована на {period}.\n\n"
        f"✅ Теперь доступно 50 AI-запросов в день.\n"
        f"📅 Действует до: *{expires_at.strftime('%d.%m.%Y')}*\n\n"
        "Арни ждёт тебя в приложении! 💪",
        parse_mode="Markdown",
    )
