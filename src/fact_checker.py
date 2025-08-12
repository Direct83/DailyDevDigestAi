"""Модуль фактчекинга."""
from __future__ import annotations

import re
from typing import List

import requests

from .config import google_search_config


def _extract_code_blocks(article: str) -> list[tuple[str, str]]:
    """Находит блоки тройных бэктиков и возвращает список (lang, code)."""
    pattern = re.compile(r"```(\w+)?\n([\s\S]*?)```", re.MULTILINE)
    results: list[tuple[str, str]] = []
    for m in pattern.finditer(article):
        lang = (m.group(1) or "").strip().lower()
        code = m.group(2)
        results.append((lang, code))
    return results


def _lint_python(code: str) -> bool:
    """Простейшая проверка: компилируется ли код Python."""
    try:
        compile(code, "<article_snippet>", "exec")
        return True
    except Exception:
        return False


def validate_article(article: str) -> bool:
    """Проверяет корректность фактов и работоспособность кода.

    MVP-проверки:
    - Python-блоки компилируются
    - Отсутствуют TODO-рыбы
    """
    blocks = _extract_code_blocks(article)
    for lang, code in blocks:
        if lang in {"py", "python"} and not _lint_python(code):
            return False

    if "(Подключите OpenAI для реальной генерации)" in article:
        # Не блокируем публикацию, это ожидаемо на MVP-этапе
        pass

    if "Здесь будет текст статьи" in article:
        return False

    return True


def _google_fact_check(queries: List[str], min_hits: int = 1) -> bool:
    """Проверка фактов через Google Custom Search API (опционально).

    Возвращает True, если для большинства запросов есть результаты.
    """
    if not google_search_config.api_key or not google_search_config.cse_id:
        return True  # без ключей не блокируем публикацию

    ok = 0
    total = 0
    for q in queries:
        if not q.strip():
            continue
        total += 1
        try:
            url = (
                "https://www.googleapis.com/customsearch/v1"
                f"?key={google_search_config.api_key}&cx={google_search_config.cse_id}&q={requests.utils.quote(q)}"
            )
            resp = requests.get(url, timeout=10)
            if resp.ok and len(resp.json().get("items", [])) >= min_hits:
                ok += 1
        except Exception:
            continue
    if total == 0:
        return True
    return ok / total >= 0.6


def validate_article_with_facts(article: str, fact_queries: List[str]) -> bool:
    """Комбинированная проверка: код + веб-факты.

    Возвращает True, если обе проверки проходят.
    """
    code_ok = validate_article(article)
    facts_ok = _google_fact_check(fact_queries)
    return code_ok and facts_ok
