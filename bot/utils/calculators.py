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


def calculate_tdee(bmr: float, schedule: str) -> float:
    return bmr * ACTIVITY_MULTIPLIERS.get(schedule, 1.375)


def calculate_macros(tdee: float, goal: str) -> dict:
    adjustments = {
        "lose_weight":   (-400, 0.35, 0.25, 0.40),
        "gain_muscle":   (+300, 0.30, 0.25, 0.45),
        "recomposition": (   0, 0.35, 0.30, 0.35),
        "maintain":      (   0, 0.25, 0.30, 0.45),
    }
    delta, p_ratio, f_ratio, c_ratio = adjustments.get(goal, (0, 0.25, 0.30, 0.45))
    calories = tdee + delta
    return {
        "calories":  int(calories),
        "protein_g": int(calories * p_ratio / 4),
        "fat_g":     int(calories * f_ratio / 9),
        "carb_g":    int(calories * c_ratio / 4),
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
