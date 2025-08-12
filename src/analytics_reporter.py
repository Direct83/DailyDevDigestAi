"""Модуль сборки и отправки аналитики."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class WeeklyReport:
    publications: int
    total_views: int
    top_article: str
    top_read_article: str
    cta_ctr: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "publications": self.publications,
            "total_views": self.total_views,
            "top_article": self.top_article,
            "top_read_article": self.top_read_article,
            "cta_ctr": self.cta_ctr,
        }


def collect_weekly_report() -> dict:
    """Собирает статистику за неделю (MVP-заглушка)."""
    report = WeeklyReport(
        publications=7,
        total_views=0,
        top_article="",
        top_read_article="",
        cta_ctr=0.0,
    )
    return report.as_dict()
