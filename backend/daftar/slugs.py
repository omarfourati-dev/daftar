"""Practice slugs – the sub-domain of the booking page: ``https://<slug>.<BASE_DOMAIN>``.

3–40 characters, lower-case letters, digits and inner hyphens; some names are reserved. Demo practices get
``demo-<8 random characters>``. The database enforces the same rules (migration 0001).
"""

from __future__ import annotations

import re
import secrets
import string
import unicodedata

SLUG_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$"
_SLUG = re.compile(SLUG_PATTERN)
RESERVED_SLUGS = frozenset(
    {"www", "app", "api", "admin", "demo", "mail", "smtp", "static", "assets", "daftar", "status", "monitoring", "test"}
)
MAX_LENGTH = 40


def slug_problem(slug: str) -> str | None:
    """``"invalid"``, ``"reserved"`` or None when the slug can be used (uniqueness is checked by the database)."""
    if not _SLUG.fullmatch(slug):
        return "invalid"
    if slug in RESERVED_SLUGS:
        return "reserved"
    return None


def suggest_slug(name: str) -> str:
    """A valid slug derived from a practice name (accents removed, words joined by hyphens)."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    words = re.findall(r"[a-z0-9]+", ascii_name)
    slug = ""
    for word in words:
        candidate = f"{slug}-{word}" if slug else word
        if len(candidate) > MAX_LENGTH:
            break
        slug = candidate
    if not slug:
        return "cabinet"
    if slug_problem(slug) is not None:
        slug = f"{slug}-cabinet"[:MAX_LENGTH].strip("-")
    return slug


def demo_slug() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "demo-" + "".join(secrets.choice(alphabet) for _ in range(8))
