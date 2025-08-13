# DailyDevDigestAi

AI-агент, автоматизирующий ежедневную публикацию статей (тема → генерация → фактчекинг → обложка → публикация → аналитика → CTA).

## Структура

- `src/main.py` — CLI и оркестрация пайплайна
- `src/topics_selector.py` — выбор темы (мок + антидубль за 20 дней)
- `src/article_generator.py` — генерация статьи (мок + опционально OpenAI)
- `src/fact_checker.py` — базовый фактчекинг (валидация python-кода)
- `src/cover_generator.py` — генерация обложки (мок + опционально DALL·E, 1200×630)
- `src/publisher.py` — публикация в Ghost (реально при наличии ключей, иначе dry-run)
- `src/analytics_reporter.py` — отчётность (мок)
- `src/cta_inserter.py` — вставка CTA (ротация из `data/ctas.json`)
- `src/config.py` — конфиг (env + пути)
- `src/state.py` — хранилище последних тем (`data/state.json`)

## Запуск

```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python -m src.main run-once
```

Мок-режим (по умолчанию): без ключей выполняется сбор тем, генерация текста и обложки в режиме заглушек, публикация — dry-run.

Чтобы включить реальные сервисы, задайте переменные окружения.
Скопируйте `env.example` в `.env` и заполните значения — файл подхватится автоматически, либо экспортируйте переменные вручную.

```bash
# OpenAI
set OPENAI_API_KEY=sk-...
set OPENAI_MODEL=gpt-4o-mini
set OPENAI_IMAGE_MODEL=gpt-image-1

# Ghost Admin API
set GHOST_ADMIN_API_URL=https://your-blog.com
set GHOST_ADMIN_API_KEY=<admin_id>:<secret_hex>

# Google Custom Search (опционально)
set GOOGLE_API_KEY=...
set GOOGLE_CSE_ID=...

# Google Trends регион (для pytrends)
set GOOGLE_TRENDS_GEO=RU
```

После задания ключей — повторный запуск `python -m src.main run-once` выполнит реальные вызовы.

### Планировщик (Windows Task Scheduler)

Запланируйте ежедневный запуск пайплайна и еженедельный отчёт:

```bat
schtasks /Create /TN "DDD_Daily" /TR "%CD%\.venv\Scripts\python.exe -m src.main daily" /SC DAILY /ST 07:00
schtasks /Create /TN "DDD_Weekly" /TR "%CD%\.venv\Scripts\python.exe -m src.main weekly" /SC WEEKLY /D SUN /ST 19:00
```

Убедитесь, что локальная TZ — Europe/Moscow, либо скорректируйте время под вашу TZ.

## Переменные окружения

- `OPENAI_API_KEY` — для генерации текста/обложек (опционально)
- `OPENAI_MODEL` (по умолчанию `gpt-4o-mini`)
- `OPENAI_IMAGE_MODEL` (по умолчанию `gpt-image-1`)
- `GHOST_ADMIN_API_URL`, `GHOST_ADMIN_API_KEY` — публикация (если уберём dry-run)
- `APP_TIMEZONE` (не используется в расчёте времени публикации; сейчас фиксировано `Europe/Moscow`)
- `DATA_DIR`, `STATE_FILE`, `CTAS_FILE` — пути к данным

## CTA

Файл `data/ctas.json` (опционален):

```json
[
  {"type": "free", "title": "Бесплатный мастер‑класс по AI", "url": "https://example.com/free-ai"},
  {"type": "course", "title": "Флагманский курс Python", "url": "https://example.com/course"}
]
```

## Дальнейшие шаги

1. Интеграция источников тем (добавить TG/RSS‑прокси, Яндекс Вордстат; выровнять окно 48ч для всех)
2. Довести генерацию: контроль длины через модель, чек‑лист качества
3. Публикация в Ghost: доп. теги/метки, обработка ошибок/ретраи
4. Планировщик (cron/Windows Task Scheduler/Docker + cron)
5. Интеграции аналитики (Ghost API, GA4, Я.Метрика, to.click) и отправка email с PDF
6. Более умный фактчекинг (внешние песочницы, web‑поиск)
