"""Модуль генерации статьи."""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from .config import Config
from .cta_inserter import CTAProvider


def _openai_client():
    if not Config.OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI

        return OpenAI(api_key=Config.OPENAI_API_KEY)
    except Exception:
        return None


def _adjust_length_with_model(client, html: str) -> str:
    length = len(html)
    if 4000 <= length <= 8000:
        return html
    try:
        target = 6000
        prompt = (
            "Отредактируй ниже HTML-статью так, чтобы её длина была в диапазоне 4000–8000 символов (целевой размер ~6000), "
            "сохранив структуру, язык и смысл. Нельзя использовать Markdown, только HTML. Верни только HTML.\n\n"
            f"---\n{html}\n---"
        )
        resp = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=[{"role": "system", "content": "Ты редактор, который аккуратно изменяет длину текста и сохраняет структуру."}, {"role": "user", "content": prompt}],
            temperature=0.4,
        )
        new_html = resp.choices[0].message.content or html
        return new_html
    except Exception:
        return html


def generate_article(topic: str, outline: List[str], tags: List[str]) -> Tuple[str, List[str]]:
    client = _openai_client()
    ctas = CTAProvider()
    pair = ctas.pick_pair()

    if client:
        system = (
            "Ты технический редактор блога буткемпа по IT. Пиши по-русски, живым стилем. "
            "Структура: интригующее вступление, разделы h2/h3, примеры кода где уместно. "
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

    # Вставка CTA
    if pair:
        blocks = [CTAProvider.render_cta_html(p) for p in pair]
        for block in blocks:
            if "<!--CTA_SLOT-->" in html:
                html = html.replace("<!--CTA_SLOT-->", block, 1)
        # если слотов нет — добавим в конец
        if "<!--CTA_SLOT-->" not in html:
            html += "\n" + "\n".join(blocks)

    return html, tags


def _fallback_html(topic: str, outline: List[str]) -> str:
    items = "".join(f"<li>{p}</li>" for p in outline)
    return (
        f"<h2>{topic}</h2>"
        f"<p>Короткое вступление: почему тема важна именно сейчас.</p>"
        f"<h3>План</h3><ul>{items}</ul>"
        f"<h3>Пример кода</h3><pre><code class=\"language-python\">print('Hello, AI')</code></pre>"
        f"<!--CTA_SLOT-->"
    )
