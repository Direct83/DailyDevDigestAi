# DailyDevDigestAi

AI-агент, автоматизирующий ежедневную публикацию статей (тема → генерация → фактчекинг → обложка → публикация → аналитика → CTA).

## Быстрый старт

1) Установка зависимостей (Git Bash на Windows)
```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

2) Настройка окружения
```bash
cp env.example .env
```
Минимум для продакшена заполните в `.env`:
- OPENAI_API_KEY — генерация текста/обложек (можно без него, будет fallback)
- GHOST_ADMIN_API_URL и GHOST_ADMIN_API_KEY — публикация в Ghost
- GOOGLE_API_KEY и GOOGLE_CSE_ID — фактчекинг (поиск)
- SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, REPORT_EMAIL_TO — еженедельный отчёт
Опционально: GA4_PROPERTY_ID, GA4_JSON_KEY_PATH, TOCLICK_API_KEY, CTAS_JSON, TELEGRAM_RSS_FEEDS, YANDEX_SUGGEST_SEEDS.

3) Первый запуск
```bash
./.venv/Scripts/python.exe -m src.main run-once
```
Если ключей нет, пройдёт упрощённый сценарий (без реальной публикации и части проверок).

4) (Опционально) Линтер/форматтер для разработки
```bash
./.venv/Scripts/python.exe -m pip install ruff pre-commit
pre-commit install
# ручной запуск
./.venv/Scripts/python.exe -m ruff check . --fix
./.venv/Scripts/python.exe -m ruff format .
```

## Запуск и расписание

- Разовая публикация (для проверки):
  - `./.venv/Scripts/python.exe -m src.main run-once`
- Ежедневный цикл:
  - В 07:00 МСК планировщик запускает `run-once`; публикация автоматически ставится на 11:00 МСК
- Еженедельный отчёт:
  - В воскресенье в 19:00 МСК запускается `weekly`: `./.venv/Scripts/python.exe -m src.main weekly`

Используйте любой планировщик (Task Scheduler, cron, CI). Часовая зона: `Europe/Moscow`.

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

- **Язык и CLI**: Python 3.10+, Typer
- **Сетевые вызовы и парсинг**: requests, BeautifulSoup4, feedparser
- **Источники тем**: Hacker News (REST), Reddit (RSS/JSON), Google Trends (pytrends), GitHub Trending (HTML‑парсинг), Telegram RSS (опц.), Yandex Suggest (опц.)
- **Генерация контента и обложек**: OpenAI Python SDK (Chat Completions, Images DALL‑E 3), Pillow
- **Фактчекинг**: AST‑проверка Python, Piston API (песочница сниппетов) / Replit API (опц.), Google Custom Search API
- **Публикация**: Ghost Admin API, PyJWT (JWT для Ghost, выравнивание времени по заголовку Date)
- **Аналитика**: Google Analytics 4 (google-analytics-data), Ghost Admin API (метаданные постов), to.click (CTR)
- **Отчёты**: reportlab (PDF), SMTP (отправка email)
- **Конфигурация и время**: python-dotenv, pytz
- **Качество кода**: Ruff (линт/форматирование) + pre-commit
- **Планирование**: планировщик ОС (Windows Task Scheduler/cron)
