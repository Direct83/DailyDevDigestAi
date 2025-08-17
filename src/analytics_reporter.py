"""Модуль сборки и отправки аналитики."""

from __future__ import annotations

import io
import logging
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .config import Config
from .ghost_utils import fetch_posts


def _ghost_posts_summary(days: int = 7) -> dict[str, object]:
    """Возвращает отдельные списки опубликованных за N дней, запланированных и черновиков.

    Структура:
    {
        "count_published": int,
        "count_scheduled": int,
        "count_draft": int,
        "published": [(title, iso_datetime)],
        "scheduled": [(title, iso_datetime)],
        "drafts": [(title, iso_datetime_updated)],
        "slugs": [slug, ...],  # только для опубликованных (для GA)
    }
    """
    if not Config.GHOST_ADMIN_API_URL:
        return {
            "count_published": 0,
            "count_scheduled": 0,
            "count_draft": 0,
            "published": [],
            "scheduled": [],
            "drafts": [],
            "slugs": [],
        }
    base = Config.GHOST_ADMIN_API_URL.rstrip("/") + "/ghost/api/admin"
    since_dt = datetime.now(timezone.utc) - timedelta(days=days)
    # Ghost NQL дружелюбнее к формату "YYYY-MM-DD HH:MM:SS" без микросекунд/таймзоны
    since = since_dt.strftime("%Y-%m-%d %H:%M:%S")
    logging.info("Ghost summary: base=%s since(utc)=%s", base, since)
    try:
        # Опубликованные за период
        data_pub = fetch_posts(
            filter=f"status:published+published_at:>'{since}'",
            fields="title,slug,published_at,status",
            order="published_at desc",
            limit=100,
        )
        logging.info("Published: count=%d", len(data_pub))
        published = [(p.get("title"), p.get("published_at")) for p in data_pub if p.get("status") == "published"]
        slugs = [p.get("slug") for p in data_pub]

        # Запланированные
        data_sch = fetch_posts(
            filter="status:scheduled",
            fields="title,published_at,status",
            order="published_at asc",
            limit=100,
        )
        logging.info("Scheduled: count=%d", len(data_sch))
        scheduled = [(p.get("title"), p.get("published_at")) for p in data_sch if p.get("status") == "scheduled"]

        # Черновики (последние обновлённые)
        data_draft = fetch_posts(
            filter="status:draft",
            fields="title,updated_at,status",
            order="updated_at desc",
            limit=100,
        )
        logging.info("Drafts: count=%d", len(data_draft))
        drafts = [(p.get("title"), p.get("updated_at")) for p in data_draft if p.get("status") == "draft"]

        return {
            "count_published": len(published),
            "count_scheduled": len(scheduled),
            "count_draft": len(drafts),
            "published": published,
            "scheduled": scheduled,
            "drafts": drafts,
            "slugs": slugs,
        }
    except Exception as e:
        logging.error("Ghost summary error: %s", e)
        return {
            "count_published": 0,
            "count_scheduled": 0,
            "count_draft": 0,
            "published": [],
            "scheduled": [],
            "drafts": [],
            "slugs": [],
        }


def _ga4_summary(slugs: list[str]) -> tuple[int, list[tuple[str, int]]]:
    """Возвращает суммарные просмотры и топ‑5 путей из GA4 по слугам (если настроен).

    Требует GA4_PROPERTY_ID и GA4_JSON_KEY_PATH.
    """
    if not (Config.GA4_PROPERTY_ID and Config.GA4_JSON_KEY_PATH and slugs):
        return 0, []
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_file(Config.GA4_JSON_KEY_PATH)
        client = BetaAnalyticsDataClient(credentials=credentials)
        property_id = f"properties/{Config.GA4_PROPERTY_ID}"
        # фильтранем по pagePath, содержащему любой из slug
        dimensions = [Dimension(name="pagePath")]
        metrics = [Metric(name="screenPageViews")]
        date_ranges = [DateRange(start_date="7daysAgo", end_date="today")]
        request = RunReportRequest(
            property=property_id,
            dimensions=dimensions,
            metrics=metrics,
            date_ranges=date_ranges,
        )
        resp = client.run_report(request)
        total = 0
        rows = []
        for row in resp.rows:
            path = row.dimension_values[0].value or ""
            views = int(row.metric_values[0].value or 0)
            total += views
            if any(s and s in path for s in slugs):
                rows.append((path, views))
        rows.sort(key=lambda x: x[1], reverse=True)
        return total, rows[:5]
    except Exception:
        return 0, []


