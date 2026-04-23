from aiogram import Router
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, BotCommand,
)
from aiogram.filters import Command, CommandStart

from bot.config import WEBAPP_URL, VIP_USER_IDS
from db.queries import get_user

router = Router()

APP_BTN = lambda: InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="💪 Открыть P.A.R.K.E.R.", web_app=WebAppInfo(url=WEBAPP_URL))
]]) if WEBAPP_URL else None


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    name = message.from_user.first_name or "друг"
    vip = message.from_user.id in VIP_USER_IDS
    badge = " 👑 VIP" if vip else ""
    text = (
        f"Привет, {name}!{badge}\n\n"
        "Я — *P.A.R.K.E.R.*, твой персональный тренер и нутрициолог.\n\n"
        "Не шаблонные планы — протокол под *твою* жизнь: "
        "твой график, твоё здоровье, твои цели.\n\n"
        "👇 Открывай приложение — Арни уже ждёт."
    )
    await message.answer(text, reply_markup=APP_BTN(), parse_mode="Markdown")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    text = (
        "📋 *Команды P.A.R.K.E.R.*\n\n"
        "/start — открыть приложение\n"
        "/plan — показать текущий план питания и тренировок\n"
        "/progress — мой прогресс\n"
        "/restart — начать заново (сбросить профиль)\n"
        "/referral — партнёрская программа\n"
        "/help — эта справка\n\n"
        "💬 Или просто открой приложение и спроси Арни — он ответит на всё."
    )
    await message.answer(text, reply_markup=APP_BTN(), parse_mode="Markdown")


@router.message(Command("plan"))
async def cmd_plan(message: Message) -> None:
    user = get_user(message.from_user.id)
    if not user:
        await message.answer(
            "У меня нет твоего профиля. Сначала заполни анкету в приложении 👇",
            reply_markup=APP_BTN()
        )
        return
    await message.answer(
        "Твой план — в приложении, там удобнее читать. Открывай 👇",
        reply_markup=APP_BTN()
    )


@router.message(Command("progress"))
async def cmd_progress(message: Message) -> None:
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Профиль не найден. Начни с /start", reply_markup=APP_BTN())
        return
    goal_map = {
        "lose_weight": "🔥 Похудение",
        "gain_muscle": "💪 Набор массы",
        "maintain": "⚖️ Поддержание формы",
        "recomposition": "🔄 Рекомпозиция",
    }
    goal = goal_map.get(user.get("goal", ""), user.get("goal", "—"))
    text = (
        f"📊 *Твой профиль*\n\n"
        f"Цель: {goal}\n"
        f"Вес: {user.get('weight_kg', '—')} кг\n"
        f"Рост: {user.get('height_cm', '—')} см\n"
        f"Возраст: {user.get('age', '—')} лет\n\n"
        "Дневник тренировок и питания — в приложении 👇"
    )
    await message.answer(text, reply_markup=APP_BTN(), parse_mode="Markdown")


@router.message(Command("restart"))
async def cmd_restart(message: Message) -> None:
    await message.answer(
        "Хочешь начать заново? Открой приложение и нажми *Начать заново* в разделе Профиль.",
        reply_markup=APP_BTN(), parse_mode="Markdown"
    )


@router.message(Command("referral"))
async def cmd_referral(message: Message) -> None:
    uid = message.from_user.id
    await message.answer(
        "🤝 *Партнёрская программа P.A.R.K.E.R.*\n\n"
        "Скоро здесь будет реферальная система.\n"
        "Приглашай друзей — получай бонусы и премиум-доступ.\n\n"
        "_Следи за обновлениями!_",
        parse_mode="Markdown"
    )


async def set_bot_commands(bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="start",    description="Открыть P.A.R.K.E.R."),
        BotCommand(command="plan",     description="Мой план питания и тренировок"),
        BotCommand(command="progress", description="Мой прогресс"),
        BotCommand(command="restart",  description="Начать заново"),
        BotCommand(command="referral", description="Партнёрская программа"),
        BotCommand(command="help",     description="Справка по командам"),
    ])
