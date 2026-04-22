# PROJECT_IDEA.md — P.A.R.K.E.R.
> Personal Adaptive Resource & Kinetic Energy Regulator  
> ™ P.A.R.K.E.R.

---

## 1. Проблема

Стандартные планы питания и тренировок не адаптируются к реальной жизни:

| Проблема | Пример |
|---|---|
| Конфликт графика и режима | 5 приёмов пищи невозможны при 19ч смене |
| Игнорирование здоровья | Приседания со штангой при сколиозе |
| Отсутствие гибкости | «Штраф» за пропущенную тренировку → демотивация |
| Метаболический хаос | Стандартный калькулятор ошибается на 500–1000 ккал для Петра (205 см) |

---

## 2. Решение: принцип «Биологического Аудита»

Бот не просто выдаёт план — он ежедневно адаптируется под «вводные данные дня»:

- **Адаптивное питание** — жидкие калории и 2-минутные перекусы для занятых
- **Корректирующие тренировки** — ЛФК при сколиозе, плавание при усталости ног
- **Управление восстановлением** — если Лера отработала 12ч на ногах, силовая → растяжка
- **Обратная связь по 3 осям:** что съел / как спал / уровень стресса

---

## 3. Целевая аудитория

### MVP (4 человека — закрытый тест)
| Персона | Специфика | Главный запрос |
|---|---|---|
| Пётр | Рост 205 см, смены 19ч | Точный КБЖУ, питание «на ходу» |
| Вика | Сколиоз | Безопасные упражнения, ЛФК-блоки |
| Лера | 12ч на ногах, эстетика | Контроль КБЖУ, антиотёк, рельеф |
| (4-й) | TBD | TBD |

### Публичный запуск (Этап 5+)
- **High-Load Профессионалы**: HoReCa, медицина, логистика (12ч+ графики)
- **Специфические Атлеты**: нестандартные параметры, особенности здоровья
- **Результатники-эстеты**: цель — «тело-идеал», жёсткий КБЖУ + микропериодизация

---

## 4. Конкуренты и наш козырь

| Продукт | Сильные стороны | Слабые стороны |
|---|---|---|
| MyFitnessPal / FatSecret | Большая база продуктов | Нет персонализации под график |
| Nike Training / Fitbod | Хорошие упражнения | Нет понимания диеты и сна |
| **P.A.R.K.E.R.** | **Еда + Тренировки + График + Здоровье** | MVP пока текстовый |

---

## 5. Техническая спецификация

### 5.1 Архитектура системы

```
[Telegram User]
      ↓
[aiogram 3.x Bot — Railway]
      ↓
[FSM (Redis)] — хранение шага онбординга/диалога
      ↓
[Services Layer]
   ├── NutritionService  — расчёт КБЖУ, план питания
   ├── WorkoutService    — подбор упражнений, запреты
   ├── AIService         — Claude API (генерация планов, диалог)
   └── AnalyticsService  — прогресс, отчёты (Этап 3)
      ↓
[Supabase PostgreSQL]
```

### 5.2 Стек технологий

| Слой | Технология | Обоснование |
|---|---|---|
| Язык | Python 3.12 | Лучшая экосистема для Telegram-ботов и AI |
| Telegram | aiogram 3.x | Async, FSM из коробки, активная поддержка |
| AI | Anthropic Claude API | Лучшее понимание контекста, prompt caching |
| БД | Supabase (PostgreSQL) | Бесплатный tier, REST + Realtime, Auth |
| Сессии/FSM | Redis (Railway plugin) | In-memory хранение состояний пользователей |
| Сервер | Railway | Автодеплой из GitHub, простой scale-up |
| CI/CD | GitHub → Railway webhook | Push в main = деплой |

### 5.3 База данных — схема таблиц

