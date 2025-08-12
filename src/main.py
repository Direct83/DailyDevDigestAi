"""Главный модуль оркестрации пайплайна."""
from datetime import datetime, timedelta

from topics_selector import select_topic
from article_generator import generate_article
from fact_checker import validate_article
from cover_generator import generate_cover
from cta_inserter import insert_cta
from publisher import publish
from analytics_reporter import collect_weekly_report


def run_daily_pipeline():
    """Запускает ежедневный цикл публикации."""
    topic, thesis = select_topic()
    article = generate_article(topic, thesis)
    if not validate_article(article):
        raise ValueError("Статья не прошла проверку")
    article = insert_cta(article)
    cover = generate_cover(topic)
    publish_time = datetime.now().replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=0)
    publish(article, cover, publish_time)


def run_weekly_report():
    """Собирает и отправляет еженедельный отчёт."""
    report = collect_weekly_report()
    print("Неделя закрыта. Отчёт:", report)


if __name__ == "__main__":
    run_daily_pipeline()
