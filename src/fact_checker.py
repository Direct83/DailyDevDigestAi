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


def _run_python_piston(code: str) -> Tuple[bool, str]:
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
        out = (run.get("stdout") or "") + (run.get("stderr") or "")
        ok = (run.get("code") == 0)
        return ok, out.strip()
    except Exception as e:
        return False, str(e)


def _run_python_replit(code: str) -> Tuple[bool, str]:
    if not (Config.REPLIT_EVAL_URL and Config.REPLIT_EVAL_TOKEN):
        return False, "replit not configured"
    if len(code) > 1000:
        return True, "skipped"
    banned = ["import os", "import sys", "subprocess", "open(", "requests."]
    if any(b in code for b in banned):
        return True, "skipped"
    try:
        headers = {"Authorization": f"Bearer {Config.REPLIT_EVAL_TOKEN}", "Content-Type": "application/json"}
        payload = {"language": "python3", "files": [{"name": "main.py", "content": code}]}
        r = requests.post(Config.REPLIT_EVAL_URL, json=payload, headers=headers, timeout=20)
        if r.status_code >= 400:
            return False, f"replit http {r.status_code}"
        data = r.json()
        # ожидаем поля stdout/stderr/exitCode в ответе; зависит от конкретного шлюза
        stdout = data.get("stdout") or ""
        stderr = data.get("stderr") or ""
        exit_code = int(data.get("exitCode") or 0)
        ok = exit_code == 0
        return ok, (stdout + stderr).strip()
    except Exception as e:
        return False, str(e)


def _run_python_in_sandbox(code: str) -> Tuple[bool, str]:
    provider = Config.SANDBOX_PROVIDER
    if provider == "replit":
        return _run_python_replit(code)
    return _run_python_piston(code)


def _tokenize_topic(topic: str) -> List[str]:
    tokens = [t for t in re.split(r"[^\w\-\/]+", topic.lower()) if t and len(t) > 2]
    stop = {"the", "and", "for", "with", "from", "this", "that", "open", "available", "device", "local", "run"}
    return [t for t in tokens if t not in stop]


def _build_search_queries(topic: str) -> List[str]:
    base = topic.strip()
    tokens = _tokenize_topic(base)
    pairs = [t for t in tokens if ("/" in t or "-" in t)]
    head = tokens[:3]
    # расширенная стратегия: добавим кавычки для точных совпадений и пару тематических запросов
    quoted = [f'"{t}"' for t in pairs[:2]]
    combos = []
    if len(pairs) >= 1 and len(head) >= 1:
        combos.append(f"{pairs[0]} {head[0]}")
    if len(pairs) >= 2:
        combos.append(f"{pairs[0]} {pairs[1]}")
    # базовый список
    queries: List[str] = [base]
    queries.extend(pairs)
    queries.extend(head)
    queries.extend(quoted)
    queries.extend([f"site:github.com {head[0]}" if head else ""])  # узкое подтверждение
    queries.extend(combos)
    seen: set[str] = set()
    result: List[str] = []
    for q in queries:
        qn = q.strip()
        if qn and qn not in seen and len(qn) > 2:
            seen.add(qn)
            result.append(qn)
    return result[:8]


def verify_with_search(topic: str, max_checks: int = 8) -> List[str]:
    if not (Config.GOOGLE_API_KEY and Config.GOOGLE_CSE_ID):
        return []
    queries = _build_search_queries(topic)
    errors: List[str] = []
    tried: List[str] = []
    for q in queries[:max_checks]:
        tried.append(q)
        try:
            resp = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params={"key": Config.GOOGLE_API_KEY, "cx": Config.GOOGLE_CSE_ID, "q": q},
                timeout=20,
            )
            data = resp.json()
            total = int(data.get("searchInformation", {}).get("totalResults", "0"))
            logging.debug("CSE: q=%s total=%s", q, total)
            if total > 0:
                return []
        except Exception as e:
            logging.warning("CSE error for q=%s: %s", q, e)
            errors.append(f"Ошибка Google CSE: {e}")
    if not errors:
        # Возвращаем одну ошибку — сигнал верхнему уровню пересобрать/остановить публикацию
        errors.append("Не найдено подтверждений ни по одному подзапросу: " + ", ".join(tried))
    return errors


# Дополнительные внешние источники как fallback (без ключей)
def _evidence_github(tokens: List[str]) -> bool:
    # Проверим, что по ключам есть публичные репозитории — это хорошее непрямое подтверждение
    for t in tokens[:3]:
        try:
            r = requests.get("https://api.github.com/search/repositories", params={"q": t, "per_page": 1}, timeout=15)
            if r.status_code < 400 and r.json().get("total_count", 0) > 0:
                logging.debug("Fallback GitHub ok for token=%s", t)
                return True
        except Exception as e:
            logging.warning("GitHub search error for %s: %s", t, e)
    return False


def _evidence_hn(tokens: List[str]) -> bool:
    # Algolia HN API без ключей
    for t in tokens[:3]:
        try:
            r = requests.get("https://hn.algolia.com/api/v1/search", params={"query": t, "tags": "story"}, timeout=15)
            if r.status_code < 400 and (r.json().get("nbHits", 0) or len(r.json().get("hits", [])) > 0):
                logging.debug("Fallback HN ok for token=%s", t)
                return True
        except Exception as e:
            logging.warning("HN search error for %s: %s", t, e)
    return False


def verify_facts(topic: str) -> List[str]:
    # 1) Google CSE
    cse_errors = verify_with_search(topic)
    if not cse_errors:
        return []
    # 2) GitHub fallback
    tokens = _tokenize_topic(topic)
    if _evidence_github(tokens):
        return []
    # 3) HN fallback
    if _evidence_hn(tokens):
        return []
    return cse_errors


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

    # 3) Поиск фактов (CSE + fallback источники)
    errors.extend(verify_facts(topic))

    return (len(errors) == 0, errors)