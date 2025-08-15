"""Доменная логика антидублирования тем.

Единая реализация токенизации заголовков и правил похожести.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_STOP = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    # русские служебные
    "и",
    "или",
    "по",
    "на",
    "от",
    "до",
    "что",
    "это",
}


def tokens(text: str) -> set[str]:
    """Разбивает заголовок на нормализованные токены.

    Удаляет служебные слова и слишком короткие токены, приводит к нижнему регистру.
    """
    raw = [t for t in re.split(r"[^\w\-/]+", (text or "").lower()) if t]
    result: set[str] = set()
    for t in raw:
        if len(t) < 3:
            continue
        if t in _STOP:
            continue
        result.add(t)
    return result


def anchors(text: str, *, min_len: int = 7) -> set[str]:
    """Возвращает «якорные» токены длиной не меньше `min_len`."""
    return {t for t in tokens(text) if len(t) >= min_len}


def is_similar(a: str, b: str) -> bool:
    """Возвращает True, если заголовки похожи по токенам.

    Эвристика: пересечение токенов с «бренд‑хитом» (любой токен длиной ≥5)
    или достаточный Jaccard‑индекс (≥ 0.5).
    """
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    inter = ta & tb
    brand_hit = any(len(tok) >= 5 for tok in inter)
    jacc = len(inter) / max(1, len(ta | tb))
    return brand_hit or jacc >= 0.5


def quick_duplicate_heuristic(candidate: str, recent_titles: Iterable[str]) -> bool:
    """Быстрая ручная эвристика дублей на случай недоступности LLM.

    Правило: если у кандидата ≥ 7 слов и хотя бы одно слово длиной ≥ 7 символов
    встречается в любом из недавних заголовков, считаем дубликатом.
    """
    cand_tokens = [t for t in candidate.split() if t]
    if len(cand_tokens) < 7:
        return False
    long_words = {t.lower() for t in cand_tokens if len(t) >= 7}
    if not long_words:
        return False
    for title in recent_titles:
        lower = (title or "").lower()
        if any(w in lower for w in long_words):
            return True
    return False


def is_similar_to_recent(title: str, recent_titles: Iterable[str]) -> bool:
    """Проверяет заголовок на дубли с недавними заголовками."""
    norm = (title or "").strip().lower()
    for t in recent_titles:
        tt = (t or "").strip().lower()
        if tt == norm:
            return True
        if is_similar(title, t or ""):
            return True
    return False


def anchor_freq(titles: Iterable[str], *, min_len: int = 7) -> dict[str, int]:
    """Строит частоты якорей по списку заголовков."""
    freq: dict[str, int] = {}
    for t in titles:
        for tok in tokens(t):
            if len(tok) >= min_len:
                freq[tok] = freq.get(tok, 0) + 1
    return freq
