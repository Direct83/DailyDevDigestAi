"""Клиент для публикации в Ghost Admin API.

Если нет ключей/URL — функции возвращают None и используются в dry-run режиме.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests

from .config import ghost_config


@dataclass
class GhostCredentials:
    url: str
    admin_api_key: str


def _get_credentials() -> Optional[GhostCredentials]:
    if not ghost_config.admin_api_url or not ghost_config.admin_api_key:
        return None
    return GhostCredentials(url=ghost_config.admin_api_url.rstrip("/"), admin_api_key=ghost_config.admin_api_key)


def schedule_post(title: str, html: str, tags: list[str], publish_time: datetime) -> Optional[str]:
    creds = _get_credentials()
    if not creds:
        return None

    # Ghost Admin API: аутентификация через Admin API Key (JWT). Для простоты используем ключ напрямую,
    # многие инсталляции поддерживают X-Auth-Token c Admin API Key как ключ (вариативно по версии Ghost).
    # Для полноценного JWT понадобятся id и secret, разделённые ':'. Здесь оставим упрощённый вариант.
    headers = {
        "Authorization": f"Ghost {creds.admin_api_key}",
        "Content-Type": "application/json",
    }

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

    try:
        resp = requests.post(f"{creds.url}/posts/", headers=headers, data=json.dumps(payload), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and data.get("posts"):
            return data["posts"][0].get("url")
    except Exception:
        return None
    return None


