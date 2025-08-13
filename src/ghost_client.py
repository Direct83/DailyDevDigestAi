"""Клиент для публикации в Ghost Admin API.

Если нет ключей/URL — функции возвращают None и используются в dry-run режиме.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
import jwt

from .config import ghost_config


@dataclass
class GhostCredentials:
    url: str
    admin_api_key: str


def _get_credentials() -> Optional[GhostCredentials]:
    if not ghost_config.admin_api_url or not ghost_config.admin_api_key:
        return None
    return GhostCredentials(url=ghost_config.admin_api_url.rstrip("/"), admin_api_key=ghost_config.admin_api_key)


def _build_admin_jwt(creds: GhostCredentials) -> Optional[str]:
    """Строит JWT для Ghost Admin API из ключа формата id:secret.

    Возвращает строку токена или None, если формат неверен.
    """
    try:
        key_id, secret = creds.admin_api_key.strip().split(":", 1)
    except ValueError:
        return None

    now = datetime.now(timezone.utc)
    payload = {
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        # Аудитория по документации Ghost Admin API v5
        "aud": "/v5/admin/",
    }
    headers = {"kid": key_id}

    token = jwt.encode(payload, bytes.fromhex(secret), algorithm="HS256", headers=headers)
    # PyJWT v2 возвращает строку
    return token


def schedule_post(title: str, html: str, tags: list[str], publish_time: datetime) -> Optional[str]:
    creds = _get_credentials()
    if not creds:
        return None

    token = _build_admin_jwt(creds)
    if not token:
        return None

    headers = {"Authorization": f"Ghost {token}", "Content-Type": "application/json"}

    payload = {
        "posts": [
            {
                "title": title,
                "html": html,
                "status": "scheduled",
                "published_at": publish_time.isoformat(),
                "tags": tags,
            }
        ]
    }

    # Поддерживаем как базовый URL блога, так и уже указанный admin-путь
    base = creds.url.rstrip("/")
    admin_base = base if "/ghost/api/admin" in base else f"{base}/ghost/api/admin"

    try:
        resp = requests.post(
            f"{admin_base}/posts/?source=html",
            headers=headers,
            data=json.dumps(payload),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and data.get("posts"):
            return data["posts"][0].get("url")
    except Exception:
        return None
    return None


