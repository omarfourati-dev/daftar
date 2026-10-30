"""Flouci payment API v2 (official documentation: https://docs.flouci.com, read on 30.10.2026).

- Generate Payment: ``POST https://developers.flouci.com/api/v2/generate_payment`` with
  ``Authorization: Bearer <PUBLIC_KEY>:<PRIVATE_KEY>`` and JSON ``{amount (string, millimes), accept_card,
  success_link, fail_link, webhook, webhook_version, developer_tracking_id, session_timeout_secs}`` →
  ``{result: {success, payment_id, link, developer_tracking_id}, …}``.
- Verify Payment: ``GET https://developers.flouci.com/api/v2/verify_payment/{payment_id}`` (same header) →
  ``{success, result: {amount (integer, millimes), status: SUCCESS|PENDING|EXPIRED|FAILURE|…,
  developer_tracking_id}}``. A payment counts only with ``success == true`` and ``status == "SUCCESS"``.
- Webhook v2: ``POST`` JSON event, header ``X-Flouci-Signature: t=<unix>,v1=<hex HMAC-SHA256(private key,
  "<t>.<raw body>")>``; we check it in constant time, refuse timestamps older than 5 minutes and **still** confirm
  every payment with Verify Payment (the body is never trusted).

``FLOUCI_APP_TOKEN`` is the public key, ``FLOUCI_APP_SECRET`` the private key. Keys are never logged and never part
of an error message. Only the Python standard library is used (``urllib``).

STATUS: implemented exactly after the official documentation, but NOT YET RUN AGAINST THE REAL FLOUCI API (no keys
on 30.10.2026). Before going live: one payment with the "TEST APP" keys of the Flouci test environment (test card
4509 2111 1111 1119), check the redirect, the signed webhook and Verify Payment.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .payment_provider import CreatedPayment, ProviderError, VerifiedPayment

log = logging.getLogger("daftar")

API = "https://developers.flouci.com/api/v2"
TIMEOUT_SECONDS = 15
SESSION_TIMEOUT_SECS = 1200
SIGNATURE_MAX_AGE_SECONDS = 300
_PAYMENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,200}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")

#: ``(method, url, headers, body) -> (status, response body)``; raises OSError on network problems.
Transport = Callable[[str, str, dict[str, str], bytes | None], tuple[int, bytes]]


def urllib_transport(method: str, url: str, headers: dict[str, str], body: bytes | None) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)  # noqa: S310 - fixed https URL
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            return response.status, response.read(1_000_000)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(1_000_000)


class FlouciProvider:
    def __init__(self, public_key: str, private_key: str, *, transport: Transport = urllib_transport) -> None:
        self._public = public_key
        self._private = private_key
        self._transport = transport

    def __repr__(self) -> str:
        return "FlouciProvider(keys=***)"

    def _call(self, method: str, url: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
        headers = {"Authorization": f"Bearer {self._public}:{self._private}", "Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        try:
            status, raw = self._transport(method, url, headers, data)
        except OSError as exc:
            log.warning("flouci: %s %s unreachable (%s)", method, url.split("/api/")[-1], type(exc).__name__)
            raise ProviderError("Flouci est injoignable.") from None
        try:
            return status, json.loads(raw.decode("utf-8")) if raw else None
        except (UnicodeDecodeError, ValueError):
            log.warning("flouci: %s answered %s without JSON", url.split("/api/")[-1], status)
            raise ProviderError("Réponse inattendue de Flouci.") from None

    def create_payment(
        self, *, amount_millimes: int, tracking_id: str, success_url: str, fail_url: str, webhook_url: str
    ) -> CreatedPayment:
        status, data = self._call("POST", f"{API}/generate_payment", {
            "amount": str(amount_millimes),
            "accept_card": True,
            "success_link": success_url,
            "fail_link": fail_url,
            "webhook": webhook_url,
            "webhook_version": 2,
            "developer_tracking_id": tracking_id,
            "session_timeout_secs": SESSION_TIMEOUT_SECS,
        })
        result = data.get("result") if isinstance(data, dict) else None
        if status != 200 or not isinstance(result, dict) or result.get("success") is not True:
            log.warning("flouci: generate_payment refused (HTTP %s)", status)
            raise ProviderError("Flouci a refusé la création du paiement.")
        payment_id, link = result.get("payment_id"), result.get("link")
        if not isinstance(payment_id, str) or not _PAYMENT_ID.fullmatch(payment_id):
            raise ProviderError("Réponse inattendue de Flouci.")
        if not isinstance(link, str) or not link.startswith("https://"):
            raise ProviderError("Réponse inattendue de Flouci.")
        return CreatedPayment(payment_id=payment_id, link=link)

    def verify_payment(self, payment_id: str) -> VerifiedPayment:
        if not _PAYMENT_ID.fullmatch(payment_id or ""):
            raise ProviderError("Identifiant de paiement invalide.")
        status, data = self._call("GET", f"{API}/verify_payment/{payment_id}")
        if status != 200 or not isinstance(data, dict) or data.get("success") is not True:
            log.warning("flouci: verify_payment refused (HTTP %s)", status)
            raise ProviderError("Flouci n'a pas pu vérifier le paiement.")
        result = data.get("result")
        if not isinstance(result, dict):
            raise ProviderError("Réponse inattendue de Flouci.")
        amount, state, tracking = result.get("amount"), result.get("status"), result.get("developer_tracking_id")
        if type(amount) is not int or not isinstance(state, str):
            raise ProviderError("Réponse inattendue de Flouci.")
        return VerifiedPayment(status=state, amount_millimes=amount, tracking_id=tracking if isinstance(tracking, str) else None)

    def check_signature(self, header: str | None, body: bytes, now: datetime) -> bool:
        if not header:
            return False
        parts = dict(part.split("=", 1) for part in header.split(",") if "=" in part)
        stamp, given = parts.get("t", ""), parts.get("v1", "")
        if not stamp.isdigit() or not _HEX.fullmatch(given):
            return False
        if abs(now.timestamp() - int(stamp)) > SIGNATURE_MAX_AGE_SECONDS:
            return False
        expected = hmac.new(self._private.encode("utf-8"), stamp.encode("ascii") + b"." + body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, given)
