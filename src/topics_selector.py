"""Модуль выбора темы для статьи."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import feedparser
import requests

from .config import Config
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


def fetch_hn(limit: int = 50) -> list[TopicCandidate]:
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


def fetch_github_trending() -> list[TopicCandidate]:
    """Скрейп GitHub Trending за сегодня.

    Используем HTML-страницу Trending, выбираем репозитории с релевантными ключевыми словами в названии/описании.
    """
    url = "https://github.com/trending?since=daily"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; DDD-AI/1.0)"}
    try:
        from bs4 import BeautifulSoup

        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("article.Box-row")
        now = datetime.now(timezone.utc)
        result: list[TopicCandidate] = []
        for it in items[:25]:
            full_name_el = it.select_one("h2 a")
            desc_el = it.select_one("p")
            if not full_name_el:
                continue
            name = " ".join(full_name_el.get_text(strip=True).split())  # "owner / repo"
            desc = desc_el.get_text(strip=True) if desc_el else ""
            title = f"{name}: {desc}" if desc else name
            if any(k.lower() in title.lower() for k in KEYWORDS):
                # эвристический скор
                stars_el = it.select_one("a.Link--muted[href$='/stargazers']")
                try:
                    stars_text = stars_el.get_text(strip=True).replace(",", "") if stars_el else "0"
                    score = float(stars_text) if stars_text.isdigit() else 1.0
                except Exception:
                    score = 1.0
                result.append(TopicCandidate(title=title, source="GitHub", score=score, published_at=now))
        return result
    except Exception:
        return []


def fetch_telegram_rss() -> list[TopicCandidate]:
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
    state = state or StateStore()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    candidates: list[TopicCandidate] = []
    candidates.extend(fetch_hn())
    candidates.extend(fetch_reddit())
    candidates.extend(fetch_google_trends())
    candidates.extend(fetch_github_trending())
    candidates.extend(fetch_telegram_rss())

    # 48 часов окно
    candidates = [c for c in candidates if c.published_at >= cutoff]

    # Антидубли по истории Ghost (20 дней):
    # считаем частоты токенов и блокируем якоря len>=7, встречавшиеся в истории ≥1 раз.
    recent_titles = state.get_recent_titles()
    from .state import StateStore as _SS

    # Применяем фильтр по якорям всегда
    freq: dict[str, int] = {}
    for t in recent_titles:
        for tok in _SS._tokens(t):
            if len(tok) >= 7:
                freq[tok] = freq.get(tok, 0) + 1
    banned_anchors = {t for t, n in freq.items() if n >= 1}
    if banned_anchors:

        def _anchors(text: str) -> set[str]:
            return {t for t in _SS._tokens(text) if len(t) >= 7}

        filtered: list[TopicCandidate] = []
        for c in candidates:
            if _anchors(c.title) & banned_anchors:
                continue
            filtered.append(c)
        candidates = filtered

    # антидубль 20 дней (дополнительная страховка)
    candidates = [c for c in candidates if not state.is_recent_topic(c.title)]

    # сортировка
    candidates.sort(key=lambda c: c.score, reverse=True)

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
    # Простая эвристика для тезисов
    return [
        f"Контекст и зачем сейчас: {title}",
        "Быстрый разбор основных понятий",
        "Пошаговый туториал с примерами кода",
        "Типичные ошибки и best practices",
        "Что почитать дальше и как прокачаться",
    ]
