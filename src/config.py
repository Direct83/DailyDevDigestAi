"""Глобальная конфигурация и доступ к переменным окружения.

Используется для централизованного управления ключами и параметрами.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


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


