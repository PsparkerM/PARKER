import asyncio
import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from bot.bot_instance import bot

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="UTC")


async def _send(tg_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id=tg_id, text=text)
    except Exception as e:
        logger.warning("reminder send failed tg_id=%s: %s", tg_id, e)


_MEAL_MESSAGES = {
    "завтрак":        "🍳 Доброе утро! Пора позавтракать. Хороший завтрак заряжает на весь день — не пропускай. Приятного аппетита! 💪",
    "обед":           "🍽 Обеденный перерыв! Пора пообедать по плану питания. Не забудь про белок и сложные углеводы. Приятного аппетита! 💪",
    "ужин":           "🌙 Время ужина! Пора поужинать — придерживайся плана и не переедай на ночь. Приятного аппетита! 💪",
    "перекус":        "🥜 Время перекуса! Небольшой полезный перекус поддержит уровень энергии. 💪",
    "второй завтрак": "☕ Время второго завтрака! Поддержи метаболизм — небольшой перекус по плану. 💪",
    "breakfast":      "🍳 Good morning! Time for breakfast — don't skip it. A good breakfast fuels your day. Enjoy! 💪",
    "lunch":          "🍽 Lunch time! Time to eat according to your meal plan. Don't forget your protein. Enjoy! 💪",
    "dinner":         "🌙 Dinner time! Stick to your plan and don't overeat before bed. Enjoy! 💪",
    "snack":          "🥜 Snack time! A healthy snack keeps your energy stable. 💪",
}


def _meal_text(label: str) -> str:
    return _MEAL_MESSAGES.get(label.lower().strip(),
        f"🍽 Пора {label}! Время подкрепиться по плану питания. Приятного аппетита! 💪")


def _job_id(reminder_id: str) -> str:
    return f"rem_{reminder_id}"


def _clear_jobs(jid: str) -> None:
    """Remove a job and any indexed sub-jobs (used for multi-time meal reminders)."""
    if scheduler.get_job(jid):
        scheduler.remove_job(jid)
    for i in range(10):
        sub = f"{jid}_{i}"
        if scheduler.get_job(sub):
            scheduler.remove_job(sub)


