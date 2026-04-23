from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart

from bot.config import WEBAPP_URL

router = Router()

WELCOME = (
    "👋 Привет! Я *P.A.R.K.E.R.* — твой персональный нутрициолог и тренер.\n\n"
    "🧬 Я не даю стандартные планы — я строю протокол *под твою жизнь*:\n"
    "твой график, твоё здоровье, твои цели.\n\n"
    "📋 Заполни анкету — получишь персональный план питания и тренировок."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    kb = None
    if WEBAPP_URL:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🚀 Открыть анкету P.A.R.K.E.R.",
                web_app=WebAppInfo(url=WEBAPP_URL),
            )
        ]])
    await message.answer(WELCOME, reply_markup=kb, parse_mode="Markdown")
