from aiogram import Router, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, BotCommand, ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.filters import Command, CommandStart

from bot.config import WEBAPP_URL, VIP_USER_IDS
from db.queries import get_user

router = Router()

APP_BTN = lambda: InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="💪 Открыть P.A.R.K.E.R.", web_app=WebAppInfo(url=WEBAPP_URL))
]]) if WEBAPP_URL else None


def _start_text(name: str, vip: bool) -> str:
    badge = " 👑" if vip else ""
    return (
        f"Привет, *{name}*!{badge}\n\n"
        "Я — *P.A.R.K.E.R.*\n"
        "Твой персональный нутрициолог и тренер на базе ИИ.\n\n"
        "Тебя ведёт *Арни* — не просто бот, а твой личный коуч:\n"
        "• Рассчитывает КБЖУ под твои параметры\n"
        "• Строит план питания на 7 дней\n"
        "• Даёт программу тренировок\n"
        "• Помнит твой прогресс и адаптирует план\n\n"
        "👇 *Открой приложение и познакомься с Арни*"
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    name = message.from_user.first_name or "друг"
    vip = message.from_user.id in VIP_USER_IDS
    await message.answer(
        _start_text(name, vip),
        reply_markup=APP_BTN(),
        parse_mode="Markdown"
    )


@router.message(Command("help"))
@router.message(F.text.lower().in_({"меню", "/меню", "menu", "/menu", "помощь", "/помощь", "команды"}))
async def cmd_help(message: Message) -> None:
    text = (
        "📋 *Команды P.A.R.K.E.R.*\n\n"
        "/start — открыть приложение\n"
        "/план — мой план питания и тренировок\n"
        "/прогресс — статистика и динамика\n"
        "/рестарт — начать заново\n"
        "/помощь — эта справка\n\n"
        "💬 Или просто открой приложение — Арни всегда на месте."
    )
    await message.answer(text, reply_markup=APP_BTN(), parse_mode="Markdown")


@router.message(Command("plan", "план"))
@router.message(F.text.lower().in_({"план", "/план", "питание", "тренировки"}))
async def cmd_plan(message: Message) -> None:
    user = get_user(message.from_user.id)
    if not user:
        await message.answer(
            "📝 Профиль не найден.\nЗаполни анкету в приложении — займёт 1 минуту.",
            reply_markup=APP_BTN()
        )
        return
    name = user.get("name") or message.from_user.first_name or "друг"
    await message.answer(
        f"Привет, {name}! Твой план — в приложении, там удобнее читать.\nОткрывай 👇",
        reply_markup=APP_BTN()
    )


@router.message(Command("progress", "прогресс"))
@router.message(F.text.lower().in_({"прогресс", "/прогресс", "статистика", "вес"}))
async def cmd_progress(message: Message) -> None:
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Профиль не найден. Начни с /start", reply_markup=APP_BTN())
        return
    goal_map = {
        "lose_weight":   "🔥 Похудение",
        "gain_muscle":   "💪 Набор массы",
        "maintain":      "⚖️ Поддержание формы",
        "recomposition": "🔄 Рекомпозиция",
    }
    goal = goal_map.get(user.get("goal", ""), "—")
    name = user.get("name") or "—"
    text = (
        f"📊 *Профиль {name}*\n\n"
        f"Цель: {goal}\n"
        f"Вес: {user.get('weight_kg', '—')} кг\n"
        f"Рост: {user.get('height_cm', '—')} см\n"
        f"Возраст: {user.get('age', '—')} лет\n\n"
        "Графики и дневник — в приложении 👇"
    )
    await message.answer(text, reply_markup=APP_BTN(), parse_mode="Markdown")


@router.message(Command("restart", "рестарт"))
@router.message(F.text.lower().in_({"рестарт", "/рестарт", "заново", "сброс"}))
async def cmd_restart(message: Message) -> None:
    await message.answer(
        "🔄 Хочешь начать заново?\n\n"
        "Открой приложение → вкладка *Профиль* → кнопка *Начать заново*.\n\n"
        "Все данные будут сброшены.",
        reply_markup=APP_BTN(),
        parse_mode="Markdown"
    )


@router.message(F.text & ~F.text.startswith("/"))
async def handle_free_text(message: Message) -> None:
    name = message.from_user.first_name or "друг"
    await message.answer(
        f"Привет, {name}! 👋\n\n"
        "Чтобы пообщаться с Арни — открой приложение.\n"
        "Там есть чат, трекер питания и твой план. 💪",
        reply_markup=APP_BTN()
    )


async def set_bot_commands(bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="start",     description="Открыть P.A.R.K.E.R."),
        BotCommand(command="plan",      description="Мой план питания и тренировок"),
        BotCommand(command="progress",  description="Мой прогресс"),
        BotCommand(command="restart",   description="Начать заново"),
        BotCommand(command="help",      description="Справка"),
    ])
