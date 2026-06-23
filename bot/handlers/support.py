"""Саппорт-система внутри Telegram-бота.

Поток:
  1. Пользователь жмёт «🆘 Поддержка» (callback sup:open) или шлёт /support.
  2. Бот переводит его в FSM-состояние awaiting и просит описать проблему.
  3. Следующее сообщение (текст или фото-скрин) пересылается ВСЕМ из ADMIN_TG_IDS
     (владелец + менеджеры) с шапкой-маркером и подсказкой «Ответь на это сообщение».
  4. Админ/менеджер ОТВЕЧАЕТ реплаем на эту шапку прямо в своём Telegram —
     handler admin_reply ловит реплай, достаёт TG ID из текста и релеит ответ юзеру.

Никакой БД для работы не нужно: маршрутизация ответа stateless — TG ID пользователя
зашит в текст пересланной шапки, парсится из reply_to_message. Переживает рестарт.

ВАЖНО: этот роутер подключается в main.py ДО start.router, иначе catch-all
handle_free_text в start.py перехватит сообщения раньше.
"""
import logging
import re

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import ADMIN_TG_IDS

logger = logging.getLogger(__name__)
router = Router()

# Фраза-маркер: есть и в саппорт-шапке, и в платёжном алерте.
# По ней admin_reply отличает «релей-сообщения» от прочих (напр. алерта о новом юзере).
RELAY_MARK = "Ответь на это сообщение"


class SupportSG(StatesGroup):
    awaiting = State()


def _uname(u) -> str:
    return f"@{u.username}" if u.username else "нет username"


async def _open_support(message: Message, state: FSMContext) -> None:
    await state.set_state(SupportSG.awaiting)
    await message.answer(
        "🆘 *Поддержка P.A.R.K.E.R.*\n\n"
        "Опиши проблему одним сообщением — можно приложить скриншот.\n"
        "Например: _оплатил подписку, но Pro не включился_, что-то не работает, вопрос.\n\n"
        "Передам команде сразу — ответим прямо здесь, в этом чате.\n"
        "Отменить — /cancel",
        parse_mode="Markdown",
    )


@router.message(Command("support", "поддержка", "саппорт"))
async def cmd_support(message: Message, state: FSMContext) -> None:
    await _open_support(message, state)


@router.callback_query(F.data == "sup:open")
async def cb_support_open(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _open_support(callback.message, state)


@router.message(Command("cancel", "отмена"), SupportSG.awaiting)
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Окей, отменил. Если что — жми «🆘 Поддержка» или /support.")


async def _forward_to_admins(bot, message: Message, header: str) -> bool:
    """Шлёт админам шапку-маркер и копию исходного сообщения юзера (текст/фото)."""
    ok = False
    for admin_id in ADMIN_TG_IDS:
        try:
            await bot.send_message(admin_id, header, parse_mode="Markdown")
            await bot.copy_message(admin_id, message.chat.id, message.message_id)
            ok = True
        except Exception as e:
            logger.warning("support: forward to %s failed: %s", admin_id, e)
    return ok


async def _handle_ticket(message: Message, state: FSMContext) -> None:
    u = message.from_user
    header = (
        "🆘 *Обращение в поддержку*\n\n"
        f"Имя: {u.full_name}\n"
        f"TG ID: `{u.id}`\n"
        f"Username: {_uname(u)}\n\n"
        f"↩️ {RELAY_MARK} — напишешь пользователю."
    )
    ok = await _forward_to_admins(message.bot, message, header)
    await state.clear()
    if ok:
        await message.answer(
            "✅ Передал команде! Ответим прямо здесь, в этом чате. Спасибо 🙏"
        )
    else:
        await message.answer(
            "⚠️ Не получилось отправить обращение. Попробуй чуть позже, пожалуйста."
        )


@router.message(SupportSG.awaiting, F.text & ~F.text.startswith("/"))
async def support_text(message: Message, state: FSMContext) -> None:
    await _handle_ticket(message, state)


@router.message(SupportSG.awaiting, F.photo)
async def support_photo(message: Message, state: FSMContext) -> None:
    await _handle_ticket(message, state)


@router.message(
    F.reply_to_message,
    F.from_user.id.in_(ADMIN_TG_IDS),
    F.reply_to_message.text.contains(RELAY_MARK),
)
async def admin_reply(message: Message) -> None:
    """Админ/менеджер ответил реплаем на саппорт-шапку или платёжный алерт →
    релеим его текст пользователю, чей TG ID зашит в исходном сообщении."""
    rt = message.reply_to_message.text or ""
    m = re.search(r"TG ID:\D*(\d{4,})", rt)
    if not m:
        return
    target = int(m.group(1))
    text = message.text or message.caption or ""
    if not text.strip():
        await message.answer("Пустой ответ — напиши текстом или подпиши фото.")
        return
    try:
        await message.bot.send_message(
            target,
            f"💬 *Поддержка P.A.R.K.E.R.:*\n\n{text}",
            parse_mode="Markdown",
        )
        await message.answer(f"✅ Отправлено пользователю `{target}`", parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Не доставлено ({target}): {e}")
