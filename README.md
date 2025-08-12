# DailyDevDigestAi

AI-агент, автоматизирующий ежедневную публикацию статей (тема → генерация → фактчекинг → обложка → публикация → аналитика → CTA).

## Структура

- `src/main.py` — CLI и оркестрация пайплайна
- `src/topics_selector.py` — выбор темы (мок + антидубль за 20 дней)
- `src/article_generator.py` — генерация статьи (мок + подготовка к OpenAI)
- `src/fact_checker.py` — базовый фактчекинг (валидация python-кода)
- `src/cover_generator.py` — заготовка генерации обложки
- `src/publisher.py` — публикация в Ghost (dry-run)
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

## Переменные окружения

- `OPENAI_API_KEY` — для генерации текста/обложек (опционально)
- `OPENAI_MODEL` (по умолчанию `gpt-4o-mini`)
- `OPENAI_IMAGE_MODEL` (по умолчанию `gpt-image-1`)
- `GHOST_ADMIN_API_URL`, `GHOST_ADMIN_API_KEY` — публикация (если уберём dry-run)
- `APP_TIMEZONE` (по умолчанию `Europe/Moscow`)
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

1. Интеграция источников тем (Google Trends, HN, GitHub Trending, Reddit, RSS/TG, Wordstat)
2. Реальные вызовы OpenAI: текст + изображения
3. Реальная публикация в Ghost Admin API (отложенные публикации)
4. Планировщик (cron/Windows Task Scheduler/Docker + cron)
5. Интеграции аналитики (Ghost API, GA4, Я.Метрика, to.click) и отправка email с PDF
6. Более умный фактчекинг (внешние песочницы, web‑поиск)
