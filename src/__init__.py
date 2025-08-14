"""Пакет DailyDevDigestAi."""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # type: ignore

if load_dotenv is not None:
    # Автозагрузка .env из корня проекта, если есть
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    dotenv_path = os.path.join(root_dir, ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)

__all__ = []
