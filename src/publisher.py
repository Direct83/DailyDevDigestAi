"""Модуль публикации статьи в Ghost."""

from datetime import datetime


def publish(article: str, cover: bytes, publish_time: datetime) -> None:
    """Публикует статью с обложкой в Ghost."""
    # TODO: интеграция с Ghost Admin API
    print(f"Статья запланирована на {publish_time}")
