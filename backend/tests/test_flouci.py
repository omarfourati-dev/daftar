"""The Flouci implementation of the payment provider (API v2, docs.flouci.com) – against a recorded transport.

The requests must match the official documentation exactly (URLs, headers, field names, amount as a string in
millimes); keys never appear in errors or logs.
"""

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Any

import pytest

from daftar.flouci import FlouciProvider
from daftar.payment_provider import CreatedPayment, ProviderError, VerifiedPayment, provider_from_settings
from daftar.settings import Settings
from tests.conftest import JWT_SECRET, TEST_DATABASE_URL

PUBLIC, PRIVATE = "pub-123", "priv-456-very-secret"
NOW = datetime(2026, 10, 30, 8, 0, tzinfo=UTC)


class Transport:
    """Records requests and answers with prepared ``(status, body)`` pairs (or raises)."""

    def __init__(self, *answers: Any) -> None:
        self.answers = list(answers)
        self.requests: list[dict[str, Any]] = []

    def __call__(self, method: str, url: str, headers: dict[str, str], body: bytes | None) -> tuple[int, bytes]:
        self.requests.append({"method": method, "url": url, "headers": headers, "body": body})
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        status, payload = answer
        return status, payload if isinstance(payload, bytes) else json.dumps(payload).encode()


def provider(*answers: Any) -> tuple[FlouciProvider, Transport]:
    transport = Transport(*answers)
    return FlouciProvider(PUBLIC, PRIVATE, transport=transport), transport


def test_generate_payment_request_follows_the_documentation() -> None:
    p, t = provider((200, {"result": {"success": True, "payment_id": "AgCKuBm0S5uLPghBo571MQ",
                                      "link": "https://checkout.flouci.com/x/AgCKuBm0S5uLPghBo571MQ",
                                      "developer_tracking_id": "DAF-2026-0001"}, "name": "developers", "code": 0, "version": "v2"}))
    created = p.create_payment(amount_millimes=49_000, tracking_id="DAF-2026-0001", success_url="https://d.example/ok",
                               fail_url="https://d.example/ko", webhook_url="https://d.example/api/public/flouci/webhook")
    assert created == CreatedPayment(payment_id="AgCKuBm0S5uLPghBo571MQ", link="https://checkout.flouci.com/x/AgCKuBm0S5uLPghBo571MQ")
    (req,) = t.requests
    assert req["method"] == "POST"
    assert req["url"] == "https://developers.flouci.com/api/v2/generate_payment"
    assert req["headers"]["Authorization"] == f"Bearer {PUBLIC}:{PRIVATE}"
    assert req["headers"]["Content-Type"] == "application/json"
    assert json.loads(req["body"]) == {
        "amount": "49000",
        "accept_card": True,
        "success_link": "https://d.example/ok",
        "fail_link": "https://d.example/ko",
        "webhook": "https://d.example/api/public/flouci/webhook",
        "webhook_version": 2,
        "developer_tracking_id": "DAF-2026-0001",
        "session_timeout_secs": 1200,
    }


@pytest.mark.parametrize(
    "answer",
    [
        (400, {"result": {"status": 400, "message": "Bad Request"}}),
        (200, {"result": {"success": False}}),
        (200, {"result": {"success": True, "link": "https://x"}}),  # no payment_id
        (200, {"result": {"success": True, "payment_id": "a b", "link": "https://x"}}),
        (200, {"result": {"success": True, "payment_id": "abc", "link": "javascript:alert(1)"}}),
        (200, b"<html>gateway error</html>"),
        (500, b""),
        OSError("connection refused"),
    ],
)
def test_generate_payment_errors_never_leak_keys(answer: Any, caplog: pytest.LogCaptureFixture) -> None:
    p, _ = provider(answer)
    with caplog.at_level(logging.DEBUG), pytest.raises(ProviderError) as caught:
        p.create_payment(amount_millimes=1000, tracking_id="DAF-2026-0001", success_url="https://a", fail_url="https://b",
                         webhook_url="https://c")
    for secret in (PUBLIC, PRIVATE):
        assert secret not in str(caught.value) and secret not in repr(caught.value)
        assert secret not in caplog.text
    assert PRIVATE not in repr(p)


