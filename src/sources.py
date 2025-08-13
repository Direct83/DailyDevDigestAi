"""Источники тем: Hacker News (Algolia API), GitHub Trending, Reddit, RSS.

Без ключей: используется публичный поиск Algolia HN API.
"""
from __future__ import annotations

import time
from typing import List

import requests
from xml.etree import ElementTree

from .config import sources_config

try:
    from pytrends.request import TrendReq  # type: ignore
except Exception:
    TrendReq = None  # type: ignore


def _hn_recent_stories(query: str, hours: int = 48, hits_per_page: int = 20) -> List[str]:
    now = int(time.time())
    cutoff = now - hours * 3600
    url = (
        f"https://hn.algolia.com/api/v1/search?query={requests.utils.quote(query)}&tags=story"
        f"&numericFilters=created_at_i>{cutoff}&hitsPerPage={hits_per_page}"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        titles = []
        for hit in data.get("hits", [])[:hits_per_page]:
            title = (hit.get("title") or "").strip()
            if title:
                titles.append(title)
        return titles
    except Exception:
        return []


def fetch_candidate_topics() -> List[str]:
    """Возвращает список кандидатов по темам AI/Web/Data за последние 48 часов."""
    queries = ["AI", "machine learning", "web development", "data science", "react", "python"]
    candidates: list[str] = []

    # Hacker News
    for q in queries:
        candidates.extend(_hn_recent_stories(q, hours=48, hits_per_page=10))

    # GitHub Trending (неофициальный парсинг)
    try:
        gh = requests.get("https://ghapi.huchen.dev/repositories", timeout=10)
        if gh.ok:
            for item in gh.json()[:20]:
                name = item.get("name")
                desc = item.get("description") or ""
                lang = item.get("language") or ""
                if any(l.strip().lower() in (lang or "").lower() for l in sources_config.github_language_filter.split(",")):
                    title = f"GitHub Trending: {name} — {desc}".strip()
                    candidates.append(title)
    except Exception:
        pass

    # Reddit (без ключей ограниченно: публичная JSON-лента)
    for sub in sources_config.reddit_subs:
        try:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=15"
            resp = requests.get(url, headers={"User-Agent": "DailyDevDigest/1.0"}, timeout=10)
            if resp.ok:
                data = resp.json()
                for child in data.get("data", {}).get("children", [])[:15]:
                    t = (child.get("data", {}).get("title") or "").strip()
                    if t:
                        candidates.append(f"r/{sub}: {t}")
        except Exception:
            continue

    # RSS
    for feed in sources_config.rss_feeds:
        try:
            r = requests.get(feed, timeout=10)
            if not r.ok:
                continue
            root = ElementTree.fromstring(r.content)
            for item in root.iterfind(".//item"):
                title_node = item.find("title")
                if title_node is not None and title_node.text:
                    candidates.append(title_node.text.strip())
        except Exception:
            continue

    # Уберём дубликаты, сохранив порядок
    seen: set[str] = set()
    unique: list[str] = []
    for t in candidates:
        if t not in seen:
            seen.add(t)
            unique.append(t)

    # Google Trends (опционально)
    if TrendReq is not None:
        try:
            pytrends = TrendReq(hl="ru-RU", tz=180)
            kws = ["как", "how to", "обучить", "настроить", "установить", "пример"]
            pytrends.build_payload(kws, timeframe="now 7-d", geo=sources_config.google_trends_geo)
            related = pytrends.related_queries()
            for kw in kws:
                data = related.get(kw, {})
                for key in ("top", "rising"):
                    df = data.get(key)
                    if df is not None:
                        for row in df.head(10).to_dict("records"):
                            q = (row.get("query") or "").strip()
                            if q and q not in seen:
                                seen.add(q)
                                unique.append(q)
        except Exception:
            pass

    # Приоритизируем «обучающие» запросы в выдаче
    def _score(title: str) -> int:
        t = title.lower()
        score = 0
        for token in ["how to", "как ", "как-", "обучить", "настроить", "установить", "пример", "tutorial", "guide"]:
            if token in t:
                score += 1
        return score

    unique.sort(key=_score, reverse=True)

    return unique[:100]


