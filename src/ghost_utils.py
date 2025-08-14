"""Утилиты для Ghost Admin API: базовый URL, JWT и общий fetch.

- ghost_admin_base: собирает базовый адрес Admin API
- ghost_auth_headers: генерирует JWT с выравниванием по серверному времени
- fetch_posts: обёртка GET /posts с параметрами NQL
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import jwt
import requests

from .config import Config


def ghost_admin_base() -> str:
    if not Config.GHOST_ADMIN_API_URL:
        raise RuntimeError("GHOST_ADMIN_API_URL is not configured")
    return Config.GHOST_ADMIN_API_URL.rstrip("/") + "/ghost/api/admin"


def _server_epoch(base: str) -> int:
    try:
        r = requests.get(base + "/site/", timeout=10)
        date_hdr = r.headers.get("Date")
        if date_hdr:
            dt_ = parsedate_to_datetime(date_hdr)
            if dt_ and dt_.tzinfo is not None:
                return int(dt_.timestamp())
    except Exception:
        pass
    return int(datetime.utcnow().replace(tzinfo=timezone.utc).timestamp())


def ghost_auth_headers() -> dict[str, str]:
    """Возвращает заголовки авторизации Ghost (JWT) с iat/exp по времени сервера."""
    if not (Config.GHOST_ADMIN_API_URL and Config.GHOST_ADMIN_API_KEY):
        return {}
    base = ghost_admin_base()
    kid, secret = Config.GHOST_ADMIN_API_KEY.split(":", 1)
    now_epoch = _server_epoch(base)
    header = {"alg": "HS256", "typ": "JWT", "kid": kid}
    payload = {"iat": now_epoch, "exp": now_epoch + 5 * 60, "aud": "/v5/admin/"}
    token = jwt.encode(payload, bytes.fromhex(secret), algorithm="HS256", headers=header)
    return {"Authorization": f"Ghost {token}"}


def fetch_posts(
    *,
    filter: str | None = None,
    fields: str = "title,slug,status,published_at,updated_at",
    order: str | None = None,
    limit: int = 100,
    timeout: int = 60,
) -> list[dict[str, Any]]:
    """GET /posts с параметрами NQL, возвращает список постов (dict).

    Исключения не скрываем — пусть вызывающая сторона решает, как обрабатывать.
    """
    base = ghost_admin_base()
    params: dict[str, Any] = {"fields": fields, "limit": str(limit)}
    if filter:
        params["filter"] = filter
    if order:
        params["order"] = order
    r = requests.get(base + "/posts/", headers=ghost_auth_headers(), params=params, timeout=timeout)
    r.raise_for_status()
    return r.json().get("posts", [])


def upload_image_bytes(image_bytes: bytes, filename: str = "cover.png", *, timeout: int = 60) -> str | None:
    """Загружает изображение в Ghost и возвращает URL или None при ошибке."""
    base = ghost_admin_base()
    try:
        files = {"file": (filename, image_bytes, "image/png")}
        r = requests.post(base + "/images/upload/", headers=ghost_auth_headers(), files=files, timeout=timeout)
        if r.status_code >= 400:
            return None
        data = r.json()
        return data.get("images", [{}])[0].get("url")
    except Exception:
        return None


def publish_html_post(
    *,
    title: str,
    html: str,
    tags: list[str] | None,
    feature_image: str | None,
    status: str,
    published_at: str | None,
    timeout: int = 60,
) -> dict:
    """Публикация/планирование поста через Admin API /posts?source=html.

    Возвращает JSON ответа или поднимает исключение при HTTP>=400.
    """
    base = ghost_admin_base()
    tag_objects: list[dict[str, str]] = [{"name": t} for t in (tags or []) if t]
    payload = {
        "posts": [
            {
                "title": title,
                "html": html,
                "status": status,
                **({"published_at": published_at} if published_at else {}),
                **({"feature_image": feature_image} if feature_image else {}),
                "tags": tag_objects,
            },
        ],
    }
    r = requests.post(base + "/posts/?source=html", headers=ghost_auth_headers(), json=payload, timeout=timeout)
    if r.status_code >= 400:
        r.raise_for_status()
    return r.json()
