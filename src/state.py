"""Хранилище состояния: предотвращение повторов тем в течение N дней."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import ClassVar

from .config import Config
from .domain.dedup import is_similar as _dd_is_similar
from .domain.dedup import tokens as _dd_tokens
from .ghost_utils import fetch_posts


@dataclass
class StateStore:
    history_days: int = 20

    def is_recent_topic(self, title: str) -> bool:
        """Проверяет, публиковался ли идентичный заголовок за последние `history_days`.

        Запрашивает посты из Ghost по `updated_at` и сравнивает заголовки без регистра.
        При ошибках сети/авторизации возвращает False (не блокируем публикацию).
        """
        # Если Ghost не настроен — не можем проверить, считаем, что нет дубля
        if not Config.GHOST_ADMIN_API_URL:
            return False
        since_dt = datetime.now(timezone.utc) - timedelta(days=self.history_days)
        since = since_dt.strftime("%Y-%m-%d %H:%M:%S")
        try:
            # Ищем по updated_at за 20 дней во всех статусах, затем сравниваем заголовки без регистра
            posts = fetch_posts(
                filter=f"updated_at:>'{since}'",
                fields="title,updated_at,status",
                order="updated_at desc",
                limit=50,
                timeout=30,
            )
            normalized = title.strip().lower()
            return any((p.get("title", "").strip().lower() == normalized) for p in posts)
        except Exception:
            return False

    def add_topic(self, title: str) -> None:
        # Больше не храним локально; факт публикации есть в Ghost
        return

    def get_recent_titles(self) -> list[str]:
        """Возвращает заголовки постов в Ghost за последние `history_days`.

        Сначала пытается применить фильтр на стороне сервера; если API вернул
        ошибку, делает запасной запрос без фильтра и отбраковывает по времени на
        клиенте. Используется для антидублирования тем.
        """
        if not Config.GHOST_ADMIN_API_URL:
            logging.info("Ghost not configured; recent_titles=0")
            return []
        since_dt = datetime.now(timezone.utc) - timedelta(days=self.history_days)
        since = since_dt.strftime("%Y-%m-%d %H:%M:%S")
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                posts = fetch_posts(
                    filter=f"updated_at:>'{since}'",
                    fields="title,updated_at,status",
                    order="updated_at desc",
                    limit=100,
                    timeout=30,
                )
                titles = [p.get("title", "") for p in posts]
                logging.info("Ghost recent titles fetched: %s", len(titles))
                if titles:
                    return titles
            except Exception as e:
                last_err = e
            # fallback: без фильтра на сервере — фильтруем на клиенте
            try:
                posts = fetch_posts(
                    fields="title,updated_at,status",
                    order="updated_at desc",
                    limit=100,
                    timeout=30,
                )
                titles = [
                    p.get("title", "") for p in posts if (p.get("updated_at") and str(p.get("updated_at")) >= since)
                ]
                logging.info("Ghost recent titles fetched (fallback): %s", len(titles))
                if titles:
                    return titles
            except Exception as e2:
                last_err = e2
            time.sleep(1.0)
        logging.warning("Ghost recent titles unavailable: %s", last_err)
        return []

    # --- Внутренние утилиты похожести тем ---
    _STOP: ClassVar[set[str]] = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "this",
        "that",
        "open",
        "available",
        "device",
        "local",
        "run",
        "управление",
        "через",
        "для",
        "как",
        "и",
        "или",
        "по",
        "код",
        "кодом",
        "конфигурации",
        "инфраструктуры",
        "инфраструктурой",
        "безопасное",
        "предсказуемое",
        "автоматизация",
        "обзор",
        "введение",
        "гайд",
        "урок",
        "курс",
        "что",
        "это",
        "про",
        "с",
        "на",
        "от",
        "до",
        "по",
        "через",
        "практика",
        "пример",
        "часть",
    }

    @classmethod
    def _tokens(cls, text: str) -> set[str]:
        # делегируем доменной реализации, но сохраняем STOP для обратной совместимости
        return {t for t in _dd_tokens(text) if t not in cls._STOP}

    @classmethod
    def _is_similar(cls, a: str, b: str) -> bool:
        return _dd_is_similar(a, b)

    @classmethod
    def _is_similar_to_recent(cls, title: str, recent_titles: list[str]) -> bool:
        norm = title.strip().lower()
        for t in recent_titles:
            if (t or "").strip().lower() == norm:
                return True
            if cls._is_similar(title, t or ""):
                return True
        return False
