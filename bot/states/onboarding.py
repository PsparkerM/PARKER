from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    goal = State()
    gender = State()
    age = State()
    height = State()
    weight = State()
    body_fat = State()
    body_fat_value = State()
    schedule = State()
    health_issues = State()
    equipment = State()
    confirmation = State()
