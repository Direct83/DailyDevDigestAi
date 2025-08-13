"""Модуль выбора темы для статьи."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import feedparser
import requests

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


def fetch_hn(limit: int = 50) -> List[TopicCandidate]:
    try:
        ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=15).json()
    except Exception:
        return []
    result: List[TopicCandidate] = []
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


def fetch_reddit() -> List[TopicCandidate]:
    result: List[TopicCandidate] = []
    for url in REDDIT_FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                title = e.get("title", "")
                published = e.get("published_parsed")
                dt = datetime.fromtimestamp(time.mktime(published), tz=timezone.utc) if published else datetime.now(timezone.utc)
                if any(k.lower() in title.lower() for k in KEYWORDS):
                    result.append(TopicCandidate(title=title, source="Reddit", score=1.0, published_at=dt))
        except Exception:
            continue
    return result


def fetch_google_trends() -> List[TopicCandidate]:
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="ru-RU", tz=180)
        df = pytrends.trending_searches(pn="russia")
        now = datetime.now(timezone.utc)
        cands: List[TopicCandidate] = []
        for idx, row in df.head(20).iterrows():
            title = str(row[0])
            if any(k.lower() in title.lower() for k in KEYWORDS):
                cands.append(TopicCandidate(title=title, source="Trends", score=1.5, published_at=now))
        return cands
    except Exception:
        return []


def fetch_github_trending() -> List[TopicCandidate]:
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
        result: List[TopicCandidate] = []
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


def select_topic(state: Optional[StateStore] = None) -> Dict[str, object]:
    state = state or StateStore()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    candidates: List[TopicCandidate] = []
    candidates.extend(fetch_hn())
    candidates.extend(fetch_reddit())
    candidates.extend(fetch_google_trends())
    candidates.extend(fetch_github_trending())

    # 48 часов окно
    candidates = [c for c in candidates if c.published_at >= cutoff]

    # антидубль 20 дней
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


def build_outline(title: str) -> List[str]:
    # Простая эвристика для тезисов
    return [
        f"Контекст и зачем сейчас: {title}",
        "Быстрый разбор основных понятий",
        "Пошаговый туториал с примерами кода",
        "Типичные ошибки и best practices",
        "Что почитать дальше и как прокачаться",
    ]