def test_verify_payment_request_and_answer() -> None:
    p, t = provider((200, {"success": True, "result": {"type": "card", "amount": 49_000, "status": "SUCCESS",
                                                       "details": {}, "developer_tracking_id": "DAF-2026-0001",
                                                       "settlement_status": "PROCESSING"},
                           "status_code": 200, "name": "developers", "code": 0, "version": "2.0.0"}))
    assert p.verify_payment("AgCKuBm0S5uLPghBo571MQ") == VerifiedPayment(status="SUCCESS", amount_millimes=49_000,
                                                                         tracking_id="DAF-2026-0001")
    (req,) = t.requests
    assert req["method"] == "GET" and req["body"] is None
    assert req["url"] == "https://developers.flouci.com/api/v2/verify_payment/AgCKuBm0S5uLPghBo571MQ"
    assert req["headers"]["Authorization"] == f"Bearer {PUBLIC}:{PRIVATE}"


def test_verify_tolerates_a_missing_tracking_id() -> None:
    p, _ = provider((200, {"success": True, "result": {"amount": 1250, "status": "PENDING", "developer_tracking_id": None}}))
    assert p.verify_payment("abc") == VerifiedPayment(status="PENDING", amount_millimes=1250, tracking_id=None)


@pytest.mark.parametrize(
    "answer",
    [
        (404, {"result": {"status": 404, "message": "Payment not found"}}),
        (200, {"success": False, "result": {"status": "SUCCESS", "amount": 1}}),
        (200, {"success": True, "result": {"status": "SUCCESS", "amount": "49000"}}),  # amount must be an integer
        (200, {"success": True, "result": {"amount": 1}}),
        OSError("timeout"),
    ],
)
def test_verify_errors(answer: Any) -> None:
    p, _ = provider(answer)
    with pytest.raises(ProviderError):
        p.verify_payment("abc")


@pytest.mark.parametrize("payment_id", ["", "../admin", "a/b", "a?b=c", "x" * 201, "a b"])
def test_verify_refuses_odd_payment_ids_without_calling_flouci(payment_id: str) -> None:
    p, t = provider()
    with pytest.raises(ProviderError):
        p.verify_payment(payment_id)
    assert t.requests == []


def _signature(body: bytes, t: int, key: str = PRIVATE) -> str:
    mac = hmac.new(key.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={t},v1={mac}"


def test_webhook_signature() -> None:
    p, _ = provider()
    body = b'{"event":"payment.succeeded","payment_id":"abc"}'
    t = int(NOW.timestamp())
    assert p.check_signature(_signature(body, t), body, NOW) is True
    assert p.check_signature(_signature(body, t - 299), body, NOW) is True
    assert p.check_signature(_signature(body, t - 301), body, NOW) is False  # replay
    assert p.check_signature(_signature(body, t + 301), body, NOW) is False
    assert p.check_signature(_signature(body, t, key="other"), body, NOW) is False
    assert p.check_signature(_signature(body + b" ", t), body, NOW) is False
    for header in (None, "", "t=abc,v1=00", "v1=00", f"t={t}", "garbage"):
        assert p.check_signature(header, body, NOW) is False


def test_provider_from_settings() -> None:
    def settings(**keys: Any) -> Settings:
        return Settings(database_url=TEST_DATABASE_URL, jwt_secret=JWT_SECRET, **keys)

    assert provider_from_settings(settings()) is None
    assert provider_from_settings(settings(flouci_app_token="a")) is None
    assert isinstance(provider_from_settings(settings(flouci_app_token="a", flouci_app_secret="b")), FlouciProvider)
