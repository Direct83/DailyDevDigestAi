"""Хранилище состояния: предотвращение повторов тем в течение N дней."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Set, ClassVar
import re
import time
import logging

import requests

from .config import Config
from email.utils import parsedate_to_datetime


def _ghost_headers() -> Dict[str, str]:
    """JWT с учётом серверного времени Ghost (устойчивее к расхождению часов)."""
    if not (Config.GHOST_ADMIN_API_URL and Config.GHOST_ADMIN_API_KEY):
        return {}
    import jwt
    import requests

    def _get_server_epoch() -> int:
        try:
            base = Config.GHOST_ADMIN_API_URL.rstrip("/") + "/ghost/api/admin"
            r = requests.get(base + "/site/", timeout=10)
            date_hdr = r.headers.get("Date")
            if date_hdr:
                dt_ = parsedate_to_datetime(date_hdr)
                if dt_.tzinfo is None:
                    dt_ = dt_.replace(tzinfo=timezone.utc)
                return int(dt_.timestamp())
        except Exception:
            pass
        return int(datetime.utcnow().timestamp())

    kid, secret = Config.GHOST_ADMIN_API_KEY.split(":", 1)
    now_epoch = _get_server_epoch()
    header = {"alg": "HS256", "typ": "JWT", "kid": kid}
    payload = {"iat": now_epoch, "exp": now_epoch + 5 * 60, "aud": "/v5/admin/"}
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
            # Ищем по updated_at за 20 дней во всех статусах, затем сравниваем заголовки без регистра
            q = f"updated_at:>\"{since}\""
            r = requests.get(
                base + f"/posts/?filter={q}&fields=title,updated_at,status&limit=50&order=updated_at%20desc",
                headers=headers,
                timeout=30,
            )
            if r.status_code >= 400:
                return False
            posts = r.json().get("posts", [])
            normalized = title.strip().lower()
            return any((p.get("title", "").strip().lower() == normalized) for p in posts)
        except Exception:
            return False

    def add_topic(self, title: str) -> None:
        # Больше не храним локально; факт публикации есть в Ghost
        return

    def get_recent_titles(self) -> List[str]:
        if not Config.GHOST_ADMIN_API_URL:
            logging.info("Ghost not configured; recent_titles=0")
            return []
        base = Config.GHOST_ADMIN_API_URL.rstrip("/") + "/ghost/api/admin"
        since = (datetime.now(timezone.utc) - timedelta(days=self.history_days)).isoformat()
        headers = _ghost_headers()
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                q = f"updated_at:>\"{since}\""
                r = requests.get(
                    base + f"/posts/?filter={q}&fields=title,updated_at,status&limit=100&order=updated_at%20desc",
                    headers=headers,
                    timeout=30,
                )
                if r.status_code >= 400:
                    # Fallback: без server-side фильтра, отберём по времени на клиенте
                    r2 = requests.get(
                        base + f"/posts/?fields=title,updated_at,status&limit=100&order=updated_at%20desc",
                        headers=headers,
                        timeout=30,
                    )
                    if r2.status_code >= 400:
                        last_err = RuntimeError(f"Ghost HTTP {r.status_code}/{r2.status_code}")
                    else:
                        posts = r2.json().get("posts", [])
                        titles = [p.get("title", "") for p in posts if (p.get("updated_at") and p.get("updated_at") >= since)]
                        logging.info("Ghost recent titles fetched (fallback): %s", len(titles))
                        if titles:
                            return titles
                else:
                    posts = r.json().get("posts", [])
                    titles = [p.get("title", "") for p in posts]
                    logging.info("Ghost recent titles fetched: %s", len(titles))
                    if titles:
                        return titles
            except Exception as e:
                last_err = e
            time.sleep(1.0)
        logging.warning("Ghost recent titles unavailable: %s", last_err)
        return []

    # --- Внутренние утилиты похожести тем ---
    _STOP: ClassVar[Set[str]] = {
        "the","and","for","with","from","this","that","open","available","device","local","run",
        "управление","через","для","как","и","или","по","код","кодом","конфигурации","инфраструктуры",
        "инфраструктурой","безопасное","предсказуемое","автоматизация","обзор","введение","гайд","урок","курс",
        "что","это","про","с","на","от","до","по","через","практика","пример","часть"
    }

    @classmethod
    def _tokens(cls, text: str) -> Set[str]:
        raw = [t for t in re.split(r"[^\w\-/]+", (text or "").lower()) if t]
        tokens = set()
        for t in raw:
            if len(t) < 3:
                continue
            if t in cls._STOP:
                continue
            tokens.add(t)
        return tokens

    @classmethod
    def _is_similar(cls, a: str, b: str) -> bool:
        ta, tb = cls._tokens(a), cls._tokens(b)
        if not ta or not tb:
            return False
        inter = ta & tb
        brand_hit = any(len(tok) >= 5 for tok in inter)
        jacc = len(inter) / max(1, len(ta | tb))
        return brand_hit or jacc >= 0.5

    @classmethod
    def _is_similar_to_recent(cls, title: str, recent_titles: List[str]) -> bool:
        norm = title.strip().lower()
        for t in recent_titles:
            if (t or "").strip().lower() == norm:
                return True
            if cls._is_similar(title, t or ""):
                return True
        return False

