"""Модуль выбора темы для статьи."""
from datetime import datetime


def select_topic():
    """Заглушка: возвращает выбранную тему и тезисы."""
    today = datetime.now().strftime('%Y-%m-%d')
    topic = f"Пример темы на {today}"
    thesis = ["Тезис 1", "Тезис 2", "Тезис 3"]
    return topic, thesis
