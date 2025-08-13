"""Модуль фактчекинга."""
from __future__ import annotations

import ast
import html
import logging
import re
from typing import List, Tuple

import requests
from bs4 import BeautifulSoup

from .config import Config


def validate_code_blocks(article_html: str) -> List[str]:
    errors: List[str] = []
    try:
        soup = BeautifulSoup(article_html, "html.parser")
        for pre in soup.find_all("pre"):
            code = pre.find("code")
            if not code:
                continue
            cls = code.get("class", [])
            code_text = code.get_text()
            if any("python" in c for c in cls):
                try:
                    ast.parse(code_text)
                except Exception as e:
                    errors.append(f"Ошибка Python-кода: {html.escape(str(e))}")
    except Exception as e:
        errors.append(f"Парсинг HTML не удался: {e}")
    return errors


def _run_python_in_sandbox(code: str) -> Tuple[bool, str]:
    """Запуск короткого Python-кода в публичной песочнице Piston API.

    Ограничим длину кода и не отправляем, если код потенциально опасен (import os, subprocess, requests, etc.).
    """
    if len(code) > 1000:
        return True, "skipped"
    banned = ["import os", "import sys", "subprocess", "open(", "requests."]
    if any(b in code for b in banned):
        return True, "skipped"
    try:
        payload = {
            "language": "python",
            "version": "3.10.0",
            "files": [{"name": "main.py", "content": code}],
            "stdin": "",
        }
        r = requests.post("https://emkc.org/api/v2/piston/execute", json=payload, timeout=20)
        if r.status_code >= 400:
            return False, f"sandbox http {r.status_code}"
        data = r.json()
        run = data.get("run", {})
        code_out = (run.get("stdout") or "") + (run.get("stderr") or "")
        ok = (run.get("code") == 0)
        return ok, code_out.strip()
    except Exception as e:
        return False, str(e)


def verify_with_search(topic: str, max_checks: int = 2) -> List[str]:
    if not (Config.GOOGLE_API_KEY and Config.GOOGLE_CSE_ID):
        return []
    queries = [topic]
    errors: List[str] = []
    for q in queries[:max_checks]:
        try:
            resp = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params={"key": Config.GOOGLE_API_KEY, "cx": Config.GOOGLE_CSE_ID, "q": q},
                timeout=20,
            )
            data = resp.json()
            total = int(data.get("searchInformation", {}).get("totalResults", "0"))
            if total <= 0:
                errors.append(f"Не найдено подтверждений по запросу: {q}")
        except Exception as e:
            errors.append(f"Ошибка Google CSE: {e}")
    return errors


def fact_check(article_html: str, topic: str) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    # 1) Синтаксис Python
    errors.extend(validate_code_blocks(article_html))

    # 2) Выполним отдельные короткие сниппеты в песочнице
    try:
        soup = BeautifulSoup(article_html, "html.parser")
        executed = 0
        for pre in soup.find_all("pre"):
            if executed >= 2:
                break
            code = pre.find("code")
            if not code:
                continue
            cls = code.get("class", [])
            code_text = code.get_text()
            if any("python" in c for c in cls):
                ok, out = _run_python_in_sandbox(code_text)
                if not ok:
                    errors.append(f"Сниппет не исполнился в песочнице: {html.escape(out)}")
                executed += 1
    except Exception:
        pass

    # 3) Поиск
    errors.extend(verify_with_search(topic))

    return (len(errors) == 0, errors)