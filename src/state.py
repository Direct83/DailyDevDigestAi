"""Хранилище состояния: предотвращение повторов тем в течение N дней."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from .config import paths_config


def _ensure_data_dir() -> None:
    data_dir = os.path.abspath(os.path.join(paths_config.data_dir))
    os.makedirs(data_dir, exist_ok=True)


def _load_state() -> dict:
    _ensure_data_dir()
    path = os.path.abspath(paths_config.state_file)
    if not os.path.exists(path):
        return {"recent_topics": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"recent_topics": []}


def _save_state(state: dict) -> None:
    _ensure_data_dir()
    path = os.path.abspath(paths_config.state_file)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_recent_topics(days: int = 20) -> set[str]:
    state = _load_state()
    result: set[str] = set()
    cutoff = datetime.utcnow() - timedelta(days=days)
    for item in state.get("recent_topics", []):
        try:
            ts = datetime.fromisoformat(item.get("ts"))
            if ts >= cutoff:
                result.add(item.get("topic", ""))
        except Exception:
            continue
    return result


def record_topic(topic: str) -> None:
    state = _load_state()
    items = state.get("recent_topics", [])
    items.append({"topic": topic, "ts": datetime.utcnow().isoformat()})
    # Обрезаем историю до последних 200 записей, чтобы файл не рос бесконечно
    items = items[-200:]
    state["recent_topics"] = items
    _save_state(state)


