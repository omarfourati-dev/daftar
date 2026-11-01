"""Demo practices show "Hygiène du jour" filled (spec stock-hygiène 8): equipment, tasks, three weeks of proofs."""

from typing import Any

import pytest
from fastapi.testclient import TestClient


def start(client: TestClient, **body: Any) -> dict[str, str]:
    res = client.post("/api/demo", json=body, headers={"X-Forwarded-For": "10.9.1.1"})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


@pytest.mark.parametrize("specialty", ["dentiste", "generaliste", "psychologue"])
def test_a_demo_has_hygiene_tasks_with_their_history(client: TestClient, specialty: str) -> None:
    headers = start(client, specialty=specialty)
    tasks = client.get("/api/hygiene/tasks", headers=headers).json()
    assert len(tasks) >= 3
    today = client.get("/api/hygiene/today", headers=headers).json()
    states = [i["state"] for i in today["items"]]
    assert states[0] == "overdue"  # red on top
    assert "due" in states or "done" in states
    assert client.get("/api/badges", headers=headers).json()["hygiene"] == today["open"] >= 1
    rows = client.get("/api/hygiene/history", headers=headers).json()["rows"]
    statuses = {r["status"] for r in rows}
    assert {"done", "missed"} <= statuses
    assert any(r["done"] and r["done"]["result"] == "not_ok" for r in rows) or specialty != "dentiste"


def test_a_dentist_demo_has_its_equipment(client: TestClient) -> None:
    headers = start(client, specialty="dentiste")
    kinds = {e["kind"] for e in client.get("/api/hygiene/equipment", headers=headers).json()}
    assert {"autoclave", "fauteuil", "aspiration", "radiographie"} <= kinds
