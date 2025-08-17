"""Глобальная конфигурация и доступ к переменным окружения.

Используется для централизованного управления ключами и параметрами.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Загружаем .env при наличии
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "", "None") else default


def _df_str(name: str, default: str | None = None):
    """Default factory: str or None from env with fallback."""
    return lambda: get_env(name, default)


def _df_str_nn(name: str, default: str):
    """Default factory: non-nullable str from env with fallback to default."""
    return lambda: get_env(name, default) or default


def _df_int(name: str, default: int):
    """Default factory: int from env with fallback to default."""
    return lambda: int(get_env(name, str(default)) or str(default))


class Config:
    # OpenAI
    OPENAI_API_KEY: str | None = get_env("OPENAI_API_KEY")
    OPENAI_MODEL: str = get_env("OPENAI_MODEL", "gpt-5")
    OPENAI_IMAGE_MODEL: str = get_env("OPENAI_IMAGE_MODEL", "dall-e-3")

    # Ghost Admin API
    GHOST_ADMIN_API_URL: str | None = get_env("GHOST_ADMIN_API_URL")
    GHOST_ADMIN_API_KEY: str | None = get_env("GHOST_ADMIN_API_KEY")  # format: <id>:<secret_hex>

    # Google Custom Search (для фактчекинга)
    GOOGLE_API_KEY: str | None = get_env("GOOGLE_API_KEY")
    GOOGLE_CSE_ID: str | None = get_env("GOOGLE_CSE_ID")

    # Google Analytics 4 (для аналитики: сбор данных о просмотрах)
    GA4_PROPERTY_ID: str | None = get_env("GA4_PROPERTY_ID")
    GA4_JSON_KEY_PATH: str | None = get_env("GA4_JSON_KEY_PATH")

    # to.click (CTR на CTA)
    TOCLICK_API_KEY: str | None = get_env("TOCLICK_API_KEY")
    TOCLICK_BASE_URL: str = get_env("TOCLICK_BASE_URL", "https://to.click/api")

    # CTA (JSON-массив), пример см. env.example
    CTAS_JSON: str | None = get_env("CTAS_JSON")

    # Telegram RSS (выбор популярных тем — список URL через запятую)
    TELEGRAM_RSS_FEEDS: str | None = get_env("TELEGRAM_RSS_FEEDS")

    # Песочница кода: piston (по умолчанию) или replit
    SANDBOX_PROVIDER: str = get_env("SANDBOX_PROVIDER", "piston").lower()
    REPLIT_EVAL_URL: str | None = get_env("REPLIT_EVAL_URL")
    REPLIT_EVAL_TOKEN: str | None = get_env("REPLIT_EVAL_TOKEN")

    # SMTP (для отправки отчётов)
    SMTP_HOST: str | None = get_env("SMTP_HOST")
    SMTP_PORT: int = int(get_env("SMTP_PORT", "587"))
    SMTP_USER: str | None = get_env("SMTP_USER")
    SMTP_PASSWORD: str | None = get_env("SMTP_PASSWORD")
    REPORT_EMAIL_TO: str | None = get_env("REPORT_EMAIL_TO")

    # Прочее
    APP_TIMEZONE: str = get_env("APP_TIMEZONE", "Europe/Moscow")

    @classmethod
    def ensure_dirs(cls) -> None:
        # Больше не требуется локальная директория data
        return
