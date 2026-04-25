import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
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


def unschedule_reminder(reminder_id: str) -> None:
    _clear_jobs(_job_id(str(reminder_id)))


async def load_all_reminders() -> None:
    from db.queries import get_all_active_reminders
    reminders = get_all_active_reminders()
    for r in reminders:
        try:
            schedule_reminder(r)
        except Exception as e:
            logger.warning("Failed to schedule reminder %s: %s", r.get("id"), e)
    logger.info("Scheduler: loaded %d reminders", len(reminders))
