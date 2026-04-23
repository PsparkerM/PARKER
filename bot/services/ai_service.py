import logging
from bot.config import ANTHROPIC_API_KEY

GOAL_LABELS = {
    "lose_weight": "похудение",
    "gain_muscle": "набор мышечной массы",
    "maintain": "поддержание формы",
    "recomposition": "рекомпозиция тела",
}

SCHEDULE_LABELS = {
    "standard": "стандартный (~8 ч)",
    "12h": "интенсивный (12 ч)",
    "16h+": "тяжёлый (16+ ч)",
    "shift": "сменный график",
}

PARKER_CHAT_SYSTEM = """Ты — Петр, персональный тренер, нутрициолог и наставник пользователя в приложении P.A.R.K.E.R.

ЛИЧНОСТЬ:
Говоришь как близкий друг который реально разбирается в спорте и питании.
Прямо, тепло, иногда с лёгким юмором, но всегда конкретно — никакой воды.
Не сюсюкаешь, но поддерживаешь. Ты тренер, а не мотивационный спикер.
Даёшь советы с конкретными цифрами: граммы, подходы, время, проценты.
Знаешь биохимию и физиологию на уровне эксперта.
Понимаешь реальную жизнь — не идеальные условия, а усталость и нехватку времени.

ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:
{profile_block}

ЗАПРЕТЫ ПО ЗДОРОВЬЮ (АБСОЛЮТНЫЕ):
{health_rules}

ПРАВИЛА:
- Отвечай коротко если вопрос простой, развёрнуто если нужны детали
- Если просят план или расчёт — давай конкретные цифры
- Медицинский дисклеймер добавляй только если речь идёт о серьёзных изменениях в питании или тренировках
- Всегда на русском языке
- Обращайся по имени если знаешь его"""

PARKER_SYSTEM_PROMPT = """Ты — P.A.R.K.E.R. (Personal Adaptive Resource & Kinetic Energy Regulator).
Ты персональный AI-нутрициолог и тренер. Ты — цифровой двойник лучшего специалиста.
Твоя задача: заменить живого тренера и диетолога на 100%.

═══ ТВОЯ ЛИЧНОСТЬ ═══
Ты профессионал. Говоришь прямо, конкретно, без воды.
Ты знаешь биохимию, физиологию, нутрициологию на уровне эксперта.
Ты понимаешь реальную жизнь людей — не идеальные условия, а смены по 16 часов и нестабильный сон.
Ты заботишься о пользователе, но не сюсюкаешь. Ты тренер, а не мотивационный спикер.

═══ ЖЁСТКИЕ ПРАВИЛА (НАРУШАТЬ НЕЛЬЗЯ) ═══

1. ЗАПРЕТЫ ПО ЗДОРОВЬЮ — АБСОЛЮТНЫЕ:
   • back_problems / сколиоз → НИКОГДА: становая тяга, приседания со штангой,
     гиперэкстензия с весом, наклоны с отягощением, жим ногами с полной амплитудой
   • knee_issues → НИКОГДА: глубокие приседания с весом, выпады с отягощением,
     запрыгивания на тумбу, бег по твёрдой поверхности
   • hypertension → НИКОГДА: тяжёлый жим над головой, натуживание (задержка дыхания),
     упражнения головой вниз

2. РЕЖИМ «16Ч+»:
   Максимум 3 приёма пищи. Всё съедается за 2–3 минуты.
   Упор на жидкие калории (гейнер, протеин, смузи). Никаких блюд с готовкой.
   Тренировка: только если есть 30 минут. Иначе — 5 мин растяжки + витамины.

3. ТОЧНОСТЬ:
   Всегда указывай: граммы продуктов, время приёмов, количество подходов × повторений,
   вес отягощения (если известен), время отдыха между подходами.

4. МЕДИЦИНСКИЙ ДИСКЛЕЙМЕР:
   Каждый план заканчивается строкой:
   ⚠️ Проконсультируйся с врачом перед началом программы.

═══ ФОРМАТ ПЛАНА ПИТАНИЯ ═══
🍽 ПЛАН ПИТАНИЯ — [цель] | [КБЖУ]

[время] [Приём N]:
• [Продукт] — [граммы]
• [Продукт] — [граммы]
Итого: ~[ккал] ккал | Б:[г]г Ж:[г]г У:[г]г

[Повтори для каждого приёма]

💧 Вода: [норма] мл/день
💊 Добавки: [список если нужны]

⚠️ Проконсультируйся с врачом перед началом программы.

═══ ФОРМАТ ТРЕНИРОВОЧНОГО ПЛАНА ═══
🏋️ ТРЕНИРОВОЧНЫЙ ПЛАН — [тип: Дом/Зал/Бассейн/ЛФК]

[Если есть ограничения здоровья — сначала блок:]
⚠️ ИСКЛЮЧЕНО из-за [причина]: [список упражнений]

[День N] — [группа мышц/тип]:
1. [Упражнение] — [N×N] [вес если есть] | Отдых: [сек]
2. [Упражнение] — [N×N] | Отдых: [сек]
...

Общее время: ~[мин] мин
Частота: [N] раз в неделю

⚠️ Проконсультируйся с врачом перед началом программы."""

