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
│   │   ├── adapt.py        # POST /api/adapt — еженедельная адаптация плана
│   │   ├── admin.py        # GET /admin — HTML-панель управления
│   │   ├── chat.py         # POST /api/chat — чат с Арни
│   │   ├── deps.py         # Зависимости FastAPI (auth, AI-квота)
│   │   ├── food.py         # POST /api/food, /api/food/photo — КБЖУ по тексту/фото
│   │   ├── logs.py         # GET/POST /api/logs — трекер веса/еды/замеров
│   │   ├── notify.py       # POST /api/notify — отправка сообщений пользователям
│   │   ├── profile.py      # POST /api/profile — онбординг, КБЖУ + планы
│   │   ├── reminders.py    # GET/POST/DELETE /api/reminders — напоминания
│   │   └── user.py         # GET /api/user, POST /api/user/update, /api/chat/history
│   ├── middleware/
│   │   ├── access_log.py   # Логирование + аномалии (TRAFFIC_SPIKE, SUSPICIOUS_IP)
│   │   ├── rate_limit.py   # SlidingWindowLimiter (in-memory, per-IP и per-user)
│   │   └── security_headers.py  # CSP, HSTS, X-Frame-Options
│   └── static/
│       └── index.html      # Telegram Mini App (SPA)
├── bot/
│   ├── handlers/
│   │   └── start.py        # /start, /plan, /progress, /restart, /dm
│   ├── services/
│   │   └── ai_service.py   # Claude API — чат, планы, КБЖУ, адаптация + fallback
│   └── utils/
│       ├── calculators.py  # BMR (Кетч-МакАрдл / Миффлин), TDEE, макросы
│       └── telegram_auth.py # HMAC-верификация Telegram initData
├── bot/
│   ├── bot_instance.py     # Singleton aiogram Bot
│   ├── config.py           # Env-переменные
│   └── scheduler.py        # APScheduler — напоминания (вода/еда/замеры)
├── db/
│   ├── client.py           # Supabase singleton-клиент
│   ├── migrations/         # SQL-миграции (002–005)
│   └── queries.py          # Все DB-операции (sync, вызывать через asyncio.to_thread)
├── main.py                 # FastAPI app + lifespan (webhook, scheduler)
├── requirements.txt
├── railway.toml
├── runtime.txt             # python-3.12.0
├── .env.example
├── .gitignore
└── CLAUDE.md
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
