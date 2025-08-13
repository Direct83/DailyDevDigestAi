"""Модуль генерации обложки."""
from __future__ import annotations

import base64
import io
from typing import Tuple

from .config import openai_config

try:
    from openai import OpenAI  # type: ignore
except Exception:  # пакет может отсутствовать на мок-этапе
    OpenAI = None  # type: ignore

try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
except Exception:
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFont = None  # type: ignore


def _ensure_size_1200x630(img: "Image.Image") -> "Image.Image":  # type: ignore[name-defined]
    target_w, target_h = 1200, 630
    # Масштабируем по меньшей стороне и центр‑кропим
    img = img.convert("RGB")
    scale = max(target_w / img.width, target_h / img.height)
    new_w, new_h = int(img.width * scale), int(img.height * scale)
    img = img.resize((new_w, new_h))
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def _overlay_title(img: "Image.Image", title: str) -> "Image.Image":  # type: ignore[name-defined]
    draw = ImageDraw.Draw(img)
    # Подложка
    margin = 24
    rect_h = 110
    draw.rectangle([(0, img.height - rect_h - margin), (img.width, img.height)], fill=(0, 0, 0, 180))
    # Текст
    if ImageFont is not None:
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
    else:
        font = None
    text = (title or "").strip()[:100]
    draw.text((margin, img.height - rect_h), text, font=font, fill=(255, 255, 255))
    return img


def generate_cover(title: str) -> bytes:
    """Генерирует обложку 1200x630. При наличии OPENAI_API_KEY — DALL·E, иначе мок.
    Накладывает заголовок.
    """
    # Мок: пусто, если нет зависимостей
    if not Image:
        return b""

    # Попробуем реальную генерацию через OpenAI Images
    if openai_config.api_key and OpenAI is not None:
        try:
            client = OpenAI()
            prompt = (
                "Минималистичная обложка блога, контрастные цвета, иконографика по теме: "
                f"{title}. Без текста, чистый фон и простые геометрические формы."
            )
            resp = client.images.generate(
                model=openai_config.image_model,
                prompt=prompt,
                size="1024x1024",
            )
            b64 = resp.data[0].b64_json  # type: ignore[attr-defined]
            raw = base64.b64decode(b64)
            img = Image.open(io.BytesIO(raw))
            img = _ensure_size_1200x630(img)
            img = _overlay_title(img, title)
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=90)
            return out.getvalue()
        except Exception:
            pass

    # Фолбэк: простая однотонная картинка с текстом
    bg = Image.new("RGB", (1200, 630), color=(20, 20, 20))
    bg = _overlay_title(bg, title)
    out = io.BytesIO()
    bg.save(out, format="JPEG", quality=90)
    return out.getvalue()