NUTRITION_USER_TEMPLATE = """\
Составь персональный план питания на день.

ПРОФИЛЬ:
• Цель: {goal}
• Пол: {gender} | Возраст: {age} лет
• Рост: {height_cm} см | Вес: {weight_kg} кг
• % жира: {body_fat}
• Рабочий график: {schedule}
• Проблемы со здоровьем: {health}
• Оборудование: {equipment}

КБЖУ (рассчитано):
🔥 {calories} ккал | 🥩 Б:{protein_g}г | 🫒 Ж:{fat_g}г | 🍞 У:{carb_g}г

ДОПОЛНИТЕЛЬНО:
• Адаптируй количество и время приёмов строго под рабочий график
• Если 16ч+ — только быстрые варианты (≤3 мин на приём)
• Учти все ограничения здоровья при выборе продуктов
• Укажи точные граммовки и время каждого приёма"""

WORKOUT_USER_TEMPLATE = """\
Составь персональную программу тренировок.

ПРОФИЛЬ:
• Цель: {goal}
• Пол: {gender} | Возраст: {age} лет
• Рост: {height_cm} см | Вес: {weight_kg} кг
• Рабочий график: {schedule}
• Проблемы со здоровьем: {health}
• Доступное оборудование: {equipment}

ТРЕБОВАНИЯ:
• Строго исключи все упражнения, запрещённые по состоянию здоровья
• Если есть сколиоз/спина — обязательный ЛФК-блок в начале каждой тренировки
• Если 16ч+ — тренировка не более 30 минут, или только растяжка
• Подбери частоту тренировок под рабочий график
• Укажи подходы × повторения, время отдыха, примерный вес"""


def _build_profile_block(profile: dict) -> str:
    if not profile:
        return "Профиль ещё не заполнен."
    lines = []
    if profile.get("name"):
        lines.append(f"Имя: {profile['name']}")
    if profile.get("goal"):
        lines.append(f"Цель: {GOAL_LABELS.get(profile['goal'], profile['goal'])}")
    if profile.get("gender"):
        lines.append(f"Пол: {'мужской' if profile['gender'] == 'male' else 'женский'}")
    if profile.get("age"):
        lines.append(f"Возраст: {profile['age']} лет")
    if profile.get("height_cm"):
        lines.append(f"Рост: {profile['height_cm']} см")
    if profile.get("weight_kg"):
        lines.append(f"Вес: {profile['weight_kg']} кг")
    if profile.get("body_fat_pct"):
        lines.append(f"% жира: {profile['body_fat_pct']}%")
    if profile.get("schedule"):
        lines.append(f"График: {SCHEDULE_LABELS.get(profile['schedule'], profile['schedule'])}")
    hi = profile.get("health_issues", [])
    if hi and hi != ["none"]:
        lines.append(f"Здоровье/травмы: {', '.join(hi)}")
    eq = profile.get("equipment", [])
    if eq:
        lines.append(f"Оборудование: {', '.join(eq)}")
    return "\n".join(lines) if lines else "Профиль частично заполнен."


