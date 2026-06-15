# Множители по реальному уровню активности (классические Харрис-Бенедикт).
# Это корректная основа TDEE — привязка к тренировочной нагрузке, а не к смене.
ACTIVITY_LEVELS = {
    "sedentary":   1.2,    # сидячий, без тренировок
    "light":       1.375,  # лёгкие 1–3 трен/нед
    "moderate":    1.55,   # умеренные 3–5 трен/нед
    "active":      1.725,  # интенсивные 6–7 трен/нед
    "very_active": 1.9,    # физ. работа + тренировки
}

# Legacy-фоллбэк: множитель по длине смены (когда уровень активности не задан).
ACTIVITY_MULTIPLIERS = {
    "standard": 1.375,
    "12h":      1.55,
    "16h+":     1.725,
    "shift":    1.55,
}

GOAL_LABELS = {
    "lose_weight":   "Похудеть 🔥",
    "gain_muscle":   "Набрать массу 💪",
    "maintain":      "Поддержать форму ⚖️",
    "recomposition": "Рекомпозиция 🔄",
}

SCHEDULE_LABELS = {
    "standard": "Стандартный (8ч)",
    "12h":      "Интенсивный (12ч)",
    "16h+":     "Тяжёлый (16ч+)",
    "shift":    "Сменный график",
}

HEALTH_LABELS = {
    "none":           "Нет проблем",
    "back_problems":  "Проблемы со спиной / сколиоз",
    "knee_issues":    "Проблемы с коленями",
    "hypertension":   "Гипертония",
}

EQUIPMENT_LABELS = {
    "none":      "Без оборудования",
    "dumbbells": "Гантели",
    "barbell":   "Штанга / гриф",
    "gym":       "Спортзал",
    "pool":      "Бассейн",
}


def calculate_bmr(gender: str, age: int, height_cm: int,
                  weight_kg: float, body_fat_pct=None) -> float:
    if body_fat_pct is not None:
        lbm = weight_kg * (1 - body_fat_pct / 100)
        return 370 + 21.6 * lbm
    if gender == "male":
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161


def calculate_tdee(bmr: float, schedule: str, activity: str | None = None) -> float:
    # Уровень активности точнее графика — используем его, если задан.
    if activity and activity in ACTIVITY_LEVELS:
        return bmr * ACTIVITY_LEVELS[activity]
    return bmr * ACTIVITY_MULTIPLIERS.get(schedule, 1.375)


# Минимально безопасный суточный калораж — чтобы дефицит не уводил в опасную зону.
# Стандартные клинические нижние границы для самостоятельного питания.
CALORIE_FLOOR = {"male": 1500, "female": 1200}

# Минимум белка на кг массы тела (сохранение мышц, особенно в дефиците).
PROTEIN_PER_KG = 1.8


def calculate_macros(tdee: float, goal: str,
                     weight_kg: float | None = None,
                     gender: str = "male") -> dict:
    adjustments = {
        "lose_weight":   (-400, 0.35, 0.25, 0.40),
        "gain_muscle":   (+300, 0.30, 0.25, 0.45),
        "recomposition": (   0, 0.35, 0.30, 0.35),
        "maintain":      (   0, 0.25, 0.30, 0.45),
    }
    delta, p_ratio, f_ratio, c_ratio = adjustments.get(goal, (0, 0.25, 0.30, 0.45))
    calories = tdee + delta

    # 1) Не опускаемся ниже безопасного минимума калорий.
    floor = CALORIE_FLOOR.get(gender, 1200)
    if calories < floor:
        calories = floor

    # 2) Белок: берём максимум из доли калоража и 1.8 г/кг массы тела.
    protein_g = calories * p_ratio / 4
    if weight_kg:
        protein_g = max(protein_g, PROTEIN_PER_KG * weight_kg)

    fat_g = calories * f_ratio / 9

    # 3) Углеводы — остаток калорий после белка и жира (чтобы сумма сходилась
    #    с калоражом даже после поднятия белка по массе тела).
    carb_g = max(0.0, (calories - protein_g * 4 - fat_g * 9) / 4)

    return {
        "calories":  int(round(calories)),
        "protein_g": int(round(protein_g)),
        "fat_g":     int(round(fat_g)),
        "carb_g":    int(round(carb_g)),
    }


def compute_macros_for_profile(data: dict) -> dict:
    weight_kg = float(data["weight_kg"])
    gender = data["gender"]
    bmr = calculate_bmr(
        gender=gender,
        age=int(data["age"]),
        height_cm=int(data["height_cm"]),
        weight_kg=weight_kg,
        body_fat_pct=data.get("body_fat_pct"),
    )
    tdee = calculate_tdee(bmr, data["schedule"], data.get("activity"))
    return calculate_macros(tdee, data["goal"], weight_kg=weight_kg, gender=gender)
