# P.A.R.K.E.R. — Personal Adaptive Resource & Kinetic Energy Regulator

## Суть проекта
Telegram-бот + Mini App (TWA): персональный AI-нутрициолог и тренер.
Адаптируется под реальный график, здоровье и цели. Цифровой двойник эксперта.
MVP — закрытый (3 пользователя). Далее — открытый доступ + масштабирование.

---

## Архитектура системы

```
Telegram ──► Bot (aiogram webhook)
                    │
                    ▼
             FastAPI Server  ◄──── Telegram Mini App (HTML/JS)
                    │                        │
                    ▼                        ▼
             Claude API              POST /api/profile
                    │
                    ▼
              Supabase DB (PostgreSQL)
```

**Один сервис на Railway** обслуживает:
- Telegram webhook (`POST /webhook/{token}`)
- Mini App frontend (`GET /` → index.html)
- REST API (`POST /api/profile`, `/api/checkin`, etc.)

---

## Стек

| Слой | Технология | Версия |
|---|---|---|
| Runtime | Python | 3.12 |
| Web-сервер | FastAPI + Uvicorn | 0.115 / 0.32 |
| Telegram Bot | aiogram | 3.13 |
| AI | Anthropic Claude API | claude-sonnet-4-6 |
| База данных | Supabase (PostgreSQL) | — |
| Frontend | HTML / CSS / JS (Telegram WebApp SDK) | — |
| Хостинг | Railway (Nixpacks) | — |
| CI/CD | GitHub → Railway (webhook автодеплой) | — |

---

## Структура репозитория

```
PARKER/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── profile.py      # POST /api/profile — КБЖУ + план
│   │   ├── checkin.py      # POST /api/checkin — ежедневный отчёт
│   │   └── webhook.py      # POST /webhook/{token}
│   └── static/
│       └── index.html      # Telegram Mini App (форма онбординга)
├── bot/
│   ├── handlers/
│   │   └── start.py        # /start → WebApp button
│   ├── services/
│   │   ├── ai_service.py   # Claude API + fallback шаблоны
│   │   └── nutrition.py    # build_profile_summary, compute_macros
│   └── utils/
│       └── calculators.py  # BMR, TDEE, макросы
├── db/
│   ├── client.py           # Supabase клиент
│   └── queries.py          # upsert_user, save_plan, get_user
├── main.py                 # FastAPI app + lifespan (webhook setup)
├── requirements.txt
├── railway.toml
├── runtime.txt
├── .env.example
├── CLAUDE.md
└── PROJECT_IDEA.md
```

---

## Переменные окружения

```
BOT_TOKEN=               # Telegram @BotFather
ANTHROPIC_API_KEY=       # console.anthropic.com
WEBAPP_URL=              # https://xxx.up.railway.app  (Railway domain)
SUPABASE_URL=            # Supabase project URL
SUPABASE_SERVICE_KEY=    # Supabase service_role key (не anon!)
```

---

## CI/CD Pipeline

```
git push origin main
       │
       ▼
   GitHub repo
       │  (webhook)
       ▼
   Railway build (Nixpacks, Python 3.12)
       │
       ▼
   uvicorn main:app --host 0.0.0.0 --port $PORT
       │
       ▼
   FastAPI startup → set_webhook(WEBAPP_URL/webhook/BOT_TOKEN)
```

---

## Ключевые API-эндпоинты

| Метод | Путь | Описание |
|---|---|---|
| GET | `/` | Отдаёт Mini App (index.html) |
| GET | `/health` | Health check для Railway |
| POST | `/webhook/{token}` | Telegram updates → aiogram |
| POST | `/api/profile` | Принимает анкету → КБЖУ → Claude → Supabase |
| POST | `/api/checkin` | Ежедневный чек-ап (этап 3) |

---

## Поток данных (основной сценарий)

```
1. Пользователь пишет /start в боте
2. Бот отвечает кнопкой «Открыть анкету» (WebApp button)
3. Telegram открывает Mini App (index.html с Railway)
4. Пользователь заполняет 9-шаговую форму в браузере
5. Mini App POST /api/profile { goal, gender, age, ... }
6. FastAPI → calculate_macros() → generate_meal_plan() (Claude)
7. FastAPI → upsert_user() + save_plan() в Supabase
8. FastAPI возвращает { macros, plan }
9. Mini App показывает результат прямо в Telegram
```

---

## База данных — Supabase

### users
```sql
id uuid PK | tg_id bigint UNIQUE | goal text | gender text
age int | height_cm int | weight_kg numeric | body_fat_pct numeric
waist_cm numeric | hips_cm numeric | schedule text
health_issues text[] | equipment text[] | food_blacklist text[]
sleep_avg numeric | created_at timestamptz | updated_at timestamptz
```

### plans
```sql
id uuid PK | user_id uuid FK | type text | content text
macros jsonb | created_at timestamptz
```

### daily_logs
```sql
id uuid PK | user_id uuid FK | log_date date
weight_kg numeric | sleep_hours numeric | stress_level int
water_ml int | notes text | created_at timestamptz
```

---

## Бизнес-правила (алгоритм)

| Условие | Действие |
|---|---|
| body_fat_pct задан | BMR = Кетч-МакАрдл |
| body_fat_pct не задан | BMR = Миффлин-Сан Жеор |
| schedule = 16h+ | Режим «Минимальный план» |
| health = back_problems | Запрет: становая, приседания со штангой, гиперэкстензия |
| health = knee_issues | Запрет: глубокие приседания, выпады с весом, тумба |
| health = hypertension | Запрет: жим над головой, натуживание |
| Любой план | Медицинский дисклеймер обязателен |

---

## Запуск локально

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить токены
python main.py         # uvicorn + bot polling (dev режим)
```

---

## Репозиторий
`https://github.com/PsparkerM/PARKER.git`
Ветка `main` → автодеплой Railway.