def _build_health_rules(profile: dict) -> str:
    health = profile.get("health_issues", [])
    rules = []
    if "back_problems" in health:
        rules.append("Спина/сколиоз → НЕЛЬЗЯ: становая тяга, приседания со штангой, гиперэкстензия, наклоны с весом")
    if "knee_issues" in health:
        rules.append("Колени → НЕЛЬЗЯ: глубокие приседания с весом, выпады с отягощением, прыжки на тумбу, бег по асфальту")
    if "hypertension" in health:
        rules.append("Гипертония → НЕЛЬЗЯ: тяжёлый жим над головой, натуживание, упражнения головой вниз")
    return "\n".join(rules) if rules else "Ограничений нет."


FOOD_SYSTEM = """Ты — эксперт-нутрициолог. Тебе дают список продуктов с граммовкой на русском языке.
Рассчитай КБЖУ каждого продукта и суммарные значения по стандартным таблицам питательности.

Верни ТОЛЬКО валидный JSON без какого-либо текста до или после:
{
  "items": [
    {"name": "название продукта", "amount_g": 200, "calories": 330, "protein_g": 46.0, "fat_g": 7.2, "carb_g": 0.0}
  ],
  "total": {"calories": 330, "protein_g": 46.0, "fat_g": 7.2, "carb_g": 0.0}
}

Правила:
- Округляй калории до целых, БЖУ до 1 знака после запятой
- Если граммовка не указана — предполагай стандартную порцию (100г, 1 шт и т.д.) и укажи её
- Если продукт не распознан — включи его с нулевыми значениями и пометь name как "? [название]"
- Используй значения для варёных/готовых продуктов если не указано иное"""


async def calculate_food_macros(text: str) -> dict:
    if not ANTHROPIC_API_KEY:
        return {"error": "AI недоступен"}
    try:
        import anthropic, json, re
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            system=FOOD_SYSTEM,
            messages=[{"role": "user", "content": f"Рассчитай КБЖУ: {text}"}],
        )
        raw = msg.content[0].text.strip()
        # Extract JSON even if there's extra text
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if not m:
            return {"error": "Не удалось распознать продукты"}
        return json.loads(m.group())
    except Exception:
        logging.exception("food calc error")
        return {"error": "Ошибка расчёта КБЖУ"}


async def generate_chat_response(message: str, history: list, profile: dict) -> str:
    if not ANTHROPIC_API_KEY:
        return "AI временно недоступен. Попробуй позже."
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        system = PARKER_CHAT_SYSTEM.format(
            profile_block=_build_profile_block(profile),
            health_rules=_build_health_rules(profile),
        )
        messages = history[-20:] + [{"role": "user", "content": message}]
        msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=system,
            messages=messages,
        )
        return msg.content[0].text
    except Exception:
        logging.exception("Claude chat error")
        return "Не удалось получить ответ. Попробуй ещё раз."


async def generate_nutrition_plan(profile: dict, macros: dict) -> str:
    if ANTHROPIC_API_KEY:
        return await _claude_nutrition(profile, macros)
    return _fallback_nutrition(profile, macros)


async def generate_workout_plan(profile: dict) -> str:
    if ANTHROPIC_API_KEY:
        return await _claude_workout(profile)
    return _fallback_workout(profile)


async def _claude_nutrition(profile: dict, macros: dict) -> str:
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        health = ", ".join(profile.get("health_issues", [])) or "нет"
        equip = ", ".join(profile.get("equipment", [])) or "нет"
        body_fat = f"{profile.get('body_fat_pct')}%" if profile.get("body_fat_pct") else "не указан"

        prompt = NUTRITION_USER_TEMPLATE.format(
            goal=profile.get("goal"),
            gender="Мужской" if profile.get("gender") == "male" else "Женский",
            age=profile.get("age"),
            height_cm=profile.get("height_cm"),
            weight_kg=profile.get("weight_kg"),
            body_fat=body_fat,
            schedule=profile.get("schedule"),
            health=health,
            equipment=equip,
            calories=macros["calories"],
            protein_g=macros["protein_g"],
            fat_g=macros["fat_g"],
            carb_g=macros["carb_g"],
        )

        msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=PARKER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception:
        logging.exception("Claude nutrition error")
        return _fallback_nutrition(profile, macros)


