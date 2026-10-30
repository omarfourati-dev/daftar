"""Business counters of the be-patienten modules exist from the start with 0 (Prometheus ``increase()`` would
otherwise miss the very first event – the alert ``DaftarFeedback`` uses ``increase(daftar_feedback_total[15m]) > 0``)."""

from fastapi.testclient import TestClient


def test_counters_are_exported_with_zero_at_startup(client: TestClient) -> None:
    text = client.get("/metrics").text
    assert "daftar_feedback_total 0.0" in text
    assert "daftar_pilot_requests_total 0.0" in text
    assert "daftar_demo_started_total 0.0" in text
