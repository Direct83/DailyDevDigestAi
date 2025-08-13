# DailyDevDigestAi

AI-агент, автоматизирующий ежедневную публикацию статей (тема → генерация → фактчекинг → обложка → публикация → аналитика → CTA).

## Структура

- `src/main.py` — CLI и оркестрация пайплайна
- `src/topics_selector.py` — выбор темы (HN + Reddit + Google Trends + GitHub Trending; антидубль через Ghost за 20 дней)
- `src/article_generator.py` — генерация статьи (OpenAI при ключе; контроль длины 4000–8000 символов)
- `src/fact_checker.py` — фактчекинг (синтаксис Python, песочница Piston API для коротких сниппетов, Google CSE)
- `src/cover_generator.py` — обложка 1200×630 (OpenAI Images при ключе), рендер в памяти
- `src/publisher.py` — публикация в Ghost (теги + “AI Generated”, отложено на 11:00 МСК)
- `src/analytics_reporter.py` — еженедельный PDF-отчёт (Ghost + опц. GA4 и CTR из to.click)
- `src/cta_inserter.py` — вставка CTA (источник: `CTAS_JSON` или to.click API; приоритизация свежих)
- `src/config.py` — конфиг (env)
- `src/state.py` — антидубль тем (через Ghost)

## Запуск

```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m src.main run-once
```

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

# GA4 (опционально)
set GA4_PROPERTY_ID=...
set GA4_JSON_KEY_PATH=path\to\service-account.json

# to.click (опционально)
set TOCLICK_API_KEY=...
set TOCLICK_BASE_URL=https://to.click/api

# CTA (JSON строка)
set CTAS_JSON=[{"type":"free","title":"Бесплатный мастер-класс","url":"https://example.com/free","priority":1,"fresh":true},{"type":"course","title":"Курс Python","url":"https://example.com/course","priority":2}]

# SMTP для отчётов
set SMTP_HOST=smtp.example.com
set SMTP_PORT=587
set SMTP_USER=...
set SMTP_PASSWORD=...
set REPORT_EMAIL_TO=director@example.com

# Прочее
set APP_TIMEZONE=Europe/Moscow
```

После задания ключей — `python -m src.main run-once` выполнит реальные вызовы.

### Планировщик (Windows Task Scheduler)

Запланируйте ежедневный запуск пайплайна и еженедельный отчёт:

```bat
schtasks /Create /TN "DDD_Daily" /TR "%CD%\.venv\Scripts\python.exe -m src.main daily" /SC DAILY /ST 07:00
schtasks /Create /TN "DDD_Weekly" /TR "%CD%\.venv\Scripts\python.exe -m src.main weekly" /SC WEEKLY /D SUN /ST 19:00
```

Убедитесь, что локальная TZ — Europe/Moscow, либо скорректируйте время под вашу TZ.

## Примечания
- Фактчекинг запускает только короткие безопасные Python-сниппеты (через Piston API); потенциально опасные блокируются.
- При отсутствии ключей сервисов соответствующие части переходят в упрощённый режим.

## Компонентная архитектура

- Модули приложения:
  - Блок выбора тем: `src/topics_selector.py`
  - Блок генерации: `src/article_generator.py`
  - Блок фактчекинга: `src/fact_checker.py`
  - Блок обложки: `src/cover_generator.py`
  - Публикация: `src/publisher.py`
  - Аналитика/отчёт: `src/analytics_reporter.py`
  - Рекламные вставки: `src/cta_inserter.py`
  - Конфигурация/состояние: `src/config.py`, `src/state.py`

- Внешние сервисы и взаимодействия:
  - OpenAI (Chat, Images) — генерация текста и обложки
  - Ghost Admin API — проверка дублей, загрузка обложки, создание/планирование постов
  - Google Custom Search API — проверка фактов (наличие результатов)
  - Piston API — запуск коротких Python‑сниппетов для валидации кода
  - Google Analytics 4 (опц.) — просмотры страниц за 7 дней
  - to.click (опц.) — сводный CTR и список CTA
  - SMTP — отправка еженедельного PDF‑отчёта

- Потоки данных:
  - Триггеры: планировщик ОС вызывает `src/main.py` (`run-once` в 07:00, `weekly` в 19:00 вс)
  - Входные данные: публичные фиды (HN/Reddit/Trends/GitHub), переменные окружения `.env`
  - Процесс: тема → текст → проверка → обложка → пост (Ghost)
  - Отчёт: сбор данных (Ghost/GA4/to.click) → PDF → email

- Хранилища и состояние:
  - Локальное состояние не используется
  - Истина о публикациях — в Ghost (антидубль по заголовку через Ghost Admin API)
  - Конфигурация — через переменные окружения, без коммита ключей в репозиторий

- Безопасность и ошибки:
  - Ключи — только в `.env`/секрет‑хранилищах, в гите игнорируются
  - Фактчекинг кода запускает только короткие и безопасные сниппеты (блокировка опасных импортов)
  - Сетевые вызовы обёрнуты в try/except; для OpenAI предусмотрены повторные попытки/фоллбек

## Технологический стек

- **Язык и CLI**: Python 3.x, Typer
- **Сетевые вызовы и парсинг**: requests, BeautifulSoup4, feedparser
- **Источники тем**: Hacker News (REST), Reddit (RSS/JSON), Google Trends (pytrends), GitHub Trending (HTML‑парсинг)
- **Генерация контента и обложек**: OpenAI Python SDK (Chat Completions, Images), Pillow
- **Фактчекинг**: AST‑проверка Python, Piston API (песочница сниппетов), Google Custom Search API
- **Публикация**: Ghost Admin API, PyJWT (JWT для Ghost)
- **Аналитика**: Google Analytics 4 (google-analytics-data), Ghost Admin API (метаданные постов), to.click (CTR)
- **Отчёты**: reportlab (PDF), SMTP (отправка email)
- **Конфигурация и время**: python-dotenv, pytz/tzdata
- **Утилиты**: python-slugify
- **Планирование**: планировщик ОС (Windows Task Scheduler/cron)
