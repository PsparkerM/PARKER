# P.A.R.K.E.R. — Personal Adaptive Resource & Kinetic Energy Regulator

## Суть проекта
Telegram-бот, затем Mini App — адаптивный AI-нутрициолог и тренер.
Соединяет питание + тренировки + реальный график жизни + состояние здоровья.

## Стек
- **Runtime:** Python 3.12
- **Telegram:** aiogram 3.x (async)
- **AI:** Anthropic Claude API (claude-sonnet-4-6 / claude-opus-4-7)
- **БД:** Supabase (PostgreSQL + Auth + Realtime)
- **Сервер:** Railway (автодеплой из GitHub main)
- **CI/CD:** GitHub → Railway webhook
- **Кеширование:** Redis (Railway plugin) для сессий/состояний FSM

## Структура репозитория
```
P.A.R.K.E.R./
├── bot/
│   ├── handlers/       # роутеры aiogram
│   ├── keyboards/      # inline & reply клавиатуры
│   ├── states/         # FSM-состояния
│   ├── services/       # бизнес-логика (nutrition, workout, ai)
│   ├── db/             # Supabase-клиент, модели
│   └── utils/          # калькуляторы КБЖУ, форматтеры
├── tests/
├── .env.example
├── main.py
├── requirements.txt
└── railway.toml
```

## Переменные окружения (.env)
```
BOT_TOKEN=
ANTHROPIC_API_KEY=
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
REDIS_URL=
```

## Запуск локально
```bash
pip install -r requirements.txt
cp .env.example .env   # заполнить
python main.py
```

## Текущий этап разработки
**Этап 1 — MVP-Бот:**
- Онбординг-анкета (цель, здоровье, график, параметры)
- Калькулятор КБЖУ (формула Кетч-МакАрдл для нестандартных параметров)
- Генерация текстовых планов питания через Claude API
- Профиль пользователя в Supabase

## Целевые пользователи (MVP, 4 человека)
- Пётр: рост 205 см, 19ч смены — жидкие калории, точный КБЖУ
- Вика: сколиоз — запрет осевых нагрузок, ЛФК-блоки
- Лера: 12ч на ногах — антиотёчный протокол, эстетика
- (4-й пользователь — уточнить)

## Ключевые бизнес-правила
- При сколиозе/проблемах со спиной — ЗАПРЕТ становой тяги и приседаний со штангой
- При смене 16ч+ — режим «Минимальный план» (5 мин растяжки + витамины)
- Расчёт КБЖУ: Кетч-МакАрдл при наличии % жира, иначе Миффлин-Сан Жеор
- Обязательный медицинский дисклеймер при регистрации

## Репозиторий GitHub
`https://github.com/PsparkerM/P.A.R.K.E.R..git`
Ветка `main` → автодеплой на Railway.

## Roadmap
1. MVP-Бот (сейчас)
2. Тренировочный движок (Дом/Зал/Бассейн/ЛФК)
3. Ежедневные отчёты + аналитика прогресса
4. Telegram Mini App (TWA)
5. Масштабирование: соцсеть, Apple Health / Google Fit
