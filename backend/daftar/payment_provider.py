"""Online payment of subscription invoices (section 11.4) behind an exchangeable provider.

Production uses Flouci (``daftar/flouci.py``) when ``FLOUCI_APP_TOKEN`` and ``FLOUCI_APP_SECRET`` are set; without
them online payment is off (``onlinePaymentAvailable=false``) and the admin records payments by hand. Tests put a
fake on ``app.state.payment_provider``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Protocol

from fastapi import Depends, Request

from .settings import Settings


@dataclass(frozen=True)
class CreatedPayment:
    payment_id: str
    link: str  # where the payer is sent


@dataclass(frozen=True)
class VerifiedPayment:
    """What the provider itself says about a payment (the only source of truth – never a webhook body)."""

    status: str  # SUCCESS | PENDING | EXPIRED | FAILURE | …
    amount_millimes: int
    tracking_id: str | None  # our invoice number, as sent when the payment was created


class ProviderError(Exception):
    """The provider could not be reached or answered something unexpected. Never contains keys."""


class PaymentProvider(Protocol):
    def create_payment(
        self, *, amount_millimes: int, tracking_id: str, success_url: str, fail_url: str, webhook_url: str
    ) -> CreatedPayment: ...

    def verify_payment(self, payment_id: str) -> VerifiedPayment: ...

    def check_signature(self, header: str | None, body: bytes, now: datetime) -> bool: ...


def provider_from_settings(settings: Settings) -> PaymentProvider | None:
    if not (settings.flouci_app_token and settings.flouci_app_secret):
        return None
    from .flouci import FlouciProvider

    return FlouciProvider(settings.flouci_app_token, settings.flouci_app_secret)


_UNSET = object()


def get_payment_provider(request: Request) -> PaymentProvider | None:
    """The app's provider – built once from the settings (or set by tests on ``app.state.payment_provider``)."""
    state = request.app.state
    provider = getattr(state, "payment_provider", _UNSET)
    if provider is _UNSET:
        provider = provider_from_settings(state.ctx.settings)
        state.payment_provider = provider
    return provider  # type: ignore[return-value]


Provider = Annotated[PaymentProvider | None, Depends(get_payment_provider)]
