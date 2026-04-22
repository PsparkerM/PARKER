from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData


class OnboardingCallback(CallbackData, prefix="ob"):
    step: str
    value: str


class MultiSelectCallback(CallbackData, prefix="ms"):
    group: str   # "health" | "equip"
    action: str  # "toggle" | "done"
    item: str = ""


HEALTH_OPTIONS = {
    "none":          "Нет проблем",
    "back_problems": "Проблемы со спиной / сколиоз",
    "knee_issues":   "Проблемы с коленями",
    "hypertension":  "Гипертония",
}

EQUIPMENT_OPTIONS = {
    "none":      "Без оборудования",
    "dumbbells": "Гантели",
    "barbell":   "Штанга / гриф",
    "gym":       "Спортзал (всё оборудование)",
    "pool":      "Бассейн",
}


def goal_kb() -> InlineKeyboardMarkup:
    cb = OnboardingCallback
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Похудеть",          callback_data=cb(step="goal", value="lose_weight").pack())],
        [InlineKeyboardButton(text="💪 Набрать массу",     callback_data=cb(step="goal", value="gain_muscle").pack())],
        [InlineKeyboardButton(text="⚖️ Поддержать форму", callback_data=cb(step="goal", value="maintain").pack())],
        [InlineKeyboardButton(text="🔄 Рекомпозиция",      callback_data=cb(step="goal", value="recomposition").pack())],
    ])


def gender_kb() -> InlineKeyboardMarkup:
    cb = OnboardingCallback
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👨 Мужской", callback_data=cb(step="gender", value="male").pack()),
        InlineKeyboardButton(text="👩 Женский", callback_data=cb(step="gender", value="female").pack()),
    ]])


def body_fat_kb() -> InlineKeyboardMarkup:
    cb = OnboardingCallback
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Знаю % жира",  callback_data=cb(step="body_fat", value="know").pack())],
        [InlineKeyboardButton(text="⏭ Пропустить",   callback_data=cb(step="body_fat", value="skip").pack())],
    ])


def schedule_kb() -> InlineKeyboardMarkup:
    cb = OnboardingCallback
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕗 Стандартный (8ч)",    callback_data=cb(step="schedule", value="standard").pack())],
        [InlineKeyboardButton(text="⚡ Интенсивный (12ч)",   callback_data=cb(step="schedule", value="12h").pack())],
        [InlineKeyboardButton(text="🔴 Тяжёлый (16ч+)",      callback_data=cb(step="schedule", value="16h+").pack())],
        [InlineKeyboardButton(text="🔄 Сменный график",      callback_data=cb(step="schedule", value="shift").pack())],
    ])


def health_issues_kb(selected) -> InlineKeyboardMarkup:
    rows = []
    for key, label in HEALTH_OPTIONS.items():
        mark = "✅ " if key in selected else "◻️ "
        rows.append([InlineKeyboardButton(
            text=mark + label,
            callback_data=MultiSelectCallback(group="health", action="toggle", item=key).pack(),
        )])
    rows.append([InlineKeyboardButton(
        text="➡️ Готово",
        callback_data=MultiSelectCallback(group="health", action="done").pack(),
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def equipment_kb(selected) -> InlineKeyboardMarkup:
    rows = []
    for key, label in EQUIPMENT_OPTIONS.items():
        mark = "✅ " if key in selected else "◻️ "
        rows.append([InlineKeyboardButton(
            text=mark + label,
            callback_data=MultiSelectCallback(group="equip", action="toggle", item=key).pack(),
        )])
    rows.append([InlineKeyboardButton(
        text="➡️ Готово",
        callback_data=MultiSelectCallback(group="equip", action="done").pack(),
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirmation_kb() -> InlineKeyboardMarkup:
    cb = OnboardingCallback
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Всё верно, поехали!", callback_data=cb(step="confirm", value="yes").pack())],
        [InlineKeyboardButton(text="🔄 Начать заново",       callback_data=cb(step="confirm", value="restart").pack())],
    ])
