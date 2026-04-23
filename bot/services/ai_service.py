import logging
import json
import re
import anthropic

from bot.config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
#  Shared client (lazy, singleton)
# ──────────────────────────────────────────────
_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY не задан")
        _client = anthropic.AsyncAnthropic(
            api_key=ANTHROPIC_API_KEY,
            timeout=30.0,
            max_retries=1,
        )
    return _client


MODEL = "claude-sonnet-4-6"

# ──────────────────────────────────────────────
#  Label maps
# ──────────────────────────────────────────────
GOAL_LABELS = {
    "lose_weight":   "похудение",
    "gain_muscle":   "набор мышечной массы",
    "maintain":      "поддержание формы",
    "recomposition": "рекомпозиция тела",
}

SCHEDULE_LABELS = {
    "standard": "стандартный (~8 ч)",
    "12h":      "интенсивный (12 ч)",
    "16h+":     "тяжёлый (16+ ч)",
    "shift":    "сменный график",
}

# ──────────────────────────────────────────────
#  System prompts
# ──────────────────────────────────────────────
ARNI_SYSTEM = """\
Ты — Арнольд, он же Арни. Персональный тренер, нутрициолог и наставник в приложении P.A.R.K.E.R.

ЛИЧНОСТЬ:
Говоришь как близкий друг, который реально разбирается в спорте и питании.
Прямо, тепло, иногда с лёгким юмором — но всегда конкретно, никакой воды.
Не сюсюкаешь, но поддерживаешь. Ты тренер, а не мотивационный спикер.
Даёшь советы с конкретными цифрами: граммы, подходы, время, проценты.
Знаешь биохимию и физиологию на уровне эксперта.
Понимаешь реальную жизнь — усталость, нехватку времени, стресс.

ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:
%%PROFILE%%

ЗАПРЕТЫ ПО ЗДОРОВЬЮ (АБСОЛЮТНЫЕ):
%%HEALTH%%

ПРАВИЛА ОТВЕТОВ:
- Короткий вопрос → короткий ответ. Просят расчёт → конкретные цифры.
- Обращайся по имени если знаешь его.
- Всегда на русском языке.
- Медицинский дисклеймер только при серьёзных изменениях питания/тренировок.\
"""

PARKER_SYSTEM_PROMPT = """\
Ты — P.A.R.K.E.R. AI-нутрициолог и тренер. Цифровой двойник лучшего специалиста.
Говоришь прямо, конкретно, без воды. Знаешь биохимию и физиологию на уровне эксперта.
Понимаешь реальную жизнь: смены 16 ч, нестабильный сон, ограниченное время.

ЗАПРЕТЫ ПО ЗДОРОВЬЮ — АБСОЛЮТНЫЕ:
back_problems → НИКОГДА: становая тяга, приседания со штангой, гиперэкстензия с весом
knee_issues → НИКОГДА: глубокие приседания с весом, выпады с отягощением, прыжки на тумбу
hypertension → НИКОГДА: тяжёлый жим над головой, натуживание, упражнения головой вниз

РЕЖИМ 16Ч+: максимум 3 приёма, жидкие калории, тренировка ≤30 мин или только растяжка.

Каждый план заканчивается строкой:
⚠️ Проконсультируйся с врачом перед началом программы.\
"""

NUTRITION_TEMPLATE = """\
Составь персональный план питания на 7 дней (Пн–Вс).

ПРОФИЛЬ:
Цель: {goal}
Пол: {gender} | Возраст: {age} лет
Рост: {height_cm} см | Вес: {weight_kg} кг
Жир: {body_fat}
График: {schedule}
Здоровье: {health}
Оборудование: {equipment}

КБЖУ: {calories} ккал | Б:{protein_g}г | Ж:{fat_g}г | У:{carb_g}г

ФОРМАТ — строго для каждого дня:
[ДЕНЬ] Понедельник
Завтрак (08:00): продукт — Xг → ~Xккал
Обед (13:00): ...
Ужин (19:00): ...
💧 Вода: X мл

Требования:
- Разные продукты каждый день, не повторяй
- Под график (16ч+ — 3 приёма, быстрые варианты)
- Точные граммовки
- В конце — ДОБАВКИ если нужны\
"""

