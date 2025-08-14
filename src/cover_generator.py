"""Модуль генерации обложки."""

from __future__ import annotations

import base64
import io
import logging

from PIL import Image, ImageDraw, ImageFont

from .config import Config


def _openai_client():
    """Возвращает OpenAI client для генерации изображений или None."""
    if not Config.OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI

        return OpenAI(api_key=Config.OPENAI_API_KEY)
    except Exception:
        return None


def _center_crop_to(img: Image.Image, target: tuple[int, int]) -> Image.Image:
    """Масштабирует по краткой стороне и центрирует обрезку под `target`."""
    tw, th = target
    w, h = img.size
    # Масштаб по краткой стороне
    scale = max(tw / w, th / h)
    nw, nh = int(w * scale + 0.5), int(h * scale + 0.5)
    img2 = img.resize((nw, nh), Image.LANCZOS)
    # Центр обрезки
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return img2.crop((left, top, left + tw, top + th))


def generate_cover_bytes(title: str) -> bytes:
    """Генерирует PNG обложку: DALL‑E (если доступно) + наложение заголовка."""
    img = _generate_base_image()

    # Если есть ключ OpenAI — генерируем через DALL‑E (или выбранную модель), затем приводим к 1200x630
    if Config.OPENAI_API_KEY:
        client = _openai_client()
        if client:
            try:
                prompt = (
                    "Minimalist, high-contrast blog cover, modern and clean, abstract tech shapes, vector style; "
                    "flat colors, glossy highlights; no letters, no words, no watermark, no logo. "
                    f"Theme: {title}."
                )
                # Сгенерируем крупнее для качества и обрежем в 1200x630
                res = client.images.generate(
                    model=Config.OPENAI_IMAGE_MODEL,
                    prompt=prompt,
                    size="1792x1024",
                    response_format="b64_json",
                )
                b64 = res.data[0].b64_json
                if not b64 and getattr(res.data[0], "url", None):
                    # Фолбэк: если вернулся URL
                    import requests  # локальный импорт, чтобы не тянуть лишнее выше

                    r = requests.get(res.data[0].url, timeout=60)
                    r.raise_for_status()
                    img_bytes = r.content
                else:
                    img_bytes = base64.b64decode(b64)
                base_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                img = _center_crop_to(base_img, (1200, 630))
            except Exception as e:
                logging.warning("Cover: DALL-E generation failed: %s", e)

    img = _overlay_text(img, title)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _generate_base_image() -> Image.Image:
    """Рисует базовый градиентный фон (fallback), 1200x630."""
    # Светлый вертикальный градиент (fallback)
    width, height = 1200, 630
    img = Image.new("RGB", (width, height))
    top = (240, 248, 255)  # почти белый с синим оттенком
    bottom = (210, 225, 255)
    for y in range(height):
        ratio = y / max(1, height - 1)
        r = int(top[0] * (1 - ratio) + bottom[0] * ratio)
        g = int(top[1] * (1 - ratio) + bottom[1] * ratio)
        b = int(top[2] * (1 - ratio) + bottom[2] * ratio)
        ImageDraw.Draw(img).line([(0, y), (width, y)], fill=(r, g, b))
    # без фигур — фон оставляем чистым
    return img


def _overlay_text(img: Image.Image, text: str) -> Image.Image:
    """Накладывает заголовок с переносами строк по ширине блока."""
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 44)
    except Exception:
        font = ImageFont.load_default()
    margin = 48
    # Подложка
    box = [(margin - 16, img.height - 220), (img.width - margin, img.height - margin)]
    draw.rectangle(box, fill=(0, 24, 64))
    # Перенос строк по ширине
    title = (text or "").strip()
    max_width = img.width - 2 * margin
    words = title.split()
    lines = []
    line = ""
    for w in words:
        test = (line + (" " if line else "") + w).strip()
        if draw.textlength(test, font=font) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    lines = lines[:2]
    y = img.height - 200
    for ln in lines:
        draw.text((margin, y), ln, fill=(255, 255, 255), font=font)
        y += 56
    return img