def schedule_reminder(r: dict) -> None:
    jid = _job_id(str(r["id"]))
    _clear_jobs(jid)
    if not r.get("active"):
        return

    tg_id = int(r["tg_id"])
    rtype = r.get("type")
    utc_offset = int(r.get("utc_offset", 3))

    if rtype == "water":
        interval = int(r.get("interval_min", 60))
        night_mode = bool(r.get("night_mode", True))

        async def water_job(tg_id=tg_id, night_mode=night_mode, utc_offset=utc_offset):
            if night_mode:
                local_hour = (datetime.now(timezone.utc) + timedelta(hours=utc_offset)).hour
                if local_hour < 7 or local_hour >= 23:
                    return
            local_h = (datetime.now(timezone.utc) + timedelta(hours=utc_offset)).hour
            if local_h < 10:
                msg = "💧 Доброе утро! Начни день со стакана воды — запускает метаболизм. Держи водный баланс! 🌊"
            elif local_h >= 20:
                msg = "💧 Вечернее напоминание! Не забывай о воде — гидратация важна в любое время суток. 💧"
            else:
                msg = "💧 Время выпить воды! Стакан прямо сейчас — держи водный баланс. Это важнее, чем кажется! 🌊"
            await _send(tg_id, msg)

        scheduler.add_job(water_job, IntervalTrigger(minutes=interval), id=jid, replace_existing=True)

    elif rtype == "meal":
        # Support both legacy single `time` and new `times` array
        times = r.get("times") or ([r.get("time", "12:00")] if r.get("time") else ["12:00"])
        labels = r.get("labels") or (["Приём пищи"] * len(times))

        for i, (time_str, label) in enumerate(zip(times, labels)):
            sub_jid = f"{jid}_{i}"
            try:
                h, m = map(int, time_str.split(":"))
                utc_h = (h - utc_offset) % 24
            except (ValueError, AttributeError):
                logger.warning("Invalid meal time %s for reminder %s slot %d", time_str, r["id"], i)
                continue

            async def meal_job(tg_id=tg_id, label=label):
                await _send(tg_id, _meal_text(label))

            scheduler.add_job(meal_job, CronTrigger(hour=utc_h, minute=m), id=sub_jid, replace_existing=True)

    elif rtype == "log":
        time_str = r.get("time", "20:00")
        try:
            h, m = map(int, time_str.split(":"))
            utc_h = (h - utc_offset) % 24
        except (ValueError, AttributeError):
            return

        async def log_job(tg_id=tg_id):
            await _send(tg_id,
                "📏 Время замеров! Запиши вес и обхваты в P.A.R.K.E.R. — 2 минуты сейчас дают Арни точные данные для адаптации плана. "
                "Открой приложение → Трекер 🎯"
            )

        scheduler.add_job(
            log_job,
            CronTrigger(hour=utc_h, minute=m),
            id=jid,
            replace_existing=True,
        )

    elif rtype == "workout":
        time_str = r.get("time", "07:00")
        day_indices = r.get("days", [0, 1, 2, 3, 4])  # 0=Mon..6=Sun
        # APScheduler day_of_week: 0=Mon in cron
        try:
            h, m = map(int, time_str.split(":"))
            utc_h = (h - utc_offset) % 24
        except (ValueError, AttributeError):
            return

        WORKOUT_MSGS = [
            "💪 Время тренировки! Арни ждёт — не подводи себя. Открой план в P.A.R.K.E.R. и погнали! 🔥",
            "🏋️ Напоминание о тренировке! Одно занятие сегодня — на шаг ближе к цели. Открой P.A.R.K.E.R. 💪",
            "⚡ Тренировочный день! Тело не изменится без работы. Арни смотрит на твои данные — давай! 💪",
        ]

        for day_idx in day_indices:
            sub_jid = f"{jid}_d{day_idx}"

            async def workout_job(tg_id=tg_id, di=day_idx):
                import random
                await _send(tg_id, random.choice(WORKOUT_MSGS))

            scheduler.add_job(
                workout_job,
                CronTrigger(day_of_week=day_idx, hour=utc_h, minute=m),
                id=sub_jid,
                replace_existing=True,
            )

    elif rtype == "motivation":
        time_str = r.get("time", "09:00")
        day_indices = r.get("days", list(range(7)))
        try:
            h, m = map(int, time_str.split(":"))
            utc_h = (h - utc_offset) % 24
        except (ValueError, AttributeError):
            return

        MOTIVATION_MSGS = [
            "🔥 Арни говорит: «Не жди подходящего момента — создай его». Сегодня отличный день начать. Открой P.A.R.K.E.R.!",
            "💪 Прогресс — это сумма маленьких шагов каждый день. Ты уже делаешь правильный выбор. Держи!",
            "⚡ Дисциплина делает то, что мотивация не может. Арни в P.A.R.K.E.R. ждёт твоих данных за сегодня 📊",
            "🎯 Один день — один шаг. Запиши еду, выпей воду, отметь тренировку. Арни следит за прогрессом!",
            "🏆 Неважно насколько медленно ты движешься — главное не останавливаться. Открой P.A.R.K.E.R. 💪",
        ]

        for day_idx in day_indices:
            sub_jid = f"{jid}_m{day_idx}"

            async def motivation_job(tg_id=tg_id):
                import random
                await _send(tg_id, random.choice(MOTIVATION_MSGS))

            scheduler.add_job(
                motivation_job,
                CronTrigger(day_of_week=day_idx, hour=utc_h, minute=m),
                id=sub_jid,
                replace_existing=True,
            )


def unschedule_reminder(reminder_id: str) -> None:
    _clear_jobs(_job_id(str(reminder_id)))


async def _expire_subscriptions_job() -> None:
    """Daily job: expire overdue subscriptions and downgrade status to free."""
    from db.queries import expire_old_subscriptions
    count = expire_old_subscriptions()
    if count:
        logger.info("Subscription expiry: %d subscription(s) expired", count)


async def _renewal_reminder_job() -> None:
    """Daily job: за SUB_RENEW_NOTIFY_DAYS дней до окончания шлём пользователю
    напоминание с кнопкой нового инвойса (оплата Звёздами)."""
    from db.queries import get_subscriptions_expiring_soon, mark_renewal_notified
    from bot.handlers.payment import sub_keyboard
    from bot.config import SUB_RENEW_NOTIFY_DAYS

    expiring = get_subscriptions_expiring_soon(SUB_RENEW_NOTIFY_DAYS)
    if not expiring:
        return

    sent = 0
    for sub in expiring:
        tg_id      = sub["tg_id"]
        expires_at = (sub.get("expires_at") or "")[:10]
        try:
            await bot.send_message(
                chat_id=tg_id,
                text=(
                    "⏳ *Подписка P.A.R.K.E.R. Pro скоро закончится*\n\n"
                    f"Действует до: *{expires_at}*\n\n"
                    "Продли за ⭐ Telegram Stars, чтобы не потерять 50 AI-запросов "
                    "в день и чат с Арни без лимитов. Выбери период:"
                ),
                parse_mode="Markdown",
                reply_markup=sub_keyboard(),
            )
            mark_renewal_notified(sub["user_id"])
            sent += 1
        except Exception as e:
            logger.warning("renewal reminder failed tg_id=%s: %s", tg_id, e)

    if sent:
        logger.info("Renewal reminders sent: %d", sent)


