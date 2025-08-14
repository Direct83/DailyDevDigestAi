"""Глобальная конфигурация и доступ к переменным окружения.

Используется для централизованного управления ключами и параметрами.
"""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional

# Загружаем .env при наличии
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "", "None") else default


class Config:
    # OpenAI
    OPENAI_API_KEY: str | None = get_env("OPENAI_API_KEY")
    OPENAI_MODEL: str = get_env("OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini"
    OPENAI_IMAGE_MODEL: str = get_env("OPENAI_IMAGE_MODEL", "dall-e-3") or "dall-e-3"

    # Ghost Admin
    GHOST_ADMIN_API_URL: str | None = get_env("GHOST_ADMIN_API_URL")
    GHOST_ADMIN_API_KEY: str | None = get_env("GHOST_ADMIN_API_KEY")  # format: <id>:<secret_hex>

    # Content API (опционально)
    GHOST_CONTENT_API_URL: str | None = get_env("GHOST_CONTENT_API_URL")
    GHOST_CONTENT_API_KEY: str | None = get_env("GHOST_CONTENT_API_KEY")

    # Google CSE (фактчекинг)
    GOOGLE_API_KEY: str | None = get_env("GOOGLE_API_KEY")
    GOOGLE_CSE_ID: str | None = get_env("GOOGLE_CSE_ID")

    # GA4 (опционально)
    GA4_PROPERTY_ID: str | None = get_env("GA4_PROPERTY_ID")
    GA4_JSON_KEY_PATH: str | None = get_env("GA4_JSON_KEY_PATH")

    # to.click
    TOCLICK_API_KEY: str | None = get_env("TOCLICK_API_KEY")
    TOCLICK_BASE_URL: str = get_env("TOCLICK_BASE_URL", "https://to.click/api") or "https://to.click/api"

    # CTA из ENV (JSON)
    CTAS_JSON: str | None = get_env("CTAS_JSON")

    # Telegram RSS (через любые публичные RSS-прокси на каналы)
    TELEGRAM_RSS_FEEDS: str | None = get_env("TELEGRAM_RSS_FEEDS")  # comma-separated URLs

    # Яндекс подсказки (approx Wordstat) — список seed-запросов через запятую
    YANDEX_SUGGEST_SEEDS: str | None = get_env("YANDEX_SUGGEST_SEEDS")  # e.g. "как, python, нейросети"

    # Песочница исполнения кода: replit | piston (по умолчанию piston)
    SANDBOX_PROVIDER: str = (get_env("SANDBOX_PROVIDER", "piston") or "piston").lower()
    REPLIT_EVAL_URL: str | None = get_env("REPLIT_EVAL_URL")  # например, https://eval.api.replit.com/eval
    REPLIT_EVAL_TOKEN: str | None = get_env("REPLIT_EVAL_TOKEN")  # Bearer token

    # SMTP
    SMTP_HOST: str | None = get_env("SMTP_HOST")
    SMTP_PORT: int = int(get_env("SMTP_PORT", "587") or "587")
    SMTP_USER: str | None = get_env("SMTP_USER")
    SMTP_PASSWORD: str | None = get_env("SMTP_PASSWORD")
    REPORT_EMAIL_TO: str | None = get_env("REPORT_EMAIL_TO")

    # Прочее
    APP_TIMEZONE: str = get_env("APP_TIMEZONE", "Europe/Moscow") or "Europe/Moscow"

    @classmethod
    def ensure_dirs(cls) -> None:
        # Больше не требуется локальная директория data
        return


@dataclass(frozen=True)
class TimeConfig:
    timezone: str = os.getenv("APP_TIMEZONE", "Europe/Moscow")
    daily_select_hour: int = int(os.getenv("DAILY_SELECT_HOUR", "7"))
    daily_publish_hour: int = int(os.getenv("DAILY_PUBLISH_HOUR", "11"))
    weekly_report_weekday: int = int(os.getenv("WEEKLY_REPORT_WEEKDAY", "6"))  # 0=Mon, 6=Sun
    weekly_report_hour: int = int(os.getenv("WEEKLY_REPORT_HOUR", "19"))


@dataclass(frozen=True)
class OpenAIConfig:
    api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    image_model: str = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")


@dataclass(frozen=True)
class GhostConfig:
    admin_api_url: Optional[str] = os.getenv("GHOST_ADMIN_API_URL")  # например: https://blog.example.com/ghost/api/admin
    admin_api_key: Optional[str] = os.getenv("GHOST_ADMIN_API_KEY")
    default_tags: tuple[str, ...] = ("AI Generated",)


@dataclass(frozen=True)
class EmailConfig:
    smtp_host: Optional[str] = os.getenv("SMTP_HOST")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: Optional[str] = os.getenv("SMTP_USER")
    smtp_password: Optional[str] = os.getenv("SMTP_PASSWORD")
    from_email: Optional[str] = os.getenv("FROM_EMAIL")
    to_email: Optional[str] = os.getenv("TO_EMAIL")


@dataclass(frozen=True)
class PathsConfig:
    data_dir: str = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
    state_file: str = os.getenv("STATE_FILE", os.path.join(os.path.dirname(__file__), "..", "data", "state.json"))
    ctas_file: str = os.getenv("CTAS_FILE", os.path.join(os.path.dirname(__file__), "..", "data", "ctas.json"))


@dataclass(frozen=True)
class SourcesConfig:
    reddit_subs: tuple[str, ...] = tuple(
        s.strip() for s in os.getenv("REDDIT_SUBS", "MachineLearning,webdev,datascience").split(",") if s.strip()
    )
    rss_feeds: tuple[str, ...] = tuple(
        s.strip()
        for s in os.getenv(
            "RSS_FEEDS",
            ",".join(
                [
                    "https://habr.com/ru/rss/all/all/?fl=ru",
                    # Добавляйте свои ленты: TG через RSS‑прокси, корпоративные блоги и т.п.
                ]
            ),
        ).split(",")
        if s.strip()
    )
    github_language_filter: str = os.getenv("GITHUB_LANG", "Python,TypeScript,JavaScript")
    google_trends_geo: str = os.getenv("GOOGLE_TRENDS_GEO", "RU")


@dataclass(frozen=True)
class GoogleSearchConfig:
    api_key: Optional[str] = os.getenv("GOOGLE_API_KEY")
    cse_id: Optional[str] = os.getenv("GOOGLE_CSE_ID")


time_config = TimeConfig()
openai_config = OpenAIConfig()
ghost_config = GhostConfig()
email_config = EmailConfig()
paths_config = PathsConfig()
sources_config = SourcesConfig()
google_search_config = GoogleSearchConfig()