async def _claude_workout(profile: dict) -> str:
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        health = ", ".join(profile.get("health_issues", [])) or "нет"
        equip = ", ".join(profile.get("equipment", [])) or "нет"

        prompt = WORKOUT_USER_TEMPLATE.format(
            goal=profile.get("goal"),
            gender="Мужской" if profile.get("gender") == "male" else "Женский",
            age=profile.get("age"),
            height_cm=profile.get("height_cm"),
            weight_kg=profile.get("weight_kg"),
            schedule=profile.get("schedule"),
            health=health,
            equipment=equip,
        )

        msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=PARKER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception:
        logging.exception("Claude workout error")
        return _fallback_workout(profile)


def _fallback_nutrition(profile: dict, macros: dict) -> str:
    cal = macros["calories"]
    pro = macros["protein_g"]
    fat = macros["fat_g"]
    carb = macros["carb_g"]
    schedule = profile.get("schedule", "standard")

    if schedule == "16h+":
        return (
            f"🍽 ПЛАН ПИТАНИЯ — Режим 16ч+\n"
            f"📊 {cal} ккал | Б:{pro}г Ж:{fat}г У:{carb}г\n\n"
            "🌅 До смены (07:00):\n"
            "• Гейнер / протеиновый коктейль на молоке — 600 мл (~500 ккал)\n"
            "• Банан — 1 шт\n\n"
            "⏰ На смене (перерыв, 2–3 мин):\n"
            "• Творог 5% — 200г\n"
            "• Протеиновый батончик — 1 шт\n\n"
            "🌙 После смены:\n"
            "• Куриная грудка — 250г\n"
            "• Гречка отварная — 200г\n"
            "• Овощной салат с оливковым маслом\n\n"
            "💊 Добавки: Магний + ZMA перед сном, Витамин D3\n\n"
            "⚠️ Проконсультируйся с врачом перед началом программы."
        )

    if schedule == "12h":
        return (
            f"🍽 ПЛАН ПИТАНИЯ — График 12ч\n"
            f"📊 {cal} ккал | Б:{pro}г Ж:{fat}г У:{carb}г\n\n"
            "🌅 Завтрак (07:00):\n"
            "• Овсянка на молоке — 100г сухой\n"
            "• 3 яйца (омлет)\n"
            "• Фрукты — 150г\n\n"
            "🕛 Обед (12:00):\n"
            "• Куриная грудка / индейка — 200г\n"
            "• Рис / гречка — 150г\n"
            "• Овощи свежие — 200г\n\n"
            "🕔 Перекус (16:00):\n"
            "• Творог 5% — 200г\n"
            "• Орехи — 30г\n\n"
            "🌙 Ужин (после смены):\n"
            "• Рыба / говядина — 200г\n"
            "• Овощной салат с маслом\n"
            "• Кефир 1% — 250 мл\n\n"
            "💊 Добавки: Омега-3, Магний\n\n"
            "⚠️ Проконсультируйся с врачом перед началом программы."
        )

    return (
        f"🍽 ПЛАН ПИТАНИЯ — Стандартный график\n"
        f"📊 {cal} ккал | Б:{pro}г Ж:{fat}г У:{carb}г\n\n"
        "🌅 Завтрак (07:30):\n"
        "• Овсянка — 80г + фрукты\n"
        "• 3 яйца\n\n"
        "🕙 Перекус (10:30):\n"
        "• Творог 5% — 150г\n"
        "• Горсть орехов — 25г\n\n"
        "🕐 Обед (13:00):\n"
        "• Куриная грудка — 200г\n"
        "• Гречка / рис — 200г\n"
        "• Овощи + оливковое масло\n\n"
        "🕔 Перекус (16:00):\n"
        "• Яблоко + 20г миндаля\n"
        "• Кефир 1% — 200 мл\n\n"
        "🌙 Ужин (19:00):\n"
        "• Рыба / говядина / индейка — 200г\n"
        "• Овощи на пару\n"
        "• Кефир 1% — 250 мл\n\n"
        "⚠️ Проконсультируйся с врачом перед началом программы."
    )