```sql
-- Пользователи
users (
  id UUID PRIMARY KEY,
  telegram_id BIGINT UNIQUE NOT NULL,
  username TEXT,
  created_at TIMESTAMPTZ
)

-- Профили (онбординг)
profiles (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users,
  goal TEXT,            -- lose_weight | gain_muscle | maintain | recomposition
  gender TEXT,
  age INT,
  height_cm INT,
  weight_kg NUMERIC,
  body_fat_pct NUMERIC, -- для формулы Кетч-МакАрдл
  activity_level TEXT,  -- sedentary | lightly | moderate | very | extra
  work_schedule TEXT,   -- стандартный | 12h | 16h+ | сменный
  health_issues TEXT[], -- back_problems | knee_issues | hypertension | ...
  equipment TEXT[],     -- none | dumbbells | barbell | gym | pool
  updated_at TIMESTAMPTZ
)

-- Ежедневные отчёты (Этап 3)
daily_logs (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users,
  date DATE,
  weight_kg NUMERIC,
  sleep_hours NUMERIC,
  stress_level INT,     -- 1-10
  notes TEXT,
  created_at TIMESTAMPTZ
)

-- Планы питания (кеш сгенерированных планов)
nutrition_plans (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users,
  calories INT,
  protein_g INT,
  fat_g INT,
  carbs_g INT,
  plan_text TEXT,
  generated_at TIMESTAMPTZ
)
```

### 5.4 FSM — состояния онбординга

```
START → GOAL → GENDER → AGE → HEIGHT → WEIGHT →
BODY_FAT (опц.) → SCHEDULE → HEALTH_ISSUES →
EQUIPMENT → CONFIRMATION → PROFILE_COMPLETE
```

### 5.5 Расчёт КБЖУ

- **С % жира:** Кетч-МакАрдл  
  `BMR = 370 + (21.6 × LBM)`  где `LBM = weight × (1 - fat%)`
- **Без % жира:** Миффлин-Сан Жеор  
  `BMR = (10 × w) + (6.25 × h) - (5 × age) ± 5`
- Коэффициент активности умножается с учётом рабочего графика, не только спорта

### 5.6 Алгоритм запретов упражнений

```python
FORBIDDEN_EXERCISES = {
    "back_problems": ["deadlift", "barbell_squat", "good_morning", "leg_press"],
    "knee_issues": ["deep_squat", "lunges_weighted", "box_jump"],
    "hypertension": ["heavy_overhead_press", "valsalva_exercises"],
}
```

### 5.7 Режимы тренировок

- **Дом** — без оборудования или с гантелями
- **Зал** — полный инвентарь, гриф, тренажёры
- **Бассейн** — плавание, акваэробика (восстановление при усталости ног)
- **ЛФК** — при сколиозе и проблемах с опорно-двигательным аппаратом
- **Минимальный план** — 5 мин при 16ч+ смене

---

## 6. Roadmap

| Этап | Что делаем | Статус |
|---|---|---|
| 1. MVP-Бот | Анкета, КБЖУ-калькулятор, текстовые планы питания | 🔧 В разработке |
| 2. Тренировочный движок | База упражнений, Дом/Зал/Бассейн/ЛФК | ⏳ Следующий |
| 3. Аналитика | Ежедневные отчёты, графики прогресса | ⏳ |
| 4. Mini App (TWA) | Визуальный интерфейс, видео, платежи | ⏳ |
| 5. Масштабирование | Соцсеть внутри, Apple Health / Google Fit | ⏳ |

---

## 7. Риски и митигация

| Риск | Митигация |
|---|---|
| Медицинский (травма при сколиозе) | Дисклеймер + алгоритмический запрет опасных упражнений |
| Потеря мотивации (Пётр устал) | Режим «Минимальный план» при 16ч+ смене |
| Ошибка распознавания продуктов | MVP: шаблонные меню; Этап 2: FatSecret API |
| Неточный КБЖУ для экстремальных параметров | Кетч-МакАрдл при указании % жира |
| Дрейф AI-ответов | System prompt с жёсткими ограничениями + финальная верификация расчётов кодом |

---

## 8. Инфраструктура

- **GitHub repo:** основная ветка `main` → триггер деплоя на Railway
- **Railway:** один сервис (бот) + Redis plugin
- **Supabase:** PostgreSQL БД + Row Level Security по `telegram_id`
- **Мониторинг:** Railway логи + Telegram-уведомление при падении бота (healthcheck)

---

*Документ актуален на 2026-04-22. Обновляется по мере прохождения этапов.*