WORKOUT_TEMPLATE = """\
Составь программу тренировок на неделю (Пн–Вс).

ПРОФИЛЬ:
Цель: {goal}
Пол: {gender} | Возраст: {age} лет | Вес: {weight_kg} кг
График: {schedule}
Здоровье: {health}
Оборудование: {equipment}

ФОРМАТ — строго по дням:
[ДЕНЬ] Понедельник — Грудь + Трицепс
1. Жим лёжа — 4×8, отдых 90 сек
...
⏱ Время: ~60 мин

[ДЕНЬ] Вторник — ОТДЫХ
Лёгкая прогулка 30 мин

Требования:
- Строго исключи запрещённые упражнения по здоровью
- Спина/сколиоз → ЛФК-разминка 5 мин перед тренировкой
- 16ч+ → тренировки ≤30 мин или только растяжка
- Подходы × повторения, отдых, вес для каждого упражнения\
"""

FOOD_SYSTEM = """\
Ты — эксперт-нутрициолог. Тебе дают список продуктов с граммовкой.
Рассчитай КБЖУ каждого продукта и суммарные значения по стандартным таблицам.

Верни ТОЛЬКО валидный JSON (без текста до/после):
{"items":[{"name":"...","amount_g":200,"calories":330,"protein_g":46.0,"fat_g":7.2,"carb_g":0.0}],"total":{"calories":330,"protein_g":46.0,"fat_g":7.2,"carb_g":0.0}}

Правила:
- Калории — целые, БЖУ — 1 знак после запятой
- Граммовка не указана → стандартная порция (100г / 1 шт)
- Продукт не распознан → name "? название", нули
- Используй значения для варёных/готовых если не указано иное\
"""

PHOTO_FOOD_SYSTEM = """\
Ты — эксперт-нутрициолог. Тебе показывают фото еды. Определи продукты, оцени граммы, рассчитай КБЖУ.

Верни ТОЛЬКО валидный JSON:
{"items":[{"name":"...","amount_g":150,"calories":200,"protein_g":15.0,"fat_g":8.0,"carb_g":18.0}],"total":{"calories":200,"protein_g":15.0,"fat_g":8.0,"carb_g":18.0},"description":"Краткое описание блюда"}

Правила:
- Оценивай количество по размеру порции (ладонь = ~150г белка, стандартная тарелка)
- Составное блюдо — разбей на компоненты
- Если еда не видна → {"error":"Не удалось распознать еду на фото"}\
"""

ADAPT_SYSTEM = """\
Ты — Арни, персональный тренер и нутрициолог. Анализируй недельный прогресс.
Дай конкретные рекомендации по корректировке плана.

Верни ТОЛЬКО валидный JSON:
{"summary":"2-3 предложения о прогрессе","weight_trend":"gaining","calorie_adjust":200,"recommendations":["рекомендация 1","рекомендация 2","рекомендация 3"],"motivation":"мотивирующее сообщение от Арни"}

weight_trend: gaining | losing | stable
calorie_adjust: число со знаком (+/-), 0 если менять не нужно\
"""


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────
def _build_profile_block(profile: dict) -> str:
    if not profile:
        return "Профиль не заполнен."
    parts = []
    if profile.get("name"):        parts.append(f"Имя: {profile['name']}")
    if profile.get("goal"):        parts.append(f"Цель: {GOAL_LABELS.get(profile['goal'], profile['goal'])}")
    if profile.get("gender"):      parts.append(f"Пол: {'мужской' if profile['gender']=='male' else 'женский'}")
    if profile.get("age"):         parts.append(f"Возраст: {profile['age']} лет")
    if profile.get("height_cm"):   parts.append(f"Рост: {profile['height_cm']} см")
    if profile.get("weight_kg"):   parts.append(f"Вес: {profile['weight_kg']} кг")
    if profile.get("body_fat_pct"):parts.append(f"% жира: {profile['body_fat_pct']}%")
    if profile.get("schedule"):    parts.append(f"График: {SCHEDULE_LABELS.get(profile['schedule'], profile['schedule'])}")
    hi = [x for x in profile.get("health_issues", []) if x != "none"]
    if hi: parts.append(f"Здоровье/травмы: {', '.join(hi)}")
    eq = profile.get("equipment", [])
    if eq: parts.append(f"Оборудование: {', '.join(eq)}")
    return "\n".join(parts) or "Профиль частично заполнен."


