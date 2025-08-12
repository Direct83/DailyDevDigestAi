"""Модуль выбора темы для статьи."""
from __future__ import annotations

from datetime import datetime
from typing import Tuple

from .state import get_recent_topics, record_topic
from .sources import fetch_candidate_topics


def select_topic() -> Tuple[str, list[str]]:
    """Выбирает тему и тезисы.

    Пока: мок-реализация с антидублем за 20 дней.
    TODO: интеграция с Google Trends, HN, GitHub Trending, Reddit и т.п.
    """
    recent = get_recent_topics(days=20)

    # Кандидаты из HN (последние 48 часов) + fallback-список
    fetched = fetch_candidate_topics()
    fallback = [
        "Как начать с LangChain для быстрых прототипов",
        "10 практик для оптимизации запросов к OpenAI API",
        "Лучшие практики CI/CD для Python-проектов",
        "Как обучить свою RAG‑систему на корпоративных документах",
        "React Server Components: когда применять и зачем",
    ]
    candidates = fetched or fallback

    topic = next((c for c in candidates if c not in recent), None)
    if topic is None:
        today = datetime.now().strftime('%Y-%m-%d')
        topic = f"Свежие тренды в AI и веб‑разработке на {today}"

    thesis = [
        "Кому полезно и зачем",
        "Ключевые шаги/архитектура",
        "Пример кода",
        "Ошибки и анти‑паттерны",
        "Итоги и дальнейшие шаги",
    ]

    record_topic(topic)
    return topic, thesis
