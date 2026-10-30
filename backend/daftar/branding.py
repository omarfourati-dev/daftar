"""Per-practice app identity on its sub-domain (section 13): web app manifests and icons.

- ``/manifest.webmanifest`` → the practice's staff app (“<name> – Daftar”, start ``/app``);
- ``/booking.webmanifest`` → the patients' booking page (“<name> – Rendez-vous”, start ``/``);
- ``/icons/practice-192.png``, ``-512.png``, ``-maskable-512.png`` → white initials on the brand colour, rendered
  with Pillow and kept in memory; the cache key contains name and colour, so a change shows up immediately.
"""

from __future__ import annotations

import io
import re
import unicodedata
from functools import lru_cache
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ICONS = {
    "/icons/practice-192.png": (192, False),
    "/icons/practice-512.png": (512, False),
    "/icons/practice-maskable-512.png": (512, True),
}
SHORT_NAME_MAX = 12
#: Words that say nothing about which practice it is.
_GENERIC = {
    "cabinet", "centre", "clinique", "polyclinique", "dr", "dr.", "docteur", "dentaire", "medical", "médical",
    "medicale", "médicale", "de", "du", "des",
}
_ARTICLES = {"el", "la", "le", "les", "l", "d", "et", "&"}


def _significant(name: str) -> list[str]:
    words = name.split()
    kept = [w for w in words if w.lower() not in _GENERIC]
    return kept or words


def short_name(name: str) -> str:
    """At most 12 characters for the home screen: ``Cabinet Dentaire du Lac`` → ``Lac``."""
    result = ""
    for word in _significant(name):
        candidate = f"{result} {word}" if result else word
        if len(candidate) > SHORT_NAME_MAX:
            break
        result = candidate
    return result or name.strip()[:SHORT_NAME_MAX].strip()


def _latin(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode().lower())


def initials(name: str) -> str:
    """One or two Latin initials (first and last meaningful word); ``D`` (Daftar) when there are none."""
    words = [_latin(w) for w in _significant(name) if w.lower() not in _ARTICLES]
    words = [w for w in words if w]
    if not words:
        return "D"
    if len(words) == 1:
        return words[0][0].upper()
    return (words[0][0] + words[-1][0]).upper()


def manifest(*, name: str, brand_color: str, kind: str) -> dict[str, Any]:
    booking = kind == "booking"
    return {
        "id": "/" if booking else "/app",
        "name": f"{name} – {'Rendez-vous' if booking else 'Daftar'}",
        "short_name": short_name(name),
        "lang": "fr",
        "start_url": "/" if booking else "/app",
        "scope": "/",
        "display": "standalone",
        "background_color": "#f8fafc",
        "theme_color": brand_color,
        "icons": [
            {"src": "/icons/practice-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/icons/practice-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/icons/practice-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }


@lru_cache(maxsize=256)
def render_icon(text: str, brand_color: str, size: int, maskable: bool) -> bytes:
    """PNG bytes: ``text`` in white on ``brand_color`` – full bleed when maskable, else a rounded square."""
    color = tuple(int(brand_color[i : i + 2], 16) for i in (1, 3, 5))
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if maskable:
        draw.rectangle((0, 0, size, size), fill=(*color, 255))
        text_box = size * 0.5  # keep the letters inside the maskable safe zone
    else:
        draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=round(size * 0.22), fill=(*color, 255))
        text_box = size * 0.62
    font_size = round(text_box / (1 if len(text) == 1 else 1.25))
    font = ImageFont.load_default(size=font_size)
    stroke = max(1, size // 96)
    draw.text((size / 2, size / 2), text, font=font, fill=(255, 255, 255, 255), anchor="mm",
              stroke_width=stroke, stroke_fill=(255, 255, 255, 255))
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()
