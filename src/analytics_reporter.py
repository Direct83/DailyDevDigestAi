"""Модуль сборки и отправки аналитики."""

from __future__ import annotations

import io
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


def _ghost_headers() -> dict[str, str]:
    if not (Config.GHOST_ADMIN_API_URL and Config.GHOST_ADMIN_API_KEY):
        return {}
    import jwt

    kid, secret = Config.GHOST_ADMIN_API_KEY.split(":", 1)
    iat = int(datetime.utcnow().timestamp())
    header = {"alg": "HS256", "typ": "JWT", "kid": kid}
    payload = {"iat": iat, "exp": iat + 5 * 60, "aud": "/v5/admin/"}
    token = jwt.encode(payload, bytes.fromhex(secret), algorithm="HS256", headers=header)
    return {"Authorization": f"Ghost {token}"}


def _ghost_posts_summary(days: int = 7) -> dict[str, object]:
    if not Config.GHOST_ADMIN_API_URL:
        return {"count": 0, "titles": []}
    base = Config.GHOST_ADMIN_API_URL.rstrip("/") + "/ghost/api/admin"
    headers = _ghost_headers()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        r = requests.get(
            base + f'/posts/?filter=published_at:>"{since}"&fields=title,slug,published_at&limit=50',
            headers=headers,
            timeout=60,
        )
        r.raise_for_status()
        data = r.json().get("posts", [])
        titles = [p.get("title") for p in data]
        slugs = [p.get("slug") for p in data]
        return {"count": len(data), "titles": titles, "slugs": slugs}
    except Exception:
        return {"count": 0, "titles": [], "slugs": []}


def _ga4_summary(slugs: list[str]) -> tuple[int, list[tuple[str, int]]]:
    """Возвращает общее число просмотров и топ-5 страниц по просмотрам за 7 дней.

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
    c.drawString(40, height - 70, "Период: последние 7 дней")
    c.drawString(40, height - 90, f"Количество публикаций: {summary.get('count', 0)}")
    if ga_total:
        c.drawString(40, height - 110, f"GA4 — суммарные просмотры: {ga_total}")
    if ctr is not None:
        c.drawString(40, height - 130, f"CTR (to.click): {ctr * 100:.1f}%")
    c.drawString(40, height - 160, "Заголовки:")
    y = height - 180
    for title in summary.get("titles", [])[:25]:
        c.drawString(50, y, f"— {title}")
        y -= 18
        if y < 60:
            c.showPage()
            y = height - 60
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
            c.drawString(50, y, f"{views:>6} — {path}")
            y -= 18
            if y < 60:
                c.showPage()
                y = height - 60
    c.showPage()
    c.save()
    return buf.getvalue()


def send_weekly_report() -> str | None:
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
