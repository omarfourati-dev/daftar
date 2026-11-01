"""Demo practices show sterilisation, traceability and specimen labels from the first click (spec stock-hygiène 8)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient


def start(client: TestClient, **body: Any) -> dict[str, str]:
    res = client.post("/api/demo", json=body, headers={"X-Forwarded-For": "10.9.2.1"})
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


@pytest.mark.parametrize("lang", ["fr", "ar"])
def test_a_dentist_demo_has_cycles_packs_and_their_patients(client: TestClient, lang: str) -> None:
    headers = start(client, specialty="dentiste", lang=lang)
    setup = client.get("/api/hygiene/cycles/setup", headers=headers).json()
    assert [(a["labelCode"], a["nextNumber"]) for a in setup["autoclaves"]] == [("A1", 413)]
    cycles = client.get("/api/hygiene/cycles?from=2026-07-01", headers=headers).json()["cycles"]
    assert [c["number"] for c in cycles] == [412, 411, 410, 409, 380]
    assert [c["result"] for c in cycles] == ["ok", "ok", "not_ok", "ok", "ok"]
    assert cycles[2]["packs"] == [] and cycles[2]["packCount"] == 5 and cycles[2]["note"]
    states = {p["state"] for c in cycles for p in c["packs"]}
    assert {"usable", "used", "expired"} <= states
    used = next(p for c in cycles for p in c["packs"] if p["state"] == "used")
    traced = client.get(f"/api/hygiene/trace?code={used['code']}", headers=headers).json()
    assert traced["use"]["patientName"] and traced["use"]["appointmentId"]
    patient = client.get(f"/api/hygiene/trace?patientId={traced['use']['patientId']}", headers=headers).json()
    assert used["code"] in [u["code"] for u in patient["uses"]]
    usable = client.get("/api/hygiene/packs", headers=headers).json()
    assert usable and all(p["state"] == "usable" for p in usable)


def test_a_generalist_demo_has_birth_dates_and_specimen_prints(client: TestClient) -> None:
    headers = start(client, specialty="generaliste")
    data = client.get("/api/practice/export", headers=headers).json()
    with_date = [p for p in data["patients"] if p["birthDate"]]
    assert len(with_date) >= 5 and all(int(p["birthDate"][:4]) == p["birthYear"] for p in with_date)
    prints = data["specimenLabels"]
    assert len(prints) >= 3
    listed = client.get(f"/api/labels/specimens?patientId={prints[0]['patientId']}", headers=headers).json()
    assert listed and listed[0]["labels"][0]["code"].startswith("E")
    assert data["sterilizationCycles"] == []  # no autoclave in the generalist's plan


def test_a_psychologist_demo_has_neither(client: TestClient) -> None:
    headers = start(client, specialty="psychologue")
    data = client.get("/api/practice/export", headers=headers).json()
    assert data["sterilizationCycles"] == [] and data["specimenLabels"] == []
