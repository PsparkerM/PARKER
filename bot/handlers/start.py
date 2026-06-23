import asyncio
from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, BotCommand,
)
from aiogram.filters import Command, CommandStart

from bot.config import WEBAPP_URL, ADMIN_TG_IDS
from db.queries import get_user, update_last_seen, get_all_users

router = Router()

APP_BTN = lambda: InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="💪 Открыть P.A.R.K.E.R.", web_app=WebAppInfo(url=WEBAPP_URL))
]]) if WEBAPP_URL else None


def _start_text(name: str, status: str) -> str:
    badge = " 👑" if status == "vip" else (" ⭐ Pro" if status == "pro" else "")
    return (
        f"Привет, *{name}*!{badge}\n\n"
        "Я — *P.A.R.K.E.R.*\n"
        "Твой персональный нутрициолог и тренер.\n\n"
        "Тебя ведёт *Арни* — твой личный коуч:\n"
        "• Рассчитывает КБЖУ под твои параметры\n"
        "• Строит план питания на 7 дней\n"
        "• Даёт программу тренировок\n"
        "• Помнит твой прогресс и адаптирует план\n\n"
        "👇 *Открой приложение и познакомься с Арни*"
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    name  = message.from_user.first_name or "друг"
    tg_id = message.from_user.id
    user  = await asyncio.to_thread(get_user, tg_id)
    status = (user or {}).get("status", "free")

    if user:
        asyncio.ensure_future(asyncio.to_thread(update_last_seen, tg_id))

    # notify admins when a brand-new user hits /start for the first time (no profile yet)
    if not user and ADMIN_TG_IDS:
        username = message.from_user.username
        un_str = f"@{username}" if username else "нет username"
        alert = (
            f"👤 *Новый пользователь зашёл!*\n\n"
            f"Имя: {message.from_user.full_name}\n"
            f"TG ID: `{tg_id}`\n"
            f"Username: {un_str}\n\n"
            f"Профиль ещё не заполнен."
        )
        for admin_id in ADMIN_TG_IDS:
            try:
                await message.bot.send_message(admin_id, alert, parse_mode="Markdown")
            except Exception:
                pass

    await message.answer(
        _start_text(name, status),
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
        "/подписка — Pro-подписка (15 AI/день)\n"
        "/рестарт — начать заново\n"
        "/помощь — эта справка\n"
        "🆘 /support — связаться с поддержкой\n\n"
        "💬 Или просто открой приложение — Арни всегда на месте."
    )
    await message.answer(text, reply_markup=APP_BTN(), parse_mode="Markdown")


@router.message(Command("plan", "план"))
@router.message(F.text.lower().in_({"план", "/план", "питание", "тренировки"}))
async def cmd_plan(message: Message) -> None:
    user = await asyncio.to_thread(get_user, message.from_user.id)
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
    user = await asyncio.to_thread(get_user, message.from_user.id)
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


@router.message(Command("dm"))
async def cmd_dm(message: Message) -> None:
    if message.from_user.id not in ADMIN_TG_IDS:
        return
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Формат: /dm <tg_id> <текст сообщения>")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный tg_id — должно быть числом")
        return
    text = parts[2]
    try:
        await message.bot.send_message(target_id, text)
        await message.answer(f"✅ Отправлено → {target_id}")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}")


