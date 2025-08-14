"""Главный модуль оркестрации пайплайна."""

from __future__ import annotations

import logging

import typer

from .agent.graph import AgentContext, run_publication_once
from .analytics_reporter import send_weekly_report
from .config import Config

app = typer.Typer(help="DailyDevDigestAi — публикация статей и отчёты")


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Урезаем болтливые внешние логгеры
    for noisy in ("httpx", "urllib3", "requests", "PIL", "matplotlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


@app.command()
def run_once() -> None:
    """Совместимая команда: один прогон публикации через граф‑агента."""
    setup_logging()
    Config.ensure_dirs()
    ctx = run_publication_once(AgentContext())
    try:
        posts = (ctx.publish_result or {}).get("posts", [])
        p = posts[0] if posts else {}
        logging.info(
            "Опубликовано/запланировано: id=%s title=%s status=%s feature_image=%s",
            p.get("id"),
            p.get("title"),
            p.get("status"),
            p.get("feature_image"),
        )
    except Exception:
        pass


@app.command()
def daily() -> None:
    # совместимость: daily выполняет один прогон через граф‑агента
    setup_logging()
    Config.ensure_dirs()
    ctx = run_publication_once(AgentContext())
    # компактный вывод результата, если публиковалось
    try:
        posts = (ctx.publish_result or {}).get("posts", [])
        p = posts[0] if posts else {}
        logging.info(
            "Опубликовано/запланировано: id=%s title=%s status=%s feature_image=%s",
            p.get("id"),
            p.get("title"),
            p.get("status"),
            p.get("feature_image"),
        )
    except Exception:
        pass


@app.command()
def weekly() -> None:
    setup_logging()
    try:
        status = send_weekly_report()
        logging.info("Еженедельный отчёт: %s", status or "пропущен (не настроен SMTP/Ghost)")
    except Exception as e:
        logging.error("Ошибка отправки отчёта: %s", e)


if __name__ == "__main__":
    app()
