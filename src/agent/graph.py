"""Минимальный каркас агента (стейт‑машина без внешних зависимостей).

Выполняет один прогон публикации:
- SelectTopic → Generate → FactCheck (retry=1) → Cover → Publish (retry=3)

Каркас узлов упрощённый, без сторонних библиотек: каждый узел мутирует контекст
и возвращает признак продолжения графа. В случае неуспеха граф останавливается.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from ..article_generator import generate_article, generate_russian_title
from ..cover_generator import generate_cover_bytes
from ..fact_checker import fact_check
from ..publisher import GhostPublisher
from ..state import StateStore
from ..topics_selector import select_topic
from .cta_node import insert_cta


@dataclass
class AgentContext:
    """Контекст одного прогона агента.

    Хранит промежуточные данные между узлами графа: выбранная тема, сгенерированные
    теги/тезисы/HTML, сгенерированная обложка, результат публикации и накопленные
    ошибки (например, из фактчекинга).
    """

    state: StateStore = field(default_factory=StateStore)
    raw_title: str | None = None
    title: str | None = None
    outline: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    html: str | None = None
    cover_bytes: bytes | None = None
    publish_result: dict | None = None
    errors: list[str] = field(default_factory=list)

    # Параметры поведения (можно вынести в отдельный конфиг при необходимости)
    retry_publish: int = 3
    retry_delay_sec: float = 2.0


def _timed(step: str, fn: Callable[[], None], *, extra: dict | None = None) -> None:
    """Измеряет время шага и логирует длительность."""
    t0 = time.perf_counter()
    try:
        fn()
    except Exception as e:
        logging.exception("%s failed: %s", step, e)
        raise
    else:
        dt = (time.perf_counter() - t0) * 1000.0
        logging.info("%s: %.0f ms", step, dt)


def _run_with_retries(action: Callable[[], None], retries: int, delay_sec: float, step: str) -> bool:
    """Запускает действие с повторами; возвращает True при успехе.

    Любое исключение записывается в лог и список ошибок контекста должно
    обрабатываться внутри вызывающей функции (мы здесь лишь повторяем вызов).
    """
    attempt = 0
    while True:
        try:
            _timed(step, action)
            return True
        except Exception as e:
            attempt += 1
            logging.warning("%s failed (attempt %d/%d): %s", step, attempt, retries, e)
            if attempt >= retries:
                return False
            time.sleep(delay_sec)


def run_publication_once(ctx: AgentContext | None = None) -> AgentContext:
    """Выполняет полный цикл публикации и возвращает заполненный контекст.

    - Выбирает уникальную тему (с учётом антидублей за 20 дней)
    - Генерирует статью и при необходимости один раз пересобирает при провале фактчекинга
    - Генерирует обложку в памяти
    - Публикует пост в Ghost (или пропускает, если Ghost не настроен)
    """
    context = ctx or AgentContext()

    # 1) Выбор темы
    def _select() -> None:
        sel = select_topic(context.state)
        context.raw_title = str(sel.get("title", ""))
        context.title = generate_russian_title(context.raw_title or "")
        context.tags = list(sel.get("tags", []))
        context.outline = list(sel.get("outline", []))

    _timed("SelectTopic", _select, extra={"raw": context.raw_title})

    # 2) Генерация текста
    def _generate() -> None:
        html, tags = generate_article(context.title or "", context.outline, context.tags)
        context.html, context.tags = html, tags

    _timed("GenerateArticle", _generate)

    # 3) Фактчекинг с одной пересборкой
    def _factcheck_once() -> bool:
        ok, errs = fact_check(context.html or "", context.title or "")
        if not ok:
            context.errors.extend(errs)
        return ok

    ok = False
    _timed("FactCheck#1", lambda: None)
    ok = _factcheck_once()
    if not ok:
        # Пересборка
        def _regenerate() -> None:
            html2, tags2 = generate_article(context.title or "", context.outline, context.tags)
            context.html, context.tags = html2, tags2

        _timed("RegenerateAfterFactCheckFail", _regenerate)

        _timed("FactCheck#2", lambda: None)
        ok = _factcheck_once()
        if not ok:
            # Останавливаемся без публикации
            return context

    # 4) Обложка
    def _cover() -> None:
        context.cover_bytes = generate_cover_bytes(context.title or "")

    _timed("GenerateCover", _cover)

    # 4.1) Вставка CTA
    def _cta() -> None:
        if context.html:
            context.html, _ = insert_cta(context.html)

    _timed("InsertCTA", _cta)

    # 5) Публикация (если настроен Ghost) с повторами
    try:
        publisher = GhostPublisher()
    except Exception:
        # Ghost не настроен — выходим без публикации
        return context

    def _publish() -> None:
        context.publish_result = publisher.publish(
            title=context.title or "",
            html=context.html or "",
            tags=context.tags,
            feature_image_bytes=context.cover_bytes,
            schedule_msk_11=True,
        )

    published = _run_with_retries(
        _publish,
        retries=context.retry_publish,
        delay_sec=context.retry_delay_sec,
        step="Publish",
    )
    if not published:
        return context

    context.state.add_topic(context.title or "")
    return context
