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
from bot.config import SUB_PLANS, ADMIN_TG_IDS, PRO_AI_DAILY_LIMIT

logger = logging.getLogger(__name__)
router = Router()

# Цены и длительности берутся из bot/config.py (env-driven, единый источник).
# Чтобы изменить стоимость — правь SUB_MONTHLY_STARS / SUB_ANNUAL_STARS там
# или задай переменные окружения. Здесь хардкода цен НЕТ.


def sub_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора плана. Используется и в /subscribe, и в напоминании
    о продлении (планировщик), поэтому вынесена в публичный хелпер."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"📅 Месяц — {SUB_PLANS['monthly']['stars']} ⭐",
            callback_data="sub:monthly",
        )],
        [InlineKeyboardButton(
            text=f"📆 Год — {SUB_PLANS['annual']['stars']} ⭐  (экономия 17%)",
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
            f"{PRO_AI_DAILY_LIMIT} AI-запросов в день.",
            parse_mode="Markdown",
        )
        return

    await message.answer(
        "🚀 *P.A.R.K.E.R. Pro*\n\n"
        f"• {PRO_AI_DAILY_LIMIT} AI-запросов в день (вместо 5)\n"
        "• Чат с Арни и разбор фото еды\n"
        "• Анализ прогресса и адаптация плана\n\n"
        "Оплата через *Telegram Stars* — безопасно, без карты.\n"
        "Выбери период:",
        reply_markup=sub_keyboard(),
        parse_mode="Markdown",
    )


@router.callback_query(F.data.startswith("sub:"))
async def sub_plan_callback(callback: CallbackQuery) -> None:
    plan = callback.data.split(":")[1]
    cfg  = SUB_PLANS.get(plan) or SUB_PLANS["monthly"]

    await callback.answer()
    await callback.message.answer_invoice(
        title=cfg["title"],
        description=cfg["description"],
        payload=f"parker_pro_{plan}_{callback.from_user.id}",
        currency="XTR",                                       # Telegram Stars
        prices=[LabeledPrice(label=cfg["title"], amount=cfg["stars"])],
        provider_token="",                                    # пусто = оплата Звёздами
    )


@router.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


async def _alert_payment_issue(bot, message: Message, plan: str, charge_id: str, reason: str) -> None:
    """Шлёт владельцу/менеджерам срочный алерт: оплата прошла, активация — нет.
    Кнопка «Активировать вручную» + возможность ответить юзеру реплаем.
    Маркер 'Ответь на это сообщение' нужен, чтобы сработал релей из support.py."""
    u = message.from_user
    stars = SUB_PLANS.get(plan, {}).get("stars", "?")
    text = (
        "🚨 *ОПЛАТА БЕЗ АКТИВАЦИИ*\n\n"
        f"Имя: {u.full_name}\n"
        f"TG ID: `{u.id}`\n"
        f"Username: {('@' + u.username) if u.username else 'нет username'}\n"
        f"План: *{plan}* ({stars}⭐)\n"
        f"Charge: `{charge_id}`\n"
        f"Причина: {reason}\n\n"
        "Нажми «Активировать вручную» — подключу Pro этому юзеру.\n"
        "↩️ Ответь на это сообщение — напишешь пользователю напрямую."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Активировать вручную", callback_data=f"actsub:{u.id}:{plan}")
    ]])
    for admin_id in ADMIN_TG_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="Markdown", reply_markup=kb)
        except Exception as e:
            logger.warning("payment alert to %s failed: %s", admin_id, e)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message) -> None:
    payment   = message.successful_payment
    payload   = payment.invoice_payload       # parker_pro_monthly_123456
    charge_id = payment.telegram_payment_charge_id

    parts = payload.split("_")
    plan  = parts[2] if len(parts) > 2 else "monthly"
    if plan not in SUB_PLANS:
        plan = "monthly"
    days  = SUB_PLANS[plan]["days"]

    # Активация в защищённом блоке: если юзера нет в БД ИЛИ упала запись —
    # деньги уже списаны, поэтому НЕ молчим: алертим админов + сохраняем чек у них,
    # юзеру обещаем ручное подключение. Так оплата без активации не теряется.
    try:
        user = get_user(message.from_user.id)
        if not user:
            raise RuntimeError("пользователя нет в БД (ещё не открыл приложение/анкету)")
        expires_at = datetime.now(timezone.utc) + timedelta(days=days)
        upsert_subscription(user["id"], plan, charge_id, expires_at)
        set_user_status(message.from_user.id, "pro")
    except Exception as e:
        logger.error(
            "ACTIVATION FAILED tg_id=%s plan=%s charge=%s: %s",
            message.from_user.id, plan, charge_id, e,
        )
        await _alert_payment_issue(message.bot, message, plan, charge_id, str(e))
        await message.answer(
            "Оплата получена ✅\n\n"
            "Возникла техническая заминка с активацией подписки — "
            "я уже уведомил команду, подключим вручную в ближайшее время. "
            "Извини за неудобство! 🙏"
        )
        return

    period = "1 год" if plan == "annual" else "30 дней"
    logger.info(
        "subscription activated tg_id=%s plan=%s charge=%s expires=%s",
        message.from_user.id, plan, charge_id, expires_at.date(),
    )
    await message.answer(
        f"🎉 Спасибо! Подписка *P.A.R.K.E.R. Pro* активирована на {period}.\n\n"
        f"✅ Теперь доступно {PRO_AI_DAILY_LIMIT} AI-запросов в день.\n"
        f"📅 Действует до: *{expires_at.strftime('%d.%m.%Y')}*\n\n"
        "Арни ждёт тебя в приложении! 💪",
        parse_mode="Markdown",
    )


@router.callback_query(F.data.startswith("actsub:"))
async def manual_activate_callback(callback: CallbackQuery) -> None:
    """Ручная активация Pro из платёжного алерта (только для ADMIN_TG_IDS)."""
    if callback.from_user.id not in ADMIN_TG_IDS:
        await callback.answer("Недоступно", show_alert=True)
        return
    try:
        _, tg_id_s, plan = callback.data.split(":", 2)
        tg_id = int(tg_id_s)
    except ValueError:
        await callback.answer("Битые данные кнопки", show_alert=True)
        return
    if plan not in SUB_PLANS:
        plan = "monthly"

    user = get_user(tg_id)
    if not user:
        await callback.answer(
            "Юзера всё ещё нет в БД — попроси его открыть приложение и заполнить анкету, "
            "потом активируй снова.",
            show_alert=True,
        )
        return

    days = SUB_PLANS[plan]["days"]
    expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    try:
        upsert_subscription(user["id"], plan, f"manual_by_{callback.from_user.id}", expires_at)
        set_user_status(tg_id, "pro")
    except Exception as e:
        logger.error("manual activation failed tg_id=%s: %s", tg_id, e)
        await callback.answer(f"Ошибка БД: {e}", show_alert=True)
        return

    logger.info("subscription manually activated tg_id=%s plan=%s by admin=%s",
                tg_id, plan, callback.from_user.id)
    try:
        await callback.message.edit_text(
            (callback.message.text or "") +
            f"\n\n✅ Активировано вручную (admin {callback.from_user.id}) до {expires_at.strftime('%d.%m.%Y')}",
        )
    except Exception:
        pass
    try:
        await callback.bot.send_message(
            tg_id,
            "🎉 Подписка *P.A.R.K.E.R. Pro* активирована! Спасибо за оплату 🙏\n"
            f"📅 Действует до: *{expires_at.strftime('%d.%m.%Y')}*",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning("notify user after manual activation failed: %s", e)
    await callback.answer("Активировано ✅")
