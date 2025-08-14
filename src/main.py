"""Главный модуль оркестрации пайплайна."""
from __future__ import annotations

import logging

import typer

from .analytics_reporter import send_weekly_report
from .article_generator import generate_article
from .config import Config
from .cover_generator import generate_cover_bytes
from .publisher import GhostPublisher
from .state import StateStore
from .topics_selector import select_topic
from .fact_checker import fact_check


app = typer.Typer(help="DailyDevDigestAi — публикация статей и отчёты")


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Урезаем болтливые внешние логгеры
    for noisy in ("httpx", "urllib3", "requests", "PIL", "matplotlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


@app.command()
def run_once() -> None:
    setup_logging()
    Config.ensure_dirs()
    state = StateStore()

    sel = select_topic(state)
    title: str = str(sel["title"])  # type: ignore
    tags = list(sel.get("tags", []))  # type: ignore
    outline = list(sel.get("outline", []))  # type: ignore

    logging.info("Тема: %s", title)

    html, tags = generate_article(title, outline, tags)

    # Фактчекинг: до двух попыток
    ok, errs = fact_check(html, title)
    if not ok:
        logging.warning("Фактчекинг не пройден, пересборка: %s", "; ".join(errs))
        html, tags = generate_article(title, outline, tags)
        ok2, errs2 = fact_check(html, title)
        if not ok2:
            logging.error("Фактчекинг повторно не пройден: %s", "; ".join(errs2))
            # По ТЗ: при неподтверждении факта после пересборки публикацию останавливаем
            return

    # Обложка (в памяти)
    cover_bytes = generate_cover_bytes(title)

    # Публикация (если настроен Ghost)
    try:
        publisher = GhostPublisher()
        res = publisher.publish(title=title, html=html, tags=tags, feature_image_bytes=cover_bytes, schedule_msk_11=True)
        # Краткий итог вместо полного JSON
        try:
            posts = (res or {}).get("posts", [])
            p = posts[0] if posts else {}
            logging.info(
                "Опубликовано/запланировано: id=%s title=%s status=%s url=%s",
                p.get("id"), p.get("title"), p.get("status"), (res or {}).get("url"),
            )
        except Exception:
            logging.info("Опубликовано/запланировано")
        state.add_topic(title)
    except Exception as e:
        logging.warning("Публикация пропущена: %s", e)


@app.command()
def daily() -> None:
    run_once()


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
