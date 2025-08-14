"""LLM‑проверка дубликатов тем по смыслу.

Использует OpenAI Chat Completions, чтобы определить, совпадает ли по смыслу
новый заголовок с любым из недавних заголовков из Ghost. Возвращает True,
если найден дубликат (нужно отбросить тему), иначе False.
"""

from __future__ import annotations

from collections.abc import Iterable

from .config import Config


def _openai_client():
    if not Config.OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI

        return OpenAI(api_key=Config.OPENAI_API_KEY)
    except Exception:
        return None


def llm_is_duplicate(candidate_title: str, recent_titles: Iterable[str], *, model: str | None = None) -> bool:
    """Проверяет, является ли `candidate_title` по смыслу дубликатом одного из `recent_titles`.

    Возвращает True, если LLM считает, что совпадает по смыслу (дубликат), иначе False.
    Если LLM недоступен, всегда возвращает False (фолбэк — верхний уровень решает, что делать).
    """
    client = _openai_client()
    if not client:
        return False

    titles = [t.strip() for t in recent_titles if t and t.strip()]
    if not titles:
        return False

    if model is None:
        model = Config.OPENAI_MODEL

    # Форматируем до разумного лимита, чтобы не раздувать промпт
    max_list = 40
    listed = "\n".join(f"- {t}" for t in titles[:max_list])

    system = "Ты строгий помощник-редактор. Твоя задача — только проверка на дубликат темы по смыслу."
    user = (
        "Ниже список недавних заголовков статей. И дана новая кандидатная тема.\n"
        "Ответь строго одним словом: YES (если кандидат — дубликат по смыслу любого из списка)"
        " или NO (если не дубликат). Никаких пояснений.\n\n"
        f"Список заголовков (последние 20 дней):\n{listed}\n\n"
        f"Кандидат: {candidate_title}\n"
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
            max_tokens=2,
        )
        answer = (resp.choices[0].message.content or "").strip().lower()
        return answer.startswith("y")  # YES
    except Exception:
        return False
