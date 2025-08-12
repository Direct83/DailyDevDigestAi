"""Модуль генерации статьи."""


def generate_article(topic: str, thesis: list[str]) -> str:
    """Генерирует текст статьи на основе темы и тезисов.

    Здесь должна вызываться модель GPT для создания текста.
    """
    body = "\n".join(f"- {t}" for t in thesis)
    article = f"# {topic}\n\n{body}\n\n(Здесь будет текст статьи)"
    return article