# ── РАЗОВАЯ РАССЫЛКА О ПЕРЕЗАПУСКЕ (launch broadcast) ──
# Шлётся ОДИН раз всем, кто когда-либо регистрировался, в указанный момент.
# Идемпотентность: job регистрируется только если момент ещё не наступил
# (см. load_all_reminders), поэтому повторный рестарт после отправки её не дублирует.
LAUNCH_BROADCAST_AT_UTC = datetime(2026, 6, 23, 6, 0, 0, tzinfo=timezone.utc)  # 09:00 МСК


def _launch_text(name: str | None) -> str:
    greet = f"Привет, {name.strip()}! 👋" if (name and name.strip()) else "Привет! 👋"
    return (
        f"{greet}\n\n"
        "💪 P.A.R.K.E.R. вернулся — и теперь он мощнее, чем когда-либо.\n\n"
        "Я полностью пересобрался с нуля: новый интерфейс, новая система трекинга, "
        "умные логи и Арни, который видит твой прогресс в реальном времени и подсказывает на лету.\n\n"
        "Худеешь, набираешь массу или просто держишь форму — мне без разницы. "
        "Моя работа: поддержать, где надо — подколоть, и не дать тебе слиться с дистанции. 🔥\n\n"
        "🎁 Первый месяц — бесплатно для всех. Без условий и звёздочек мелким шрифтом. "
        "Просто заходи и пользуйся по полной.\n"
        "Дальше будет подписка — но этот месяц твой, чтобы прочувствовать разницу.\n\n"
        "Жми кнопку ниже и погнали 👇"
    )


async def _launch_broadcast_job() -> None:
    """Разовая масштабная рассылка о перезапуске бота — всем зарегистрированным."""
    from db.queries import get_all_users
    from bot.handlers.start import APP_BTN

    users = get_all_users()
    markup = APP_BTN()
    sent = failed = 0
    for u in users:
        tg_id = u.get("tg_id")
        if not tg_id:
            continue
        try:
            await bot.send_message(
                chat_id=int(tg_id),
                text=_launch_text(u.get("name")),
                reply_markup=markup,
            )
            sent += 1
        except Exception as e:
            failed += 1
            logger.warning("launch broadcast failed tg_id=%s: %s", tg_id, e)
        await asyncio.sleep(0.05)  # держимся под лимитами Telegram (~20 msg/s)
    logger.info("Launch broadcast done: sent=%d failed=%d total=%d", sent, failed, len(users))


async def load_all_reminders() -> None:
    from db.queries import get_all_active_reminders
    reminders = get_all_active_reminders()
    for r in reminders:
        try:
            schedule_reminder(r)
        except Exception as e:
            logger.warning("Failed to schedule reminder %s: %s", r.get("id"), e)
    logger.info("Scheduler: loaded %d reminders", len(reminders))

    # System job: check for expired subscriptions every day at 00:05 UTC
    scheduler.add_job(
        _expire_subscriptions_job,
        CronTrigger(hour=0, minute=5),
        id="expire_subscriptions",
        replace_existing=True,
    )
    logger.info("Scheduler: subscription expiry job registered")

    # System job: renewal reminders every day at 10:00 UTC (≈ дневное время)
    scheduler.add_job(
        _renewal_reminder_job,
        CronTrigger(hour=10, minute=0),
        id="renewal_reminders",
        replace_existing=True,
    )
    logger.info("Scheduler: renewal reminder job registered")

    # One-shot: разовая рассылка о перезапуске в LAUNCH_BROADCAST_AT_UTC.
    # Регистрируем ТОЛЬКО если момент ещё не прошёл — иначе рестарт после
    # отправки заново её не запустит (защита от повторной массовой рассылки).
    now = datetime.now(timezone.utc)
    if now < LAUNCH_BROADCAST_AT_UTC:
        scheduler.add_job(
            _launch_broadcast_job,
            DateTrigger(run_date=LAUNCH_BROADCAST_AT_UTC),
            id="launch_broadcast",
            replace_existing=True,
            misfire_grace_time=600,  # доставим даже при коротком простое сервера у отметки
        )
        logger.info("Scheduler: launch broadcast scheduled for %s", LAUNCH_BROADCAST_AT_UTC.isoformat())
    else:
        logger.info("Scheduler: launch broadcast time passed — not scheduling")
