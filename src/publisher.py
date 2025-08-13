"""Модуль публикации статьи в Ghost."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .config import ghost_config
from .ghost_client import schedule_post


def _build_tags(article: str) -> list[str]:
    # Тег темы + системные теги из конфига
    title = (article.splitlines()[0].lstrip("# ").strip() or "Без названия")
    topic_tag = title.split("—")[0].split(":")[0].strip()
    base = list(ghost_config.default_tags)
    if topic_tag and topic_tag not in base:
        base.insert(0, topic_tag)
    return base


def publish(article: str, cover: bytes, publish_time: datetime) -> None:
    """Публикует статью с обложкой в Ghost.

    MVP: dry-run — печатает параметры. Реальная интеграция — через Ghost Admin API.
    """
    tz_aware = publish_time
    if publish_time.tzinfo is None:
        # Считаем, что вход — время в Europe/Moscow, конвертируем в UTC
        msk = ZoneInfo("Europe/Moscow")
        tz_aware = publish_time.replace(tzinfo=msk).astimezone(timezone.utc)

    # Если ключи заданы — пробуем реальный вызов
    if ghost_config.admin_api_url and ghost_config.admin_api_key:
        url = schedule_post(
            title=article.splitlines()[0].lstrip("# ").strip() or "Без названия",
            html=article,
            tags=_build_tags(article),
            publish_time=tz_aware,
        )
        if url:
            print("Опубликовано/запланировано в Ghost:", url)
            return

    print("[DRY-RUN] Публикация в Ghost:")
    print("- URL:", ghost_config.admin_api_url)
    print("- Теги:", ", ".join(ghost_config.default_tags))
    print("- Время публикации:", tz_aware.isoformat())
    print("- Длина статьи:", len(article))
    print("- Обложка (байт):", len(cover))
