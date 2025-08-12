"""Главный модуль оркестрации пайплайна."""
from __future__ import annotations

import argparse
from datetime import datetime

from .topics_selector import select_topic
from .article_generator import generate_article
from .fact_checker import validate_article
from .cover_generator import generate_cover
from .cta_inserter import insert_cta
from .publisher import publish
from .analytics_reporter import collect_weekly_report
from .config import time_config


def run_daily_pipeline() -> None:
    """Запускает ежедневный цикл публикации."""
    topic, thesis = select_topic()
    article = generate_article(topic, thesis)
    if not validate_article(article):
        raise ValueError("Статья не прошла проверку")
    article = insert_cta(article)
    cover = generate_cover(topic)
    publish_time = (
        datetime.now().replace(hour=time_config.daily_publish_hour, minute=0, second=0, microsecond=0)
    )
    publish(article, cover, publish_time)


def run_weekly_report() -> None:
    """Собирает и отправляет еженедельный отчёт."""
    report = collect_weekly_report()
    print("Неделя закрыта. Отчёт:", report)


def main() -> None:
    parser = argparse.ArgumentParser(description="DailyDevDigest AI агент")
    parser.add_argument("command", choices=["run-once", "daily", "weekly"], help="Что запустить")
    args = parser.parse_args()

    if args.command == "run-once":
        run_daily_pipeline()
    elif args.command == "daily":
        run_daily_pipeline()
    elif args.command == "weekly":
        run_weekly_report()


if __name__ == "__main__":
    main()
