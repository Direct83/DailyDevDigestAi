"""Модуль генерации статьи."""

from __future__ import annotations

import logging

from .config import Config


def _openai_client():
    """Возвращает OpenAI client или None, если ключ/SDK недоступны."""
    if not Config.OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI

        return OpenAI(api_key=Config.OPENAI_API_KEY)
    except Exception:
        return None


def generate_russian_title(topic: str) -> str:
    """Генерирует краткий русский заголовок на основе темы.

    Требования: 60–90 символов, без кавычек, без эмодзи.
    При отсутствии клиента — возвращает исходную тему, подрезанную до 100 символов.
    """
    client = _openai_client()
    base = (topic or "").strip()
    if not client:
        return (base[:100]).rstrip()
    try:
        prompt = (
            "Сформулируй один короткий заголовок на РУССКОМ по теме ниже. "
            "60–90 символов. Без кавычек и эмодзи. Верни только заголовок.\n\n" + base
        )
        resp = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Ты редактор заголовков техноблога."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
        )
        title = (resp.choices[0].message.content or base).strip()
        # защита от слишком длинного
        if len(title) > 100:
            title = title[:100].rstrip(" -:,.!")
        return title
    except Exception:
        return (base[:100]).rstrip()


def _adjust_length_with_model(client, html: str) -> str:
    """Подгоняет длину HTML статьи к диапазону 4–8 тис. символов с помощью LLM.

    Если вызов не удался — возвращает исходный HTML без изменений.
    """
    length = len(html)
    if 4000 <= length <= 8000:
        return html
    try:
        # целевой размер ~6000, используется только в описании промпта
        prompt = (
            "Отредактируй ниже HTML-статью так, чтобы её длина была в диапазоне 4000–8000 символов (целевой размер ~6000), "
            "сохранив структуру, язык и смысл. Нельзя использовать Markdown, только HTML. Верни только HTML.\n\n"
            f"---\n{html}\n---"
        )
        resp = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Ты редактор, который аккуратно изменяет длину текста и сохраняет структуру.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )
        return resp.choices[0].message.content or html
    except Exception:
        return html


def generate_article(topic: str, outline: list[str], tags: list[str]) -> tuple[str, list[str]]:
    """Генерирует HTML статьи и итоговые теги по теме и тезисам.

    Возвращает кортеж: (html, tags). При недоступности LLM использует простой
    локальный шаблон через `_fallback_html`.
    """
    client = _openai_client()

    if client:
        system = (
            "Ты технический редактор блога буткемпа по IT. Пиши по-русски, живым стилем. "
            "Структура: интригующее вступление, разделы h2/h3, примеры кода где уместно. "
            "Примеры кода должны быть исполняемыми и использовать только стандартную библиотеку Python (без сторонних пакетов). "
            "Длина 4000–8000 символов. Используй HTML (h2/h3/p/pre/code/ul/ol/li). Без Markdown."
        )
        outline_html = "".join(f"<li>{p}</li>" for p in outline)
        user = (
            f"Тема: {topic}. Теги: {', '.join(tags)}.\n"
            f"Сделай структуру по тезисам: <ul>{outline_html}</ul>\n"
            f"Вставь места для CTA в двух местах как комментарии <!--CTA_SLOT-->."
        )
        try:
            resp = client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.7,
            )
            html = resp.choices[0].message.content or ""
            # Коррекция длины при необходимости
            html = _adjust_length_with_model(client, html)
        except Exception as e:
            logging.warning("OpenAI не ответил: %s", e)
            html = _fallback_html(topic, outline)
    else:
        html = _fallback_html(topic, outline)

    return html, tags


def _fallback_html(topic: str, outline: list[str]) -> str:
    """Простейший HTML-шаблон статьи на случай недоступности LLM."""
    items = "".join(f"<li>{p}</li>" for p in outline)
    return (
        f"<h2>{topic}</h2>"
        f"<p>Короткое вступление: почему тема важна именно сейчас.</p>"
        f"<h3>План</h3><ul>{items}</ul>"
        f"<h3>Пример кода</h3><pre><code class=\"language-python\">print('Hello, AI')</code></pre>"
        f"<!--CTA_SLOT-->"
    )