def _toclick_ctr() -> float | None:
    """Возвращает CTR из to.click (0..1) за 7 дней, если доступен ключ."""
    if not Config.TOCLICK_API_KEY:
        return None
    try:
        url = (Config.TOCLICK_BASE_URL or "https://to.click/api").rstrip("/") + "/ctr?period=7d"
        r = requests.get(url, headers={"Authorization": f"Bearer {Config.TOCLICK_API_KEY}"}, timeout=20)
        if r.status_code < 400:
            data = r.json()
            if isinstance(data, dict) and "ctr" in data:
                return float(data["ctr"])  # ожидаем CTR в долях (0..1)
    except Exception:
        return None
    return None


def _render_pdf(
    summary: dict[str, object],
    ga_total: int,
    ga_top: list[tuple[str, int]],
    ctr: float | None,
) -> bytes:
    """Рендерит PDF‑сводку с кириллицей: counts + списки заголовков."""

    def _register_cyrillic_font() -> str | None:
        # 1) Явный путь из ENV
        candidates: list[str] = []
        env_path = os.getenv("REPORT_FONT_PATH")
        if env_path:
            candidates.append(env_path)
        # 2) Локальный бандл (если добавят в проект)
        candidates.append(str(Path(__file__).resolve().parent.parent / "assets" / "fonts" / "DejaVuSans.ttf"))
        # 3) Системные пути (Windows/Linux)
        candidates.extend(
            [
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/ARIAL.TTF",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            ],
        )
        for idx, p in enumerate(candidates):
            try:
                if p and Path(p).exists():
                    name = f"AppFont{idx}"
                    pdfmetrics.registerFont(TTFont(name, p))
                    return name
            except Exception:
                continue
        return None

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    font_name = _register_cyrillic_font()
    # Заголовок
    if font_name:
        c.setFont(font_name, 16)
    else:
        c.setFont("Helvetica-Bold", 16)
    c.drawString(40, height - 40, "Еженедельная сводка блога")
    # Основной текст
    if font_name:
        c.setFont(font_name, 12)
    else:
        c.setFont("Helvetica", 12)
    # Вспомогательная обёртка по ширине страницы
    margin_left = 40
    margin_right = 40
    max_text_width = width - margin_left - margin_right

    def wrap_lines(text: str, size: int = 12) -> list[str]:
        words = (text or "").split()
        if not words:
            return [""]
        lines: list[str] = []
        current: list[str] = []
        while words:
            word = words.pop(0)
            test = (" ".join([*current, word])).strip()
            w = pdfmetrics.stringWidth(test, font_name or "Helvetica", size)
            if w <= max_text_width or not current:
                current.append(word)
            else:
                lines.append(" ".join(current))
                current = [word]
        if current:
            lines.append(" ".join(current))
        return lines

    def draw_bullet_line(text: str, y_pos: float, prefix: str = "— ") -> float:
        # выводит текст с переносами; возвращает новую координату y
        wrapped = wrap_lines(prefix + text, 12)
        for idx, line in enumerate(wrapped):
            c.drawString(margin_left + (0 if idx == 0 else 16), y_pos, line if idx == 0 else line.strip())
            y_pos -= 16
            if y_pos < 60:
                c.showPage()
                if font_name:
                    c.setFont(font_name, 12)
                else:
                    c.setFont("Helvetica", 12)
                y_pos = height - 60
        return y_pos

    c.drawString(40, height - 70, "Период: последние 7 дней")
    c.drawString(
        40,
        height - 90,
        f"Опубликовано (7д): {summary.get('count_published', 0)} — Запланировано: {summary.get('count_scheduled', 0)} — Черновики: {summary.get('count_draft', 0)}",
    )
    if ga_total:
        c.drawString(40, height - 110, f"GA4 — суммарные просмотры: {ga_total}")
    if ctr is not None:
        c.drawString(40, height - 130, f"CTR (to.click): {ctr * 100:.1f}%")
    # Заголовки — опубликованные
    c.drawString(40, height - 160, "Опубликовано:")
    y = height - 180
    published: list[tuple[str, str]] = summary.get("published", [])  # type: ignore
    if not published:
        y = draw_bullet_line("ещё не публиковали", y)
    else:
        for title, dt_iso in published[:25]:
            suffix = f" ({dt_iso[:10]})" if dt_iso else ""
            y = draw_bullet_line(f"{title}{suffix}", y)

    # Заголовки — запланировано
    c.drawString(40, y - 10, "Запланировано:")
    y -= 30
    scheduled: list[tuple[str, str]] = summary.get("scheduled", [])  # type: ignore
    if not scheduled:
        y = draw_bullet_line("нет запланированных", y)
    else:
        for title, dt_iso in scheduled[:25]:
            suffix = f" ({dt_iso[:16].replace('T', ' ')})" if dt_iso else ""
            y = draw_bullet_line(f"{title}{suffix}", y)
    if ga_top:
        c.showPage()
        if font_name:
            c.setFont(font_name, 14)
        else:
            c.setFont("Helvetica-Bold", 14)
        c.drawString(40, height - 40, "ТОП страниц (GA4)")
        if font_name:
            c.setFont(font_name, 12)
        else:
            c.setFont("Helvetica", 12)
        y = height - 70
        for path, views in ga_top:
            y = draw_bullet_line(f"{views:>6} — {path}", y)
    # Черновики
    c.drawString(40, y - 10, "Черновики:")
    y -= 30
    drafts: list[tuple[str, str]] = summary.get("drafts", [])  # type: ignore
    if not drafts:
        y = draw_bullet_line("нет черновиков", y)
    else:
        for title, dt_iso in drafts[:25]:
            suffix = f" (upd {dt_iso[:16].replace('T', ' ')})" if dt_iso else ""
            y = draw_bullet_line(f"{title}{suffix}", y)
    c.showPage()
    c.save()
    return buf.getvalue()


def send_weekly_report() -> str | None:
    """Собирает сводку, формирует PDF и отправляет письмо. Возвращает 'sent' или None."""
    summary = _ghost_posts_summary(7)
    ga_total, ga_top = _ga4_summary(summary.get("slugs", []))  # type: ignore
    ctr = _toclick_ctr()
    pdf_bytes = _render_pdf(summary, ga_total, ga_top, ctr)

    if not (Config.SMTP_HOST and Config.SMTP_USER and Config.SMTP_PASSWORD and Config.REPORT_EMAIL_TO):
        return None

    lines = [
        f"Публикаций: {summary.get('count', 0)}",
    ]
    if ga_total:
        lines.append(f"GA4 суммарные просмотры: {ga_total}")
    if ctr is not None:
        lines.append(f"CTR: {ctr * 100:.1f}%")

    msg = MIMEMultipart()
    msg["Subject"] = "Еженедельная аналитика блога"
    msg["From"] = Config.SMTP_USER
    msg["To"] = Config.REPORT_EMAIL_TO
    msg.attach(MIMEText("\n".join(lines) or "Сводка по публикациям за неделю во вложении.", "plain", "utf-8"))

    part = MIMEApplication(pdf_bytes, Name="weekly_report.pdf")
    part["Content-Disposition"] = 'attachment; filename="weekly_report.pdf"'
    msg.attach(part)

    with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
        server.starttls()
        server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
        server.sendmail(Config.SMTP_USER, [Config.REPORT_EMAIL_TO], msg.as_string())
    return "sent"
