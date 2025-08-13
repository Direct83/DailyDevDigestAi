"""Модуль публикации статьи в Ghost."""
from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional

import jwt
import pytz
import requests

from .config import Config


class GhostPublisher:
    def __init__(self) -> None:
        if not (Config.GHOST_ADMIN_API_URL and Config.GHOST_ADMIN_API_KEY):
            raise RuntimeError("Не настроен Ghost Admin API")
        self.base = Config.GHOST_ADMIN_API_URL.rstrip("/") + "/ghost/api/admin"
        self._token = self._make_jwt(Config.GHOST_ADMIN_API_KEY)
        self.headers = {"Authorization": f"Ghost {self._token}"}

    def _make_jwt(self, admin_key: str) -> str:
        kid, secret = admin_key.split(":", 1)
        iat = int(dt.datetime.utcnow().timestamp())
        header = {"alg": "HS256", "typ": "JWT", "kid": kid}
        payload = {"iat": iat, "exp": iat + 5 * 60, "aud": "/v5/admin/"}
        token = jwt.encode(payload, bytes.fromhex(secret), algorithm="HS256", headers=header)
        return token

    def upload_image_bytes(self, image_bytes: bytes, filename: str = "cover.png") -> Optional[str]:
        try:
            files = {"file": (filename, image_bytes, "image/png")}
            r = requests.post(self.base + "/images/upload/", headers=self.headers, files=files, timeout=60)
            r.raise_for_status()
            data = r.json()
            return data.get("images", [{}])[0].get("url")
        except Exception:
            return None

    def publish(self, title: str, html: str, tags: List[str], feature_image_bytes: Optional[bytes], schedule_msk_11: bool = True) -> Dict:
        feature_image = None
        if feature_image_bytes:
            feature_image = self.upload_image_bytes(feature_image_bytes)

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

        payload = {
            "posts": [
                {
                    "title": title,
                    "html": html,
                    "status": status,
                    **({"published_at": published_at} if published_at else {}),
                    **({"feature_image": feature_image} if feature_image else {}),
                    "tags": list({*(tags or []), "AI Generated"}),
                }
            ]
        }
        r = requests.post(self.base + "/posts/?source=html", headers=self.headers, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()
