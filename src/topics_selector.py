"""Модуль выбора темы для статьи."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import feedparser
import requests

from .config import Config
from .domain.dedup import quick_duplicate_heuristic
from .llm_dedupe import llm_is_duplicate
from .state import StateStore


@dataclass
class TopicCandidate:
    title: str
    source: str
    score: float
    published_at: datetime


KEYWORDS = [
    "AI",
    "нейросети",
    "машинное обучение",
    "data science",
    "веб",
    "frontend",
    "backend",
    "Python",
    "JavaScript",
    "LLM",
]

REDDIT_FEEDS = [
    "https://www.reddit.com/r/MachineLearning/.rss",
    "https://www.reddit.com/r/datascience/.rss",
    "https://www.reddit.com/r/webdev/.rss",
]

# Токены, указывающие на обучающий характер запроса (how-to/гайд)
HOWTO_HINTS = [
    "how to",
    "tutorial",
    "guide",
    "step-by-step",
    "как ",  # пробел важен, чтобы не ловить "какой"
    "гайд",
    "пошаг",
    "инструкция",
]


def fetch_hn(limit: int = 50) -> list[TopicCandidate]:
    """Возвращает кандидатов из Hacker News (top stories) с ключевыми словами."""
    try:
        ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=15).json()
    except Exception:
        return []
    result: list[TopicCandidate] = []
    for sid in ids[:limit]:
        try:
            item = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=10).json()
            title = item.get("title", "")
            ts = item.get("time", int(time.time()))
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            score = float(item.get("score", 1))
            if any(k.lower() in title.lower() for k in KEYWORDS):
                result.append(TopicCandidate(title=title, source="HN", score=score, published_at=dt))
        except Exception:
            continue
    return result


def fetch_reddit() -> list[TopicCandidate]:
    """Возвращает кандидатов из Reddit по заранее заданным фидам."""
    result: list[TopicCandidate] = []
    for url in REDDIT_FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                title = e.get("title", "")
                published = e.get("published_parsed")
                dt = (
                    datetime.fromtimestamp(time.mktime(published), tz=timezone.utc)
                    if published
                    else datetime.now(timezone.utc)
                )
                if any(k.lower() in title.lower() for k in KEYWORDS):
                    result.append(TopicCandidate(title=title, source="Reddit", score=1.0, published_at=dt))
        except Exception:
            continue
    return result


def fetch_google_trends() -> list[TopicCandidate]:
    """Возвращает трендовые запросы Google Trends (Россия)."""
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="ru-RU", tz=180)
        df = pytrends.trending_searches(pn="russia")
        now = datetime.now(timezone.utc)
        cands: list[TopicCandidate] = []
        for idx, row in df.head(20).iterrows():
            title = str(row[0])
            if any(k.lower() in title.lower() for k in KEYWORDS):
                cands.append(TopicCandidate(title=title, source="Trends", score=1.5, published_at=now))
        return cands
    except Exception:
        return []


def fetch_telegram_rss() -> list[TopicCandidate]:
    """Возвращает кандидатов из пользовательских RSS (например, Telegram‑прокси)."""
    feeds = (Config.TELEGRAM_RSS_FEEDS or "").split(",")
    feeds = [f.strip() for f in feeds if f.strip()]
    if not feeds:
        return []
    result: list[TopicCandidate] = []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:20]:
                title = e.get("title") or e.get("summary") or ""
                if not title:
                    continue
                dt = datetime.now(timezone.utc)
                if any(k.lower() in title.lower() for k in KEYWORDS):
                    result.append(TopicCandidate(title=title, source="TG", score=1.2, published_at=dt))
        except Exception:
            continue
    return result


def select_topic(state: StateStore | None = None) -> dict[str, object]:
    """Собирает кандидатов из источников, применяет антидубли и выбирает лучшего."""
    state = state or StateStore()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    candidates: list[TopicCandidate] = []
    candidates.extend(fetch_hn())
    candidates.extend(fetch_reddit())
    candidates.extend(fetch_google_trends())
    candidates.extend(fetch_telegram_rss())

    # 48 часов окно
    candidates = [c for c in candidates if c.published_at >= cutoff]

    # LLM‑антидубли по смыслу относительно истории Ghost (20 дней)
    recent_titles = state.get_recent_titles()
    # Если Ghost настроен, но заголовки не получены — прерываем выбор темы (во избежание дублей)
    if Config.GHOST_ADMIN_API_URL and not recent_titles:
        raise RuntimeError("Недоступен список последних заголовков из Ghost — выбор темы остановлен")
    filtered: list[TopicCandidate] = []
    for c in candidates:
        decision = llm_is_duplicate(c.title, recent_titles)
        if decision is True:
            continue
        if decision is None and quick_duplicate_heuristic(c.title, recent_titles):
            # LLM недоступен — применим ручную эвристику: ≥7 слов и 1 длинное слово совпало
            continue
        filtered.append(c)
    candidates = filtered

    # Буст обучающих формулировок (how-to/гайд) перед сортировкой
    def _boost_score(c: TopicCandidate) -> float:
        title_lc = c.title.lower()
        boost = 0.0
        if any(h in title_lc for h in HOWTO_HINTS):
            boost += 0.8
        return c.score + boost

    # сортировка
    candidates.sort(key=_boost_score, reverse=True)

    if not candidates:
        # fallback — базовая тема
        title = "Как начать проект с GPT-4o: от идеи до продакшна"
        return {
            "title": title,
            "tags": ["AI", "LLM", "OpenAI"],
            "outline": [
                "Почему сейчас самое время стартовать",
                "Архитектура агента и пайплайна",
                "Фактчекинг и безопасность",
                "Публикация и аналитика",
            ],
            "source": "fallback",
        }

    best = candidates[0]
    tags = ["AI"] if "ai" in best.title.lower() else []
    if any(w in best.title.lower() for w in ["python", "django", "fastapi"]):
        tags.append("Python")
    if any(w in best.title.lower() for w in ["javascript", "react", "next"]):
        tags.append("WebDev")

    outline = build_outline(best.title)
    return {"title": best.title, "tags": tags or ["Tech"], "outline": outline, "source": best.source}


def build_outline(title: str) -> list[str]:
    """Строит минимальный план статьи по заголовку (эвристика)."""
    return [
        f"Контекст и зачем сейчас: {title}",
        "Быстрый разбор основных понятий",
        "Пошаговый туториал с примерами кода",
        "Типичные ошибки и best practices",
        "Что почитать дальше и как прокачаться",
    ]
