"""Money conventions.

- Amounts are integers in **millimes** (1 DT = 1000 millimes) – in Python, SQL (``BIGINT``) and JSON.
  Never floats. Column names end in ``_millimes``, JSON fields in ``Millimes`` (``priceMillimes``).
- Use the pydantic types below for input validation; they cap amounts at 100 000 DT so typos cannot explode sums.
- Balance of a patient: ``totalMillimes`` = Σ treatment.price, ``paidMillimes`` = Σ payment.amount,
  ``dueMillimes`` = total − paid (may become negative on overpayment).
- Display formatting happens in the web app (``formatMillimes`` in web/src/lib/i18n.svelte.ts);
  :func:`format_millimes` here is the same format for texts the server builds (e.g. receipts).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

MILLIMES_PER_DINAR = 1000
MAX_MILLIMES = 100_000 * MILLIMES_PER_DINAR

#: 0 … 100 000 DT, e.g. a price or a required deposit.
Millimes = Annotated[int, Field(ge=0, le=MAX_MILLIMES, strict=True)]
#: 0.001 … 100 000 DT, e.g. a payment.
PositiveMillimes = Annotated[int, Field(gt=0, le=MAX_MILLIMES, strict=True)]


def dinars(amount: int | float) -> int:
    """``dinars(12.5)`` → 12500 millimes (for seeds and tests; rounds to the millime)."""
    return round(amount * MILLIMES_PER_DINAR)


def format_millimes(millimes: int) -> str:
    """``120000`` → ``"120 DT"``, ``12500`` → ``"12,500 DT"``, ``1250000`` → ``"1 250 DT"``, ``-500`` → ``"-0,500 DT"``."""
    sign = "-" if millimes < 0 else ""
    whole, rest = divmod(abs(millimes), MILLIMES_PER_DINAR)
    grouped = f"{whole:,}".replace(",", " ")
    return f"{sign}{grouped} DT" if rest == 0 else f"{sign}{grouped},{rest:03d} DT"
