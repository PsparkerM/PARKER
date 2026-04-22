from aiogram import Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from bot.states.onboarding import OnboardingStates
from bot.keyboards.onboarding_kb import goal_kb

router = Router()

WELCOME_TEXT = (
    "👋 Привет! Я *P.A.R.K.E.R.* — твой персональный адаптивный нутрициолог и тренер.\n\n"
    "🎯 Я не даю «стандартный» план — я подстраиваюсь под *твой* реальный график, "
    "состояние здоровья и цели.\n\n"
    "📋 Заполним короткую анкету (~2 минуты), рассчитаем твой КБЖУ "
    "и составим персональный план питания.\n\n"
    "Готов начать?"
)

START_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🚀 Начать анкету", callback_data="start_onboarding")]
])


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=START_KB, parse_mode="Markdown")


@router.callback_query(lambda c: c.data == "start_onboarding")
async def cb_start_onboarding(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.goal)
    await callback.message.edit_text(
        "🎯 *Шаг 1 из 9 — Цель*\n\nЧего хочешь достичь?",
        reply_markup=goal_kb(),
        parse_mode="Markdown",
    )
