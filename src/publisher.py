"""Модуль публикации статьи в Ghost (Admin API v5)."""
from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional

import logging
import jwt
import pytz
import requests
from email.utils import parsedate_to_datetime

from .config import Config


class GhostPublisher:
    def __init__(self) -> None:
        if not (Config.GHOST_ADMIN_API_URL and Config.GHOST_ADMIN_API_KEY):
            raise RuntimeError("Не настроен Ghost Admin API")
        self.base = Config.GHOST_ADMIN_API_URL.rstrip("/") + "/ghost/api/admin"
        # Диагностический минимум
        self._kid = Config.GHOST_ADMIN_API_KEY.split(":", 1)[0]
        self._aud = "/v5/admin/"

    def _get_server_epoch(self) -> int:
        """Пытаемся получить серверное время из заголовка Date у /site/.

        Если не получилось — возвращаем локальное UTC now.
        """
        try:
            url = self.base + "/site/"
            r = requests.get(url, timeout=10)
            date_hdr = r.headers.get("Date")
            if date_hdr:
                dt_ = parsedate_to_datetime(date_hdr)
                if dt_.tzinfo is None:
                    dt_ = dt_.replace(tzinfo=dt.timezone.utc)
                return int(dt_.timestamp())
        except Exception:
            pass
        return int(dt.datetime.utcnow().timestamp())

    def _make_jwt(self, admin_key: str, aud: str = "/v5/admin/") -> str:
        kid, secret = admin_key.split(":", 1)
        server_now = self._get_server_epoch()
        # Устанавливаем iat по времени сервера Ghost, exp = +300с
        iat = max(0, server_now)
        header = {"alg": "HS256", "typ": "JWT", "kid": kid}
        exp = server_now + 300
        payload = {"iat": iat, "exp": exp, "aud": aud}
        token = jwt.encode(payload, bytes.fromhex(secret), algorithm="HS256", headers=header)
        return token

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Ghost {self._make_jwt(Config.GHOST_ADMIN_API_KEY, aud=self._aud)}"}

    def upload_image_bytes(self, image_bytes: bytes, filename: str = "cover.png") -> Optional[str]:
        try:
            files = {"file": (filename, image_bytes, "image/png")}
            r = requests.post(self.base + "/images/upload/", headers=self._auth_headers(), files=files, timeout=60)
            r.raise_for_status()
            data = r.json()
            return data.get("images", [{}])[0].get("url")
        except Exception:
            try:
                logging.warning("Ghost upload_image error: status=%s body=%s", getattr(r, "status_code", None), str(getattr(r, "text", ""))[:300])
            except Exception:
                pass
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
        r = requests.post(self.base + "/posts/?source=html", headers=self._auth_headers(), json=payload, timeout=60)
        r.raise_for_status()
        return r.json()
