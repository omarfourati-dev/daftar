"""Demo practices show the stock module filled (spec stock-hygiène 8): products, deliveries, use per act, orders."""

from typing import Any

import pytest
from fastapi.testclient import TestClient


def start(client: TestClient, **body: Any) -> dict[str, str]:
    res = client.post("/api/demo", json=body, headers={"X-Forwarded-For": "10.9.0.1"})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


@pytest.mark.parametrize("specialty", ["dentiste", "generaliste", "psychologue"])
def test_a_demo_has_products_deliveries_and_use(client: TestClient, specialty: str) -> None:
    headers = start(client, specialty=specialty)
    products = client.get("/api/stock/products", headers=headers).json()
    assert len(products) >= 7
    assert all(p["quantity"] >= 0 for p in products)  # a believable stock
    assert {"low", "ok"} <= {p["status"] for p in products}
    assert any(p["expiry"] == "soon" for p in products)
    assert all(p["averageCostMillimes"] for p in products)
    assert len(client.get("/api/stock/suppliers", headers=headers).json()) == 2
    receipts = client.get("/api/stock/receipts", headers=headers).json()
    assert len(receipts) >= 3 and all(r["totalMillimes"] > 0 for r in receipts)
    to_order = client.get("/api/stock/to-order", headers=headers).json()
    assert to_order["count"] >= 2
    assert client.get("/api/dashboard", headers=headers).json()["stockToOrder"] == to_order["count"]
    stats = client.get("/api/stock/stats", headers=headers).json()
    assert stats["spendingMillimes"] > 0  # at least the delivery of the day
    assert stats["previousSpendingMillimes"] > 0  # a delivery of last month to compare with
    assert stats["usageMillimes"] > 0


def test_a_dentist_demo_counts_material_per_act(client: TestClient) -> None:
    headers = start(client, specialty="dentiste")
    stats = client.get("/api/stock/stats", headers=headers).json()
    acts = [s for s in stats["byService"] if s["serviceId"] is not None]
    assert acts and all(s["treatments"] >= 1 for s in acts)
    assert any("Carpules" in item["name"] for s in acts for item in s["items"])
    movements = client.get("/api/stock/movements?limit=200", headers=headers).json()
    uses = [m for m in movements if m["kind"] == "use"]
    assert any(m["appointmentId"] and m["serviceId"] for m in uses)
    assert any(m["kind"] == "waste" for m in movements)


def test_an_arabic_demo_names_its_products_in_arabic(client: TestClient) -> None:
    headers = start(client, specialty="dentiste", lang="ar")
    names = [p["name"] for p in client.get("/api/stock/products", headers=headers).json()]
    assert any("خراطيش" in name for name in names)
