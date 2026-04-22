from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.states.onboarding import OnboardingStates
from bot.keyboards.onboarding_kb import (
    OnboardingCallback, MultiSelectCallback,
    gender_kb, body_fat_kb, schedule_kb,
    health_issues_kb, equipment_kb, confirmation_kb, goal_kb,
)
from bot.services.nutrition import build_profile_summary, compute_macros_for_profile
from bot.services.ai_service import generate_meal_plan

router = Router()


# ── 1. GOAL ───────────────────────────────────────────────────────────────────

@router.callback_query(OnboardingCallback.filter(F.step == "goal"))
async def on_goal(callback: CallbackQuery, callback_data: OnboardingCallback, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(goal=callback_data.value)
    await state.set_state(OnboardingStates.gender)
    await callback.message.edit_text(
        "👤 *Шаг 2 из 9 — Пол*\n\nУкажи свой биологический пол:",
        reply_markup=gender_kb(),
        parse_mode="Markdown",
    )


# ── 2. GENDER ─────────────────────────────────────────────────────────────────

@router.callback_query(OnboardingCallback.filter(F.step == "gender"))
async def on_gender(callback: CallbackQuery, callback_data: OnboardingCallback, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(gender=callback_data.value)
    await state.set_state(OnboardingStates.age)
    await callback.message.edit_text(
        "🔢 *Шаг 3 из 9 — Возраст*\n\nСколько тебе полных лет? _(например: 25)_",
        parse_mode="Markdown",
    )


# ── 3. AGE ────────────────────────────────────────────────────────────────────

@router.message(OnboardingStates.age)
async def on_age(message: Message, state: FSMContext) -> None:
    try:
        age = int(message.text.strip())
        if not 10 <= age <= 100:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("❌ Введи корректный возраст — целое число от 10 до 100:")
        return
    await state.update_data(age=age)
    await state.set_state(OnboardingStates.height)
    await message.answer(
        "📏 *Шаг 4 из 9 — Рост*\n\nРост в сантиметрах? _(например: 175)_",
        parse_mode="Markdown",
    )


# ── 4. HEIGHT ─────────────────────────────────────────────────────────────────

@router.message(OnboardingStates.height)
async def on_height(message: Message, state: FSMContext) -> None:
    try:
        height = int(message.text.strip())
        if not 100 <= height <= 250:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("❌ Введи корректный рост — от 100 до 250 см:")
        return
    await state.update_data(height_cm=height)
    await state.set_state(OnboardingStates.weight)
    await message.answer(
        "⚖️ *Шаг 5 из 9 — Вес*\n\nВес в килограммах? _(например: 80 или 80.5)_",
        parse_mode="Markdown",
    )


# ── 5. WEIGHT ─────────────────────────────────────────────────────────────────

@router.message(OnboardingStates.weight)
async def on_weight(message: Message, state: FSMContext) -> None:
    try:
        weight = float(message.text.strip().replace(",", "."))
        if not 20 <= weight <= 500:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("❌ Введи корректный вес — от 20 до 500 кг:")
        return
    await state.update_data(weight_kg=weight)
    await state.set_state(OnboardingStates.body_fat)
    await message.answer(
        "💧 *Шаг 6 из 9 — Процент жира*\n\n"
        "Знаешь свой % подкожного жира?\n"
        "_Если да — расчёт будет точнее (формула Кетч-МакАрдл)_",
        reply_markup=body_fat_kb(),
        parse_mode="Markdown",
    )


# ── 6. BODY FAT ───────────────────────────────────────────────────────────────

@router.callback_query(OnboardingCallback.filter(F.step == "body_fat"))
async def on_body_fat_choice(callback: CallbackQuery, callback_data: OnboardingCallback, state: FSMContext) -> None:
    await callback.answer()
    if callback_data.value == "skip":
        await state.update_data(body_fat_pct=None)
        await state.set_state(OnboardingStates.schedule)
        await callback.message.edit_text(
            "⏰ *Шаг 7 из 9 — Рабочий график*\n\nКакой у тебя рабочий график?",
            reply_markup=schedule_kb(),
            parse_mode="Markdown",
        )
    else:
        await state.set_state(OnboardingStates.body_fat_value)
        await callback.message.edit_text(
            "💧 Введи процент подкожного жира:\n_(например: 18 или 22.5)_",
            parse_mode="Markdown",
        )


@router.message(OnboardingStates.body_fat_value)
async def on_body_fat_value(message: Message, state: FSMContext) -> None:
    try:
        bf = float(message.text.strip().replace(",", "."))
        if not 3 <= bf <= 60:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("❌ Введи корректный % жира — от 3 до 60:")
        return
    await state.update_data(body_fat_pct=bf)
    await state.set_state(OnboardingStates.schedule)
    await message.answer(
        "⏰ *Шаг 7 из 9 — Рабочий график*\n\nКакой у тебя рабочий график?",
        reply_markup=schedule_kb(),
        parse_mode="Markdown",
    )


# ── 7. SCHEDULE ───────────────────────────────────────────────────────────────

@router.callback_query(OnboardingCallback.filter(F.step == "schedule"))
async def on_schedule(callback: CallbackQuery, callback_data: OnboardingCallback, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(schedule=callback_data.value, health_issues=[])
    await state.set_state(OnboardingStates.health_issues)
    await callback.message.edit_text(
        "🏥 *Шаг 8 из 9 — Здоровье*\n\n"
        "Отметь всё, что актуально (можно несколько).\n"
        "Нажми *«➡️ Готово»* когда закончишь:",
        reply_markup=health_issues_kb([]),
        parse_mode="Markdown",
    )


# ── 8. HEALTH ISSUES (multi-select) ──────────────────────────────────────────

@router.callback_query(MultiSelectCallback.filter(F.group == "health"))
async def on_health_toggle(callback: CallbackQuery, callback_data: MultiSelectCallback, state: FSMContext) -> None:
    data = await state.get_data()
    selected = list(data.get("health_issues", []))

    if callback_data.action == "done":
        if not selected:
            selected = ["none"]
        await callback.answer()
        await state.update_data(health_issues=selected, equipment=[])
        await state.set_state(OnboardingStates.equipment)
        await callback.message.edit_text(
            "🏋️ *Шаг 9 из 9 — Оборудование*\n\n"
            "Что из оборудования у тебя есть?\n"
            "Нажми *«➡️ Готово»* когда закончишь:",
            reply_markup=equipment_kb([]),
            parse_mode="Markdown",
        )
        return

    item = callback_data.item
    if item == "none":
        selected = ["none"] if "none" not in selected else []
    else:
        if "none" in selected:
            selected.remove("none")
        if item in selected:
            selected.remove(item)
        else:
            selected.append(item)

    await callback.answer()
    await state.update_data(health_issues=selected)
    await callback.message.edit_reply_markup(reply_markup=health_issues_kb(selected))


# ── 9. EQUIPMENT (multi-select) ───────────────────────────────────────────────

@router.callback_query(MultiSelectCallback.filter(F.group == "equip"))
async def on_equip_toggle(callback: CallbackQuery, callback_data: MultiSelectCallback, state: FSMContext) -> None:
    data = await state.get_data()
    selected = list(data.get("equipment", []))

    if callback_data.action == "done":
        if not selected:
            selected = ["none"]
        await callback.answer()
        await state.update_data(equipment=selected)

        final_data = {**await state.get_data(), "equipment": selected}
        macros = compute_macros_for_profile(final_data)
        await state.update_data(macros=macros)

        summary = build_profile_summary(final_data, macros)
        await state.set_state(OnboardingStates.confirmation)
        await callback.message.edit_text(
            summary + "\n\n_Всё верно?_",
            reply_markup=confirmation_kb(),
            parse_mode="Markdown",
        )
        return

    item = callback_data.item
    if item == "none":
        selected = ["none"] if "none" not in selected else []
    else:
        if "none" in selected:
            selected.remove("none")
        if item in selected:
            selected.remove(item)
        else:
            selected.append(item)

    await callback.answer()
    await state.update_data(equipment=selected)
    await callback.message.edit_reply_markup(reply_markup=equipment_kb(selected))


# ── CONFIRMATION ──────────────────────────────────────────────────────────────

@router.callback_query(OnboardingCallback.filter(F.step == "confirm"))
async def on_confirm(callback: CallbackQuery, callback_data: OnboardingCallback, state: FSMContext) -> None:
    if callback_data.value == "restart":
        await callback.answer("Начинаем заново! 🔄")
        await state.clear()
        await state.set_state(OnboardingStates.goal)
        await callback.message.edit_text(
            "🎯 *Шаг 1 из 9 — Цель*\n\nЧего хочешь достичь?",
            reply_markup=goal_kb(),
            parse_mode="Markdown",
        )
        return

    await callback.answer("Генерирую план... ⏳")
    data = await state.get_data()
    macros = data.get("macros") or compute_macros_for_profile(data)

    await callback.message.edit_text(
        "⏳ *Составляю твой план питания...*\n\nЭто займёт несколько секунд.",
        parse_mode="Markdown",
    )

    plan = await generate_meal_plan(data, macros)

    await callback.message.answer(
        f"🎉 *Твой персональный план питания:*\n\n{plan}",
        parse_mode="Markdown",
    )
    await callback.message.answer(
        "✅ *P.A.R.K.E.R. активирован!*\n\n"
        "В следующих обновлениях:\n"
        "💪 Персональная программа тренировок\n"
        "📊 Трекинг прогресса по дням\n"
        "🔄 Ежедневная адаптация плана\n\n"
        "Используй /start чтобы обновить профиль.",
        parse_mode="Markdown",
    )
    await state.clear()
