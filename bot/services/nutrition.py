from bot.utils.calculators import (
    calculate_bmr, calculate_tdee, calculate_macros,
    GOAL_LABELS, SCHEDULE_LABELS, HEALTH_LABELS, EQUIPMENT_LABELS,
)

FORBIDDEN_EXERCISES: dict[str, list[str]] = {
    "back_problems": ["становая тяга", "приседания со штангой", "гиперэкстензия с весом", "наклоны с гантелями"],
    "knee_issues":   ["глубокие приседания с весом", "выпады с отягощением", "запрыгивания на тумбу"],
    "hypertension":  ["тяжёлый жим над головой", "упражнения с задержкой дыхания (натуживание)"],
}


def compute_macros_for_profile(data: dict) -> dict:
    bmr = calculate_bmr(
        gender=data["gender"],
        age=int(data["age"]),
        height_cm=int(data["height_cm"]),
        weight_kg=float(data["weight_kg"]),
        body_fat_pct=data.get("body_fat_pct"),
    )
    tdee = calculate_tdee(bmr, data["schedule"])
    return calculate_macros(tdee, data["goal"])


def build_profile_summary(data: dict, macros: dict) -> str:
    gender_label = "Мужской" if data["gender"] == "male" else "Женский"
    body_fat = f"{data['body_fat_pct']}%" if data.get("body_fat_pct") else "не указан"
    health = ", ".join(HEALTH_LABELS.get(h, h) for h in data.get("health_issues", []))
    equip = ", ".join(EQUIPMENT_LABELS.get(e, e) for e in data.get("equipment", []))
    formula = "Кетч-МакАрдл" if data.get("body_fat_pct") else "Миффлин-Сан Жеор"

    warnings: list[str] = []
    for issue in data.get("health_issues", []):
        if issue in FORBIDDEN_EXERCISES:
            ex = ", ".join(FORBIDDEN_EXERCISES[issue])
            warnings.append(f"⚠️ Исключены: {ex}")
    warning_block = ("\n\n" + "\n".join(warnings)) if warnings else ""

    return (
        f"📋 *Твой профиль P.A.R.K.E.R.*\n\n"
        f"🎯 Цель: {GOAL_LABELS.get(data['goal'], data['goal'])}\n"
        f"👤 Пол: {gender_label}\n"
        f"🔢 Возраст: {data['age']} лет\n"
        f"📏 Рост: {data['height_cm']} см\n"
        f"⚖️ Вес: {data['weight_kg']} кг\n"
        f"💧 % жира: {body_fat}\n"
        f"⏰ График: {SCHEDULE_LABELS.get(data['schedule'], data['schedule'])}\n"
        f"🏥 Здоровье: {health}\n"
        f"🏋️ Оборудование: {equip}\n\n"
        f"📊 *Расчёт КБЖУ* ({formula})\n"
        f"🔥 Калории: {macros['calories']} ккал\n"
        f"🥩 Белки: {macros['protein_g']} г\n"
        f"🫒 Жиры: {macros['fat_g']} г\n"
        f"🍞 Углеводы: {macros['carb_g']} г"
        f"{warning_block}"
    )
