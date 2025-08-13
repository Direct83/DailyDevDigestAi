"""Модуль вставки рекламных CTA."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests

from .config import Config


@dataclass
class CTA:
    type: str
    title: str
    url: str
    priority: int | None = None
    fresh: bool = False


class CTAProvider:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path  # локальный файл больше не обязателен
        self._ctas: List[CTA] = []
        self._load()

    def _load(self) -> None:
        # 1) ENV CTAS_JSON
        if Config.CTAS_JSON:
            try:
                raw: List[Dict] = json.loads(Config.CTAS_JSON)
                self._ctas = [CTA(**x) for x in raw]
                if self._ctas:
                    self._prioritize()
                    return
            except Exception:
                pass
        # 2) to.click API (условно: /ctas)
        if Config.TOCLICK_API_KEY:
            try:
                url = (Config.TOCLICK_BASE_URL or "https://to.click/api").rstrip("/") + "/ctas"
                r = requests.get(url, headers={"Authorization": f"Bearer {Config.TOCLICK_API_KEY}"}, timeout=20)
                if r.status_code < 400:
                    raw = r.json()
                    if isinstance(raw, list):
                        self._ctas = [CTA(**x) for x in raw]
                        if self._ctas:
                            self._prioritize()
                            return
            except Exception:
                pass
        # 3) Локальный файл (опционально)
        if self.path and Path(self.path).exists():
            try:
                with Path(self.path).open("r", encoding="utf-8") as f:
                    raw = json.load(f)
                self._ctas = [CTA(**x) for x in raw]
                self._prioritize()
                return
            except Exception:
                pass
        self._ctas = []

    def _prioritize(self) -> None:
        # Сначала свежие, затем по priority (меньше — выше), затем прочие; сохраняем порядок
        def sort_key(c: CTA):
            fresh_rank = 0 if c.fresh else 1
            prio = c.priority if isinstance(c.priority, int) else 999
            return (fresh_rank, prio)

        self._ctas.sort(key=sort_key)

    def pick_pair(self) -> List[CTA]:
        free = [c for c in self._ctas if c.type.lower() in {"free", "freebie"}]
        course = [c for c in self._ctas if c.type.lower() in {"course", "program"}]
        result: List[CTA] = []
        # ограничим выбор верхними 5 по приоритету
        if free:
            result.append(random.choice(free[: min(5, len(free))]))
        if course:
            result.append(random.choice(course[: min(5, len(course))]))
        if not result and self._ctas:
            pool = self._ctas[: min(6, len(self._ctas))]
            result = random.sample(pool, k=min(2, len(pool)))
        return result

    @staticmethod
    def render_cta_html(cta: CTA) -> str:
        return (
            f'<div class="cta-block" style="border:1px solid #eee;padding:16px;border-radius:8px;margin:24px 0;">'
            f'<div style="font-weight:700;margin-bottom:8px;">{cta.title}</div>'
            f'<a href="{cta.url}" target="_blank" rel="noopener" style="color:#0057ff;">Перейти</a>'
            f"</div>"
        )
