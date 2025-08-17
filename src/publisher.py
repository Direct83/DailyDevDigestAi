"""Модуль публикации статьи в Ghost (Admin API v5)."""

from __future__ import annotations

import datetime as dt

import pytz

from .config import Config
from .ghost_utils import ghost_admin_base, publish_html_post, upload_image_bytes


class GhostPublisher:
    def __init__(self) -> None:
        """Публикатор постов в Ghost Admin API v5.

        Требует `GHOST_ADMIN_API_URL` и `GHOST_ADMIN_API_KEY` в окружении.
        """
        if not (Config.GHOST_ADMIN_API_URL and Config.GHOST_ADMIN_API_KEY):
            raise RuntimeError("Не настроен Ghost Admin API")
        self.base = ghost_admin_base()

    def publish(
        self,
        title: str,
        html: str,
        tags: list[str],
        feature_image_bytes: bytes | None,
        schedule_msk_11: bool = True,
    ) -> dict:
        """Публикует/планирует HTML‑пост в Ghost.

        - Ограничивает длину заголовка до 255 символов
        - Загружает feature image при наличии
        - При `schedule_msk_11=True` планирует публикацию на 11:00 МСК ближайшего дня
        """
        # Нормализация заголовка под ограничения Ghost (<=255 символов)
        safe_title = (title or "").strip()
        if len(safe_title) > 255:
            safe_title = safe_title[:252].rstrip() + "..."

        feature_image = None
        if feature_image_bytes:
            feature_image = upload_image_bytes(feature_image_bytes)

        status = "published"
        published_at = None
        if schedule_msk_11:
            tz = pytz.timezone(Config.APP_TIMEZONE or "Europe/Moscow")
            now = dt.datetime.now(tz)
            scheduled = now.replace(hour=11, minute=0, second=0, microsecond=0)
            if now >= scheduled:
                scheduled = scheduled + dt.timedelta(days=1)
            published_at = scheduled.astimezone(pytz.utc).isoformat()
            status = "scheduled"

        # Нормализуем теги и публикуем через общий util
        uniq_tags: list[str] = list({*(tags or []), "AI Generated"})
        return publish_html_post(
            title=safe_title,
            html=html,
            tags=uniq_tags,
            feature_image=feature_image,
            status=status,
            published_at=published_at,
        )