def _fallback_workout(profile: dict) -> str:
    equipment = profile.get("equipment", ["none"])
    health = profile.get("health_issues", [])
    schedule = profile.get("schedule", "standard")

    warnings = []
    if "back_problems" in health:
        warnings.append("⚠️ ИСКЛЮЧЕНО (спина/сколиоз): становая тяга, приседания со штангой, гиперэкстензия")
    if "knee_issues" in health:
        warnings.append("⚠️ ИСКЛЮЧЕНО (колени): глубокие приседания с весом, выпады с отягощением")
    if "hypertension" in health:
        warnings.append("⚠️ ИСКЛЮЧЕНО (гипертония): тяжёлый жим над головой, натуживание")

    warning_block = ("\n".join(warnings) + "\n\n") if warnings else ""

    if schedule == "16h+":
        return (
            f"🏋️ ТРЕНИРОВОЧНЫЙ ПЛАН — Режим 16ч+\n\n"
            f"{warning_block}"
            "⏱ Длительность: 5–10 минут (восстановление)\n\n"
            "Ежедневно перед сном:\n"
            "1. Растяжка шеи и плеч — 2 мин\n"
            "2. Растяжка спины (кошка-корова) — 2 мин\n"
            "3. Растяжка ног и бёдер — 2 мин\n"
            "4. Диафрагмальное дыхание — 2 мин\n\n"
            "💊 Обязательно: Магний 400мг + Витамин D3 перед сном\n\n"
            "⚠️ Проконсультируйся с врачом перед началом программы."
        )

    if "gym" in equipment:
        return (
            f"🏋️ ТРЕНИРОВОЧНЫЙ ПЛАН — Спортзал\n\n"
            f"{warning_block}"
            "Частота: 3 раза в неделю\n\n"
            "День A — Грудь + Трицепс:\n"
            "1. Жим штанги лёжа — 4×8 | Отдых: 90 сек\n"
            "2. Жим гантелей на наклонной — 3×10 | Отдых: 60 сек\n"
            "3. Разводка гантелей — 3×12 | Отдых: 60 сек\n"
            "4. Французский жим — 3×12 | Отдых: 60 сек\n"
            "5. Трицепс на блоке — 3×15 | Отдых: 45 сек\n\n"
            "День B — Спина + Бицепс:\n"
            "1. Подтягивания / тяга блока — 4×8 | Отдых: 90 сек\n"
            "2. Тяга гантели в наклоне — 3×10 (каждая рука) | Отдых: 60 сек\n"
            "3. Тяга нижнего блока — 3×12 | Отдых: 60 сек\n"
            "4. Сгибание рук с гантелями — 3×12 | Отдых: 60 сек\n\n"
            "День C — Ноги + Плечи:\n"
            "1. Жим ногами — 4×10 | Отдых: 90 сек\n"
            "2. Разгибание ног в тренажёре — 3×12 | Отдых: 60 сек\n"
            "3. Сгибание ног в тренажёре — 3×12 | Отдых: 60 сек\n"
            "4. Жим гантелей сидя — 3×10 | Отдых: 60 сек\n"
            "5. Подъём гантелей через стороны — 3×15 | Отдых: 45 сек\n\n"
            "⚠️ Проконсультируйся с врачом перед началом программы."
        )

    return (
        f"🏋️ ТРЕНИРОВОЧНЫЙ ПЛАН — Дома\n\n"
        f"{warning_block}"
        "Частота: 3 раза в неделю\n\n"
        "День A — Верх тела:\n"
        "1. Отжимания — 4×12 | Отдых: 60 сек\n"
        "2. Отжимания узким хватом — 3×10 | Отдых: 60 сек\n"
        "3. Планка — 3×45 сек | Отдых: 30 сек\n"
        "4. Обратные отжимания от стула — 3×12 | Отдых: 60 сек\n\n"
        "День B — Низ тела:\n"
        "1. Приседания — 4×15 | Отдых: 60 сек\n"
        "2. Ягодичный мостик — 4×15 | Отдых: 45 сек\n"
        "3. Выпады — 3×12 каждая нога | Отдых: 60 сек\n"
        "4. Подъём на носки — 3×20 | Отдых: 30 сек\n\n"
        "День C — Всё тело (кардио):\n"
        "1. Берпи — 4×8 | Отдых: 60 сек\n"
        "2. Прыжки с разведением рук — 3×20 | Отдых: 45 сек\n"
        "3. Скалолаз — 3×20 (каждая нога) | Отдых: 45 сек\n"
        "4. Планка с касанием плеч — 3×12 | Отдых: 45 сек\n\n"
        "⚠️ Проконсультируйся с врачом перед началом программы."
    )
