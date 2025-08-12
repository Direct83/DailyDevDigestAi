"""Модуль публикации статьи в Ghost."""
from __future__ import annotations

from datetime import datetime, timezone

from .config import ghost_config
from .ghost_client import schedule_post


def publish(article: str, cover: bytes, publish_time: datetime) -> None:
    """Публикует статью с обложкой в Ghost.

    MVP: dry-run — печатает параметры. Реальная интеграция — через Ghost Admin API.
    """
    tz_aware = publish_time
    if publish_time.tzinfo is None:
        tz_aware = publish_time.replace(tzinfo=timezone.utc)

    # Если ключи заданы — пробуем реальный вызов
    if ghost_config.admin_api_url and ghost_config.admin_api_key:
        url = schedule_post(
            title=article.splitlines()[0].lstrip("# ").strip() or "Без названия",
            html=article,
            tags=list(ghost_config.default_tags),
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