GOAL_MAP = {
    "lose_weight":   "Похудение",
    "gain_muscle":   "Набор массы",
    "maintain":      "Поддержание",
    "recomposition": "Рекомпозиция",
}


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if message.from_user.id not in ADMIN_TG_IDS:
        return

    users = await asyncio.to_thread(get_all_users)
    if not users:
        await message.answer("Нет пользователей.")
        return

    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    day_ago  = (now - timedelta(days=1)).isoformat()

    total    = len(users)
    vip_cnt  = sum(1 for u in users if (u.get("status") or "free") == "vip")
    pro_cnt  = sum(1 for u in users if (u.get("status") or "free") == "pro")
    free_cnt = sum(1 for u in users if (u.get("status") or "free") == "free")
    new_week = sum(1 for u in users if (u.get("created_at") or "") >= week_ago)
    active_day = sum(1 for u in users if (u.get("last_seen") or "") >= day_ago)

    recent = sorted(users, key=lambda u: u.get("created_at") or "", reverse=True)[:5]
    recent_lines = []
    for u in recent:
        nm = u.get("name") or "—"
        tid = u.get("tg_id", "—")
        dt  = (u.get("created_at") or "")[:10]
        recent_lines.append(f"• {nm} (`{tid}`) — {dt}")

    seen = [u for u in users if u.get("last_seen")]
    seen_sorted = sorted(seen, key=lambda u: u.get("last_seen") or "", reverse=True)[:5]
    seen_lines = []
    for u in seen_sorted:
        nm  = u.get("name") or "—"
        tid = u.get("tg_id", "—")
        ls  = (u.get("last_seen") or "")[:16].replace("T", " ")
        seen_lines.append(f"• {nm} (`{tid}`) — {ls}")

    text = (
        "📊 *P.A.R.K.E.R. — Статистика*\n\n"
        f"👥 Всего пользователей: *{total}*\n"
        f"👑 VIP: *{vip_cnt}*  |  ⭐ Pro: *{pro_cnt}*  |  ⚡ Free: *{free_cnt}*\n"
        f"📅 За 7 дней: *{new_week}*\n"
        f"🟢 Активны за 24 ч: *{active_day}*\n\n"
        "🕐 *Последние регистрации:*\n" + "\n".join(recent_lines or ["нет данных"])
    )
    if seen_lines:
        text += "\n\n👁 *Последние активные:*\n" + "\n".join(seen_lines)

    await message.answer(text, parse_mode="Markdown")


@router.message(Command("users"))
async def cmd_users(message: Message) -> None:
    if message.from_user.id not in ADMIN_TG_IDS:
        return

    users = await asyncio.to_thread(get_all_users)
    if not users:
        await message.answer("Нет пользователей.")
        return

    lines = []
    for u in users:
        status = u.get("status") or "free"
        badge  = "👑" if status == "vip" else ("⭐" if status == "pro" else "⚡")
        nm     = u.get("name") or "—"
        tid    = u.get("tg_id", "—")
        goal   = GOAL_MAP.get(u.get("goal", ""), "—")
        wt     = u.get("weight_kg", "—")
        ht     = u.get("height_cm", "—")
        age    = u.get("age", "—")
        ls     = (u.get("last_seen") or "")[:10] or "не заходил"
        lines.append(
            f"{badge} *{nm}* `{tid}`\n"
            f"   {goal} · {age}л · {wt}кг / {ht}см\n"
            f"   Последний вход: {ls}"
        )

    chunks = []
    current = "👥 *Все пользователи P.A.R.K.E.R.:*\n\n"
    for line in lines:
        if len(current) + len(line) + 2 > 4000:
            chunks.append(current)
            current = ""
        current += line + "\n\n"
    if current.strip():
        chunks.append(current)

    for chunk in chunks:
        await message.answer(chunk.strip(), parse_mode="Markdown")


async def set_bot_commands(bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="start",     description="Открыть P.A.R.K.E.R."),
        BotCommand(command="plan",      description="Мой план питания и тренировок"),
        BotCommand(command="progress",  description="Мой прогресс"),
        BotCommand(command="subscribe", description="Pro-подписка — 15 AI/день"),
        BotCommand(command="restart",   description="Начать заново"),
        BotCommand(command="help",      description="Справка"),
        BotCommand(command="support",   description="🆘 Поддержка — связаться с командой"),
        BotCommand(command="stats",     description="[Admin] Статистика пользователей"),
        BotCommand(command="users",     description="[Admin] Список всех пользователей"),
    ])
