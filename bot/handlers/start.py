from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart

from bot.config import WEBAPP_URL

router = Router()

WELCOME_TEXT = (
    "👋 Привет! Я *P.A.R.K.E.R.* — персональный адаптивный нутрициолог и тренер.\n\n"
    "🎯 Подстраиваюсь под твой реальный график, состояние здоровья и цели.\n\n"
    "📋 Заполни анкету за ~2 минуты и получи персональный план питания с КБЖУ."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if WEBAPP_URL:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🚀 Открыть анкету",
                web_app=WebAppInfo(url=WEBAPP_URL),
            )
        ]])
    else:
        kb = None

    await message.answer(WELCOME_TEXT, reply_markup=kb, parse_mode="Markdown")
