"""Хранилище состояния: предотвращение повторов тем в течение N дней."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests

from .config import Config


def _ghost_headers() -> Dict[str, str]:
    if not (Config.GHOST_ADMIN_API_URL and Config.GHOST_ADMIN_API_KEY):
        return {}
    import jwt

    kid, secret = Config.GHOST_ADMIN_API_KEY.split(":", 1)
    iat = int(datetime.utcnow().timestamp())
    header = {"alg": "HS256", "typ": "JWT", "kid": kid}
    payload = {"iat": iat, "exp": iat + 5 * 60, "aud": "/v5/admin/"}
    token = jwt.encode(payload, bytes.fromhex(secret), algorithm="HS256", headers=header)
    return {"Authorization": f"Ghost {token}"}


@dataclass
class StateStore:
    history_days: int = 20

    def is_recent_topic(self, title: str) -> bool:
        # Если Ghost не настроен — не можем проверить, считаем, что нет дубля
        if not Config.GHOST_ADMIN_API_URL:
            return False
        base = Config.GHOST_ADMIN_API_URL.rstrip("/") + "/ghost/api/admin"
        since = (datetime.now(timezone.utc) - timedelta(days=self.history_days)).isoformat()
        headers = _ghost_headers()
        try:
            q = f"title:'{title.replace("'", "\\'")}' + published_at:>\"{since}\""
            r = requests.get(
                base + f"/posts/?filter={q}&fields=title,published_at&limit=1",
                headers=headers,
                timeout=30,
            )
            if r.status_code >= 400:
                return False
            posts = r.json().get("posts", [])
            return any(p.get("title", "").strip().lower() == title.strip().lower() for p in posts)
        except Exception:
            return False

    def add_topic(self, title: str) -> None:
        # Больше не храним локально; факт публикации есть в Ghost
        return