def _build_health_rules(profile: dict) -> str:
    health = profile.get("health_issues", [])
    rules = []
    if "back_problems" in health:
        rules.append("Спина → НЕЛЬЗЯ: становая тяга, приседания со штангой, гиперэкстензия")
    if "knee_issues" in health:
        rules.append("Колени → НЕЛЬЗЯ: глубокие приседания с весом, выпады с отягощением, прыжки")
    if "hypertension" in health:
        rules.append("Гипертония → НЕЛЬЗЯ: тяжёлый жим над головой, натуживание")
    return "\n".join(rules) or "Ограничений нет."


def _sanitize_history(history: list) -> list:
    """Ensure valid alternating user/assistant sequence for Anthropic API."""
    clean = []
    for msg in history:
        role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
        content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
        if role not in ("user", "assistant") or not content:
            continue
        content = str(content).strip()
        if not content:
            continue
        if clean and clean[-1]["role"] == role:
            # merge consecutive same-role messages
            clean[-1]["content"] += "\n" + content
        else:
            clean.append({"role": role, "content": content})
    return clean


def _extract_json(raw: str) -> dict:
    """Extract first JSON object from raw text."""
    raw = raw.strip()
    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Find the outermost {...}
    m = re.search(r'\{[\s\S]*\}', raw)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    raise ValueError(f"No valid JSON in response: {raw[:200]}")


# ──────────────────────────────────────────────
#  Chat
# ──────────────────────────────────────────────
async def generate_chat_response(message: str, history: list, profile: dict) -> str:
    if not ANTHROPIC_API_KEY:
        return "Арни временно недоступен — API ключ не задан."
    try:
        client = _get_client()
        system = (
            ARNI_SYSTEM
            .replace("%%PROFILE%%", _build_profile_block(profile))
            .replace("%%HEALTH%%", _build_health_rules(profile))
        )
        safe_hist = _sanitize_history(history)
        # Must end on assistant (or be empty) before we append user
        if safe_hist and safe_hist[-1]["role"] == "user":
            safe_hist = safe_hist[:-1]
        messages = safe_hist[-18:] + [{"role": "user", "content": message}]
        msg = await client.messages.create(
            model=MODEL,
            max_tokens=1200,
            system=system,
            messages=messages,
        )
        return msg.content[0].text
    except anthropic.AuthenticationError:
        logger.error("Anthropic auth error — check ANTHROPIC_API_KEY")
        return "Арни недоступен — проблема с API ключом. Обратись к администратору."
    except anthropic.RateLimitError:
        logger.warning("Anthropic rate limit hit")
        return "Слишком много запросов — подожди минуту и попробуй ещё раз."
    except anthropic.APITimeoutError:
        logger.warning("Anthropic timeout")
        return "Арни думает дольше обычного — попробуй ещё раз."
    except Exception as e:
        logger.exception("generate_chat_response failed: %s", e)
        return "Арни временно недоступен. Попробуй ещё раз через минуту."


# ──────────────────────────────────────────────
#  Food calc
# ──────────────────────────────────────────────
async def calculate_food_macros(text: str) -> dict:
    if not ANTHROPIC_API_KEY:
        return {"error": "AI недоступен — API ключ не задан"}
    try:
        client = _get_client()
        msg = await client.messages.create(
            model=MODEL,
            max_tokens=900,
            system=FOOD_SYSTEM,
            messages=[{"role": "user", "content": f"Рассчитай КБЖУ: {text}"}],
        )
        return _extract_json(msg.content[0].text)
    except (anthropic.AuthenticationError, anthropic.RateLimitError, anthropic.APITimeoutError) as e:
        logger.error("food_macros API error: %s", e)
        return {"error": f"AI недоступен: {type(e).__name__}"}
    except ValueError as e:
        logger.error("food_macros JSON parse error: %s", e)
        return {"error": "Не удалось разобрать ответ AI — попробуй переформулировать"}
    except Exception as e:
        logger.exception("calculate_food_macros failed: %s", e)
        return {"error": "Ошибка расчёта КБЖУ — попробуй ещё раз"}


