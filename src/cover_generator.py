"""Модуль генерации обложки."""
from __future__ import annotations

import base64
import io
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .config import Config


def _openai_client():
    if not Config.OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI

        if Config.OPENAI_BASE_URL:
            return OpenAI(api_key=Config.OPENAI_API_KEY, base_url=Config.OPENAI_BASE_URL)
        return OpenAI(api_key=Config.OPENAI_API_KEY)
    except Exception:
        return None


def generate_cover_bytes(title: str) -> bytes:
    img = _generate_base_image()

    # Если используем альтернативный OpenAI-провайдер (например, BotHub), пропустим images API
    # и сразу сгенерируем простую обложку локально.
    use_remote_images = bool(Config.OPENAI_API_KEY) and not bool(Config.OPENAI_BASE_URL)

    if use_remote_images:
        client = _openai_client()
        if client:
            try:
                prompt = (
                    f"Минималистичная контрастная обложка блога про IT. Без текста. Абстрактные формы. Тема: {title}."
                )
                res = client.images.generate(model=Config.OPENAI_IMAGE_MODEL, prompt=prompt, size="1200x630")
                b64 = res.data[0].b64_json
                img_bytes = base64.b64decode(b64)
                img = Image.open(io.BytesIO(img_bytes)).convert("RGB").resize((1200, 630))
            except Exception:
                pass

    img = _overlay_text(img, title)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _generate_base_image() -> Image.Image:
    img = Image.new("RGB", (1200, 630), color=(10, 16, 32))
    return img


def _overlay_text(img: Image.Image, text: str) -> Image.Image:
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except Exception:
        font = ImageFont.load_default()
    margin = 40
    draw.rectangle([(margin - 10, img.height - 200), (img.width - margin, img.height - margin)], fill=(0, 0, 0, 128))
    draw.text((margin, img.height - 180), text[:140], fill=(255, 255, 255), font=font)
    return img
