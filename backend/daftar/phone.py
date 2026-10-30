"""Phone numbers, normalized to E.164 (``+21620123456``).

Tunisian input – 8 digits, optionally with 216 / +216 / 00216 in front, spaces, dots, dashes or brackets:
``"20 123 456"``, ``"+216 20123456"``, ``"0021620123456"``, ``"216 20 123 456"`` → ``+21620123456``.
Other countries only with ``+`` or ``00`` (``"+33 6 12 34 56 78"`` → ``+33612345678``).
Families share numbers – a phone number is never unique.

In pydantic models use the ready-made types::

    class PatientIn(ApiModel):
        phone: Phone                 # required, normalized, 422 code "invalid_phone" otherwise
        other_phone: OptionalPhone = None
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator

TUNISIA = "216"
_SEPARATORS = re.compile(r"[\s.\-/()  ]")
INVALID_PHONE = "invalid_phone: Numéro de téléphone invalide."


class InvalidPhone(ValueError):
    pass


def normalize_phone(raw: str) -> str:
    """E.164 or :class:`InvalidPhone` (a ``ValueError``, so pydantic turns it into a 422)."""
    text = _SEPARATORS.sub("", raw or "")
    if text.startswith("00"):
        text = "+" + text[2:]
    if text.startswith("+"):
        digits = text[1:]
        if not digits.isdigit():
            raise InvalidPhone(INVALID_PHONE)
        if digits.startswith(TUNISIA):
            if len(digits) != len(TUNISIA) + 8:
                raise InvalidPhone(INVALID_PHONE)
        elif not (8 <= len(digits) <= 15) or digits[0] == "0":
            raise InvalidPhone(INVALID_PHONE)
        return "+" + digits
    if not text.isdigit():
        raise InvalidPhone(INVALID_PHONE)
    if len(text) == 8:
        return "+" + TUNISIA + text
    if len(text) == 11 and text.startswith(TUNISIA):
        return "+" + text
    raise InvalidPhone(INVALID_PHONE)


def phone_digits(e164: str) -> str:
    """Digits without ``+`` – what ``https://wa.me/<digits>`` expects."""
    return e164.removeprefix("+")


def _optional(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    return normalize_phone(raw)


Phone = Annotated[str, AfterValidator(normalize_phone)]
OptionalPhone = Annotated[str | None, AfterValidator(_optional)]
