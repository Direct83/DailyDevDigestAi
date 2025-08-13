"""Модуль генерации статьи."""
from __future__ import annotations

from textwrap import dedent
from typing import List

from .config import openai_config

try:
    from openai import OpenAI  # type: ignore
except Exception:  # пакет может отсутствовать на мок-этапе
    OpenAI = None  # type: ignore


def _build_prompt(topic: str, thesis: List[str]) -> str:
    bullet_points = "\n".join(f"- {t}" for t in thesis)
    return dedent(
        f"""
        Ты — редактор Эльбрус Буткемпа. Напиши структурированную статью по теме: "{topic}".
        Требования:
        - Вступление с интригующим заходом (2-4 предложения)
        - Структура с подзаголовками h2/h3
        - Примеры кода, если уместно
        - Нейтральный тон, дружелюбная подача, минимум фломастера
        - Длина 4000–8000 символов
        - Вставки CTA добавит другой модуль — не добавляй сам
        Тезисы для ориентира:
        {bullet_points}
        Оформи заголовок h1 в первой строке.
        """
    ).strip()


def generate_article(topic: str, thesis: List[str]) -> str:
    """Генерирует текст статьи.

    Пока умолчание: локальная генерация-заглушка, но если есть OPENAI_API_KEY — можно подключить реальный вызов.
    """
    if openai_config.api_key and OpenAI is not None:
        prompt = _build_prompt(topic, thesis)
        try:
            client = OpenAI()
            completion = client.chat.completions.create(
                model=openai_config.model,
                messages=[
                    {"role": "system", "content": "Ты — редактор блога Эльбрус Буткемпа."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=1600,
            )
            content = (completion.choices[0].message.content or "").strip()
            if content and content.startswith("# "):
                return content
            # Если модель не добавила h1 — добавим сами
            return f"# {topic}\n\n{content}"
        except Exception:
            # Падать не хотим — используем мок ниже
            pass

    # Фолбэк-контент
    intro = (
        "Сегодня разберёмся в теме и покажем практические шаги. Материал подойдёт как начинающим, так и практикам."
    )
    sections = [
        ("Зачем это нужно", "Кратко объясняем ценность и пользу."),
        ("Как это работает", "Описываем архитектуру/алгоритм по шагам."),
        ("Пример кода", "```python\nprint('hello world')\n```"),
        ("Типичные ошибки", "Что часто идёт не так и как это исправить."),
        ("Итоги", "Короткая выжимка и ссылки на дальнейшие шаги."),
    ]
    body = "\n\n".join([f"## {h}\n\n{t}" for h, t in sections])
    text = f"# {topic}\n\n{intro}\n\n{body}"
    # Контроль длины: добиваем до нижней границы моком, если нужно
    min_chars = 4000
    if len(text) < min_chars:
        filler = ("\n\n" + "Дополнительно: разбор кейсов, нюансы реализации, ссылки на источники.") * (
            (min_chars - len(text)) // 80 + 1
        )
        text += filler
    return text[:8000]
