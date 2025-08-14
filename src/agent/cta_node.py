"""Узел графа: вставка CTA в HTML статьи.

Выбирает 1–2 CTA из провайдера и добавляет их в конец статьи. Если CTA нет,
ничего не делает. Узел изолирован, чтобы провайдер можно было легко заменить.
"""

from __future__ import annotations

from ..cta_inserter import CTAProvider


def insert_cta(html: str) -> tuple[str, int]:
    """Возвращает HTML с добавленными CTA и количество вставленных блоков."""
    provider = CTAProvider()
    picks = provider.pick_pair()
    if not picks:
        return html, 0
    blocks = [provider.render_cta_html(c) for c in picks]
    enhanced = html + "\n\n" + "\n".join(blocks)
    return enhanced, len(blocks)