async def calculate_food_macros_from_photo(image_b64: str, media_type: str = "image/jpeg") -> dict:
    if not ANTHROPIC_API_KEY:
        return {"error": "AI недоступен"}
    try:
        client = _get_client()
        msg = await client.messages.create(
            model=MODEL,
            max_tokens=900,
            system=PHOTO_FOOD_SYSTEM,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                    {"type": "text", "text": "Что на фото? Рассчитай КБЖУ."},
                ],
            }],
        )
        return _extract_json(msg.content[0].text)
    except (anthropic.AuthenticationError, anthropic.RateLimitError, anthropic.APITimeoutError) as e:
        logger.error("photo_food API error: %s", e)
        return {"error": f"AI недоступен: {type(e).__name__}"}
    except ValueError:
        return {"error": "Не удалось распознать еду на фото"}
    except Exception as e:
        logger.exception("calculate_food_macros_from_photo failed: %s", e)
        return {"error": "Ошибка распознавания фото"}


# ──────────────────────────────────────────────
#  Plans (nutrition + workout)
# ──────────────────────────────────────────────
async def generate_nutrition_plan(profile: dict, macros: dict) -> str:
    if not ANTHROPIC_API_KEY:
        return _fallback_nutrition(profile, macros)
    try:
        client = _get_client()
        hi = [x for x in profile.get("health_issues", []) if x != "none"]
        prompt = NUTRITION_TEMPLATE.format(
            goal=GOAL_LABELS.get(profile.get("goal", ""), profile.get("goal", "—")),
            gender="Мужской" if profile.get("gender") == "male" else "Женский",
            age=profile.get("age", "—"),
            height_cm=profile.get("height_cm", "—"),
            weight_kg=profile.get("weight_kg", "—"),
            body_fat=f"{profile['body_fat_pct']}%" if profile.get("body_fat_pct") else "не указан",
            schedule=SCHEDULE_LABELS.get(profile.get("schedule", ""), profile.get("schedule", "—")),
            health=", ".join(hi) if hi else "нет ограничений",
            equipment=", ".join(profile.get("equipment", [])) or "нет",
            calories=macros["calories"],
            protein_g=macros["protein_g"],
            fat_g=macros["fat_g"],
            carb_g=macros["carb_g"],
        )
        msg = await client.messages.create(
            model=MODEL,
            max_tokens=2500,
            system=PARKER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        logger.exception("generate_nutrition_plan failed: %s", e)
        return _fallback_nutrition(profile, macros)


async def generate_workout_plan(profile: dict) -> str:
    if not ANTHROPIC_API_KEY:
        return _fallback_workout(profile)
    try:
        client = _get_client()
        hi = [x for x in profile.get("health_issues", []) if x != "none"]
        prompt = WORKOUT_TEMPLATE.format(
            goal=GOAL_LABELS.get(profile.get("goal", ""), profile.get("goal", "—")),
            gender="Мужской" if profile.get("gender") == "male" else "Женский",
            age=profile.get("age", "—"),
            weight_kg=profile.get("weight_kg", "—"),
            schedule=SCHEDULE_LABELS.get(profile.get("schedule", ""), profile.get("schedule", "—")),
            health=", ".join(hi) if hi else "нет ограничений",
            equipment=", ".join(profile.get("equipment", [])) or "нет",
        )
        msg = await client.messages.create(
            model=MODEL,
            max_tokens=2500,
            system=PARKER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        logger.exception("generate_workout_plan failed: %s", e)
        return _fallback_workout(profile)


# ──────────────────────────────────────────────
#  Weekly adaptation
# ──────────────────────────────────────────────
async def generate_weekly_adaptation(profile: dict, logs: list, food_logs: list, macros: dict) -> dict:
    if not ANTHROPIC_API_KEY:
        return {"error": "AI недоступен"}
    try:
        client = _get_client()
        weight_vals = [l["weight"] for l in logs if isinstance(l, dict) and l.get("weight")]
        cal_entries = [f.get("total", {}).get("calories", 0) for f in food_logs if isinstance(f, dict) and f.get("total")]
        avg_cal = round(sum(cal_entries) / len(cal_entries)) if cal_entries else 0

        user_msg = (
            f"Пользователь: {profile.get('name','—')}, цель: {GOAL_LABELS.get(profile.get('goal',''), '—')}\n"
            f"Текущие макросы: {macros.get('calories','—')} ккал\n"
            f"Записей за период: {len(logs)}\n"
            f"Вес: {weight_vals[0] if weight_vals else '—'} → {weight_vals[-1] if len(weight_vals)>1 else '—'} кг\n"
            f"Среднее калорий/день: {avg_cal} ккал\n"
            f"Записей сна: {sum(1 for l in logs if isinstance(l,dict) and l.get('sleep'))}\n"
        )
        msg = await client.messages.create(
            model=MODEL,
            max_tokens=700,
            system=ADAPT_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        return _extract_json(msg.content[0].text)
    except ValueError:
        return {"error": "Не удалось разобрать ответ адаптации"}
    except Exception as e:
        logger.exception("generate_weekly_adaptation failed: %s", e)
        return {"error": "Ошибка анализа прогресса"}


# ──────────────────────────────────────────────
#  Fallbacks (no API)
# ──────────────────────────────────────────────
def _fallback_nutrition(profile: dict, macros: dict) -> str:
    cal = macros["calories"]
    pro = macros["protein_g"]
    fat = macros["fat_g"]
    carb = macros["carb_g"]
    schedule = profile.get("schedule", "standard")
    if schedule == "16h+":
        return (
            f"🍽 ПЛАН ПИТАНИЯ — Режим 16ч+\n📊 {cal} ккал | Б:{pro}г Ж:{fat}г У:{carb}г\n\n"
            "🌅 До смены (07:00):\n• Протеиновый коктейль на молоке — 600 мл\n• Банан — 1 шт\n\n"
            "⏰ На смене:\n• Творог 5% — 200г\n• Протеиновый батончик — 1 шт\n\n"
            "🌙 После смены:\n• Куриная грудка — 250г\n• Гречка — 200г\n• Овощной салат\n\n"
            "⚠️ Проконсультируйся с врачом перед началом программы."
        )
    return (
        f"🍽 ПЛАН ПИТАНИЯ\n📊 {cal} ккал | Б:{pro}г Ж:{fat}г У:{carb}г\n\n"
        "🌅 Завтрак (07:30): Овсянка 80г + 3 яйца\n"
        "🕙 Перекус (10:30): Творог 5% 150г + орехи 25г\n"
        "🕐 Обед (13:00): Куриная грудка 200г + гречка 200г + овощи\n"
        "🕔 Перекус (16:00): Яблоко + кефир 200 мл\n"
        "🌙 Ужин (19:00): Рыба/говядина 200г + овощи на пару\n\n"
        "⚠️ Проконсультируйся с врачом перед началом программы."
    )


def _fallback_workout(profile: dict) -> str:
    equipment = profile.get("equipment", ["none"])
    health = profile.get("health_issues", [])
    warnings = []
    if "back_problems" in health:
        warnings.append("⚠️ ИСКЛЮЧЕНО (спина): становая, приседания со штангой, гиперэкстензия")
    if "knee_issues" in health:
        warnings.append("⚠️ ИСКЛЮЧЕНО (колени): приседания с весом, выпады, прыжки")
    if "hypertension" in health:
        warnings.append("⚠️ ИСКЛЮЧЕНО (гипертония): жим над головой, натуживание")
    wb = ("\n".join(warnings) + "\n\n") if warnings else ""
    if "gym" in equipment:
        return (
            f"🏋️ ПЛАН — Спортзал\n\n{wb}"
            "День A (Грудь+Трицепс): жим лёжа 4×8, жим гантелей 3×10, французский жим 3×12\n"
            "День B (Спина+Бицепс): подтягивания 4×8, тяга гантели 3×10, сгибания 3×12\n"
            "День C (Ноги+Плечи): жим ногами 4×10, разгибания 3×12, жим гантелей сидя 3×10\n\n"
            "⚠️ Проконсультируйся с врачом перед началом программы."
        )
    return (
        f"🏋️ ПЛАН — Дома\n\n{wb}"
        "День A (Верх): отжимания 4×12, планка 3×45с, обратные отжимания 3×12\n"
        "День B (Низ): приседания 4×15, ягодичный мостик 4×15, выпады 3×12\n"
        "День C (Кардио): берпи 4×8, прыжки 3×20, скалолаз 3×20\n\n"
        "⚠️ Проконсультируйся с врачом перед началом программы."
    )
