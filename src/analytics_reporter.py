"""Модуль сборки и отправки аналитики."""


def collect_weekly_report() -> dict:
    """Собирает статистику за неделю."""
    # TODO: интеграция с Ghost API, GA4 и другими источниками
    return {
        "publications": 0,
        "total_views": 0,
        "top_article": "",
        "top_read_article": "",
        "cta_ctr": 0.0,
    }
