"""Specimen labels (spec stock-hygiène 6): the labels of the tubes and a small proof – who, when, which, how many."""

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import assert_problem

Factory = Callable[..., Any]


@pytest.fixture
def cab(make_practice: Factory, make_user: Factory, auth_headers: Factory, make_patient: Factory,
        make_appointment: Factory, clock: Any) -> Any:
    p = make_practice("Cabinet Tunis", specialty="generaliste", practitioners=["Dr. Amira"])
    sami = make_patient(p, first_name="Sami", last_name="Trabelsi", birth_year=1978, birth_date=date(1978, 3, 12))
    return type("Cab", (), {
        "practice": p,
        "owner": auth_headers(make_user(p, "owner", name="Dr. Amira Ben Salem")),
        "assistant": auth_headers(make_user(p, "assistant", name="Nisrine Hamza")),
        "dentist": auth_headers(make_user(p, "dentist", name="Dr. Karim")),
        "patient": sami,
        "appointment": make_appointment(sami, starts_at=clock.now(), practitioner_id=p.practitioners[0].id),
    })


def specimens(client: TestClient, headers: dict[str, str], patient_id: int, **values: Any) -> Any:
    body = {"patientId": patient_id, "items": [{"kind": "edta", "count": 2}, {"kind": "urine", "count": 1}], **values}
    return client.post("/api/labels/specimens", json=body, headers=headers)


def test_the_desk_prints_the_tubes_of_a_patient(client: TestClient, cab: Any) -> None:
    res = specimens(client, cab.assistant, cab.patient.id, appointmentId=cab.appointment.id, collectedBy="Dr. Amira")
    assert res.status_code == 201, res.text
    made = res.json()
    n = made["id"]
    assert made["patient"] == {"id": cab.patient.id, "firstName": "Sami", "lastName": "Trabelsi", "birthDate": "1978-03-12",
                               "birthYear": 1978}
    assert made["labels"] == [
        {"code": f"E{n}-01", "kind": "edta", "label": ""},
        {"code": f"E{n}-02", "kind": "edta", "label": ""},
        {"code": f"E{n}-03", "kind": "urine", "label": ""},
    ]
    assert (made["labelCount"], made["collectedAt"], made["collectedBy"], made["printedBy"], made["printedAt"]) == (
        3, "2026-10-30T09:00:00+01:00", "Dr. Amira", "Nisrine Hamza", "2026-10-30T09:00:00+01:00")
    assert made["appointmentId"] == cab.appointment.id
    assert client.get(f"/api/labels/specimens/{n}", headers=cab.dentist).json() == made  # printed again: same codes
    other = specimens(client, cab.dentist, cab.patient.id, items=[{"kind": "autre", "count": 1, "label": "Liquide pleural"}],
                      collectedAt="2026-10-30T08:40:00+01:00").json()
    assert other["labels"] == [{"code": f"E{other['id']}-01", "kind": "autre", "label": "Liquide pleural"}]
    assert other["appointmentId"] is None and other["collectedAt"] == "2026-10-30T08:40:00+01:00"
    proof = client.get(f"/api/labels/specimens?patientId={cab.patient.id}", headers=cab.assistant).json()
    assert [(p["id"], p["printedBy"], p["labelCount"]) for p in proof] == [(other["id"], "Dr. Karim", 1), (n, "Nisrine Hamza", 3)]


def test_a_patient_without_birth_date_shows_the_year(client: TestClient, cab: Any, make_patient: Factory) -> None:
    young = make_patient(cab.practice, first_name="Lina", last_name="Ayari", birth_year=2015)
    made = specimens(client, cab.assistant, young.id).json()
    assert (made["patient"]["birthDate"], made["patient"]["birthYear"]) == (None, 2015)


def test_a_print_is_checked(client: TestClient, cab: Any, clock: Any, make_patient: Factory) -> None:
    def refused(code: str, **values: Any) -> None:
        assert_problem(specimens(client, cab.assistant, cab.patient.id, **values), 422, code)

    refused("specimen_label_required", items=[{"kind": "autre", "count": 1}])
    refused("too_many_labels", items=[{"kind": "edta", "count": 20}, {"kind": "sec", "count": 20}, {"kind": "urine", "count": 9}])
    refused("validation", items=[])
    refused("validation", items=[{"kind": "edta", "count": 0}])
    refused("validation", items=[{"kind": "salive", "count": 1}])
    refused("invalid_collected_at", collectedAt=(clock.now() + timedelta(days=2)).isoformat())
    refused("invalid_collected_at", collectedAt=(clock.now() - timedelta(days=40)).isoformat())
    refused("invalid_appointment", appointmentId=999_999)
    someone_else = make_patient(cab.practice)
    assert_problem(specimens(client, cab.assistant, someone_else.id, appointmentId=cab.appointment.id), 422,
                   "invalid_appointment")  # the appointment of another patient
    assert_problem(specimens(client, cab.assistant, 999_999), 422, "invalid_patient")
    # "autre" keeps its name, the other kinds never carry one
    made = specimens(client, cab.assistant, cab.patient.id, items=[{"kind": "edta", "count": 1, "label": "ignoré"}]).json()
    assert made["labels"][0]["label"] == "" and made["items"] == [{"kind": "edta", "count": 1, "label": ""}]


def test_the_export_contains_the_prints_and_deleting_the_patient_removes_them(client: TestClient, cab: Any) -> None:
    specimens(client, cab.assistant, cab.patient.id)
    data = client.get("/api/practice/export", headers=cab.owner).json()
    assert data["specimenLabels"][0]["labelCount"] == 3 and data["specimenLabels"][0]["printedByName"] == "Nisrine Hamza"
    assert data["patients"][0]["birthDate"] == "1978-03-12"
    assert client.delete(f"/api/patients/{cab.patient.id}", headers=cab.owner).status_code == 204
    assert client.get("/api/practice/export", headers=cab.owner).json()["specimenLabels"] == []


def test_ids_of_another_practice_and_roles(client: TestClient, cab: Any, make_user: Factory, auth_headers: Factory) -> None:
    made = specimens(client, cab.assistant, cab.patient.id).json()
    stranger = auth_headers(make_user(role="owner"))
    assert_problem(client.get(f"/api/labels/specimens/{made['id']}", headers=stranger), 404, "not_found")
    assert_problem(specimens(client, stranger, cab.patient.id), 422, "invalid_patient")
    assert client.get(f"/api/labels/specimens?patientId={cab.patient.id}", headers=stranger).json() == []
    admin = auth_headers(make_user(role="admin"))
    for method, path in [("POST", "/api/labels/specimens"), ("GET", f"/api/labels/specimens/{made['id']}"),
                         ("GET", f"/api/labels/specimens?patientId={cab.patient.id}")]:
        assert_problem(client.request(method, path, headers=admin), 403, "forbidden")
        assert_problem(client.request(method, path), 401, "unauthorized")
