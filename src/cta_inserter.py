"""Модуль вставки рекламных CTA."""
from __future__ import annotations

import json
import os
import random
from typing import Any, Dict, List

from .config import paths_config


def _load_ctas() -> List[Dict[str, Any]]:
    path = os.path.abspath(paths_config.ctas_file)
    if not os.path.exists(path):
        # Базовый набор по умолчанию
        return [
            {"type": "free", "title": "Бесплатный мастер‑класс по AI", "url": "https://example.com/free-ai"},
            {"type": "course", "title": "Курс по Python для анализа данных", "url": "https://example.com/course-ds"},
        ]
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _render_cta_block(title: str, url: str) -> str:
    return f"\n> ▶ {title}\n> Перейти: {url}\n"


def insert_cta(article: str) -> str:
    """Добавляет минимум 1 CTA на бесплатный продукт и 1 ссылку на основной курс.

    Вставляет блоки после вступления и перед завершением статьи.
    """
    ctas = _load_ctas()
    if not ctas:
        return article

    free_ctas = [c for c in ctas if c.get("type") == "free"]
    course_ctas = [c for c in ctas if c.get("type") in {"course", "program"}]

    blocks: list[str] = []
    if free_ctas:
        c = random.choice(free_ctas)
        blocks.append(_render_cta_block(c.get("title", "Узнай больше"), c.get("url", "#")))
    if course_ctas:
        c = random.choice(course_ctas)
        blocks.append(_render_cta_block(c.get("title", "Основной курс"), c.get("url", "#")))

    if not blocks:
        return article

    # Простая стратегия размещения: после первого абзаца и в конце
    parts = article.split("\n\n", 1)
    if len(parts) == 2:
        intro, rest = parts
        result = intro + "\n\n" + blocks[0] + "\n\n" + rest
    else:
        result = article + "\n\n" + blocks[0]

    if len(blocks) > 1:
        result = result + "\n\n" + blocks[1]

    return result
