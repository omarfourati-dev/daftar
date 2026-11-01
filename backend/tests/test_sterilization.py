"""Sterilisation cycles, packs and their traceability (spec stock-hygiène 3, 5.3, 7, 8).

T0 is Friday 30.10.2026 09:00 in Tunis.
"""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import assert_problem

Factory = Callable[..., Any]


@pytest.fixture
def cab(make_practice: Factory, make_user: Factory, auth_headers: Factory, make_patient: Factory,
        make_appointment: Factory, clock: Any) -> Any:
    p = make_practice("Cabinet Sfax", specialty="dentiste", practitioners=["Dr. Fadoua"])
    sami = make_patient(p, first_name="Sami", last_name="Trabelsi")
    return type("Cab", (), {
        "practice": p,
        "owner": auth_headers(make_user(p, "owner", name="Dr. Fadoua Bellaj")),
        "assistant": auth_headers(make_user(p, "assistant", name="Nisrine Hamza")),
        "dentist": auth_headers(make_user(p, "dentist", name="Dr. Karim Jaziri")),
        "patient": sami,
        "appointment": make_appointment(sami, starts_at=clock.now(), practitioner_id=p.practitioners[0].id),
    })


def autoclave(client: TestClient, headers: dict[str, str], name: str = "Autoclave Melag") -> dict[str, Any]:
    res = client.post("/api/hygiene/equipment", json={"name": name, "kind": "autoclave"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def cycle(client: TestClient, headers: dict[str, str], equipment_id: int, **values: Any) -> dict[str, Any]:
    body = {"equipmentId": equipment_id, "program": "134 °C – 18 min", "result": "ok",
            "packs": [{"content": "Kit examen", "packaging": "sachet", "quantity": 2}], **values}
    res = client.post("/api/hygiene/cycles", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def use(client: TestClient, headers: dict[str, str], code: str, **values: Any) -> Any:
    return client.post("/api/hygiene/pack-uses", json={"code": code, **values}, headers=headers)


# --- settings ---------------------------------------------------------------------------------------------------


def test_label_settings_have_defaults_and_the_desk_chooses_its_formats(client: TestClient, cab: Any) -> None:
    res = client.get("/api/labels/settings", headers=cab.dentist)
    assert res.status_code == 200, res.text
    assert res.json() == {"formats": {"sterile": "roll62", "specimen": "roll62"},
                          "shelfLifeDays": {"sachet": 90, "double_sachet": 90, "conteneur": 90, "champ": 90}}
    res = client.patch("/api/labels/settings", json={"formats": {"specimen": "a4_3x8"}, "shelfLifeDays": {"sachet": 30}},
                       headers=cab.assistant)
    assert res.status_code == 200, res.text
    assert res.json()["formats"] == {"sterile": "roll62", "specimen": "a4_3x8"}
    assert res.json()["shelfLifeDays"]["sachet"] == 30 and res.json()["shelfLifeDays"]["champ"] == 90
    log = client.get("/api/audit-log?entity=label_settings", headers=cab.owner).json()
    assert log[0]["action"] == "update" and log[0]["userName"] == "Nisrine Hamza"
    assert log[0]["before"] == {"formatSpecimen": "roll62", "shelfLifeSachet": 90}
    assert log[0]["after"] == {"formatSpecimen": "a4_3x8", "shelfLifeSachet": 30}
    for body in ({"formats": {"sterile": "fax"}}, {"shelfLifeDays": {"sachet": 0}}, {"shelfLifeDays": {"sachet": 1826}},
                 {"shelfLifeDays": {"boite": 30}}):
        assert_problem(client.patch("/api/labels/settings", json=body, headers=cab.owner), 422, "validation")
    assert_problem(client.patch("/api/labels/settings", json={"formats": {"sterile": "a4_3x8"}}, headers=cab.dentist), 403,
                   "forbidden")


# --- cycles -----------------------------------------------------------------------------------------------------


def test_the_form_of_a_new_cycle_knows_the_autoclaves_programs_and_contents(client: TestClient, cab: Any) -> None:
    gear = autoclave(client, cab.assistant)
    client.post("/api/hygiene/equipment", json={"name": "Fauteuil", "kind": "fauteuil"}, headers=cab.assistant)
    setup = client.get("/api/hygiene/cycles/setup", headers=cab.dentist).json()
    assert setup["autoclaves"] == [{"id": gear["id"], "name": "Autoclave Melag", "labelCode": None, "nextNumber": 1,
                                    "lastRunAt": None}]
    assert setup["programs"][:3] == ["134 °C – 18 min", "134 °C – 3,5 min", "121 °C – 20 min"]
    assert {"Kit examen", "Kit extraction"} <= set(setup["contents"])
    cycle(client, cab.assistant, gear["id"], number=412, program="134 °C – 5 min",
          packs=[{"content": "Plateau orthodontie", "packaging": "conteneur", "quantity": 1}])
    setup = client.get("/api/hygiene/cycles/setup", headers=cab.assistant).json()
    assert (setup["autoclaves"][0]["labelCode"], setup["autoclaves"][0]["nextNumber"]) == ("A1", 413)
    assert setup["programs"][0] == "134 °C – 5 min" and setup["contents"][0] == "Plateau orthodontie"


def test_a_conforme_cycle_gives_numbered_packs_with_their_date(client: TestClient, cab: Any) -> None:
    client.patch("/api/labels/settings", json={"shelfLifeDays": {"sachet": 30}}, headers=cab.owner)
    gear = autoclave(client, cab.assistant)
    made = cycle(client, cab.assistant, gear["id"], number=412, packs=[
        {"content": "Kit examen", "packaging": "sachet", "quantity": 3},
        {"content": "Kit extraction", "packaging": "double_sachet", "quantity": 1},
    ])
    assert {k: made[k] for k in ("equipmentName", "labelCode", "number", "runAt", "program", "result", "packCount",
                                 "performedBy", "initials")} == {
        "equipmentName": "Autoclave Melag", "labelCode": "A1", "number": 412, "runAt": "2026-10-30T09:00:00+01:00",
        "program": "134 °C – 18 min", "result": "ok", "packCount": 4, "performedBy": "Nisrine Hamza", "initials": "NH"}
    assert [(p["code"], p["content"], p["packaging"], p["expiresOn"], p["state"]) for p in made["packs"]] == [
        ("A1-0412-01", "Kit examen", "sachet", "2026-11-29", "usable"),
        ("A1-0412-02", "Kit examen", "sachet", "2026-11-29", "usable"),
        ("A1-0412-03", "Kit examen", "sachet", "2026-11-29", "usable"),
        ("A1-0412-04", "Kit extraction", "double_sachet", "2027-01-28", "usable"),
    ]
    # the next cycle of this autoclave counts on; a second autoclave gets its own code
    assert cycle(client, cab.dentist, gear["id"])["packs"][0]["code"] == "A1-0413-01"
    other = autoclave(client, cab.assistant, "Autoclave 2")
    assert cycle(client, cab.assistant, other["id"])["packs"][0]["code"] == "A2-0001-01"
    listed = {e["id"]: e for e in client.get("/api/hygiene/equipment", headers=cab.owner).json()}
    assert (listed[gear["id"]]["labelCode"], listed[gear["id"]]["cycles"]) == ("A1", 2)


def test_a_non_conforme_cycle_gives_no_labels(client: TestClient, cab: Any) -> None:
    gear = autoclave(client, cab.assistant)
    failed = cycle(client, cab.assistant, gear["id"], result="not_ok", packs=[], packCount=6,
                   note="Indicateur non viré")
    assert (failed["result"], failed["packCount"], failed["packs"], failed["note"]) == ("not_ok", 6, [], "Indicateur non viré")
    assert_problem(client.post("/api/hygiene/cycles", json={
        "equipmentId": gear["id"], "result": "not_ok", "packs": [{"content": "Kit", "quantity": 1}]}, headers=cab.assistant),
        422, "cycle_not_ok")
    # an empty test cycle (Bowie-Dick) is conforme without packs
    assert cycle(client, cab.assistant, gear["id"], packs=[], program="Bowie-Dick")["packCount"] == 0


def test_a_new_cycle_is_checked(client: TestClient, cab: Any, clock: Any) -> None:
    gear = autoclave(client, cab.assistant)
    chair = client.post("/api/hygiene/equipment", json={"name": "Fauteuil", "kind": "fauteuil"}, headers=cab.assistant).json()
    cycle(client, cab.assistant, gear["id"], number=7)

    def refused(status: int, code: str, **values: Any) -> None:
        body = {"equipmentId": gear["id"], "result": "ok", "packs": [], **values}
        assert_problem(client.post("/api/hygiene/cycles", json=body, headers=cab.assistant), status, code)

    refused(409, "cycle_number_taken", number=7)
    refused(422, "not_an_autoclave", equipmentId=chair["id"])
    refused(422, "invalid_equipment", equipmentId=999_999)
    refused(422, "run_in_future", runAt=(clock.now() + timedelta(hours=1)).isoformat())
    refused(422, "run_too_old", runAt=(clock.now() - timedelta(days=400)).isoformat())
    refused(422, "too_many_packs", packs=[{"content": "Kit", "quantity": 60}, {"content": "Fraises", "quantity": 40}])
    refused(422, "validation", packs=[{"content": "", "quantity": 1}])
    refused(422, "validation", packs=[{"content": "Kit", "quantity": 0}])
    refused(422, "validation", packs=[{"content": "Kit", "packaging": "boite", "quantity": 1}])
    refused(422, "validation", result="maybe")
    client.patch(f"/api/hygiene/equipment/{gear['id']}", json={"active": False}, headers=cab.owner)
    refused(422, "equipment_inactive")
    # a cycle of yesterday is entered afterwards (forgotten at the time); its packs count from that day
    client.patch(f"/api/hygiene/equipment/{gear['id']}", json={"active": True}, headers=cab.owner)
    late = cycle(client, cab.assistant, gear["id"], runAt="2026-10-29T17:30:00+01:00")
    assert late["packs"][0]["expiresOn"] == "2027-01-27"


def test_the_list_of_cycles_shows_the_period_newest_first(client: TestClient, cab: Any, clock: Any) -> None:
    gear = autoclave(client, cab.assistant)
    old = cycle(client, cab.assistant, gear["id"], runAt="2026-09-01T10:00:00+01:00")
    cycle(client, cab.assistant, gear["id"], runAt="2026-10-29T10:00:00+01:00")
    last = cycle(client, cab.assistant, gear["id"])
    listed = client.get("/api/hygiene/cycles", headers=cab.dentist).json()
    assert (listed["from"], listed["to"]) == ("2026-10-01", "2026-10-30")
    assert [c["id"] for c in listed["cycles"]][0] == last["id"] and old["id"] not in [c["id"] for c in listed["cycles"]]
    assert len(client.get("/api/hygiene/cycles?from=2026-09-01&to=2026-10-30", headers=cab.dentist).json()["cycles"]) == 3
    assert client.get(f"/api/hygiene/cycles?equipmentId={gear['id']}&from=2026-09-01", headers=cab.dentist).json()["cycles"]
    assert_problem(client.get("/api/hygiene/cycles?from=2025-01-01&to=2026-10-30", headers=cab.dentist), 422, "invalid_range")
    assert client.get(f"/api/hygiene/cycles/{last['id']}", headers=cab.dentist).json() == last


# --- traceability -------------------------------------------------------------------------------------------------


def test_a_pack_is_used_for_the_patient_of_the_appointment_once(client: TestClient, cab: Any) -> None:
    gear = autoclave(client, cab.assistant)
    cycle(client, cab.assistant, gear["id"], number=412)
    res = use(client, cab.dentist, "a1 0412 01", appointmentId=cab.appointment.id)  # typed as on the label
    assert res.status_code == 201, res.text
    used = res.json()
    assert {k: used[k] for k in ("code", "content", "patientId", "patientName", "appointmentId", "usedBy", "undoable")} == {
        "code": "A1-0412-01", "content": "Kit examen", "patientId": cab.patient.id, "patientName": "Sami Trabelsi",
        "appointmentId": cab.appointment.id, "usedBy": "Dr. Karim Jaziri", "undoable": True}
    assert used["cycle"] == {"id": used["cycle"]["id"], "labelCode": "A1", "number": 412, "equipmentName": "Autoclave Melag",
                             "runAt": "2026-10-30T09:00:00+01:00", "result": "ok"}
    again = assert_problem(use(client, cab.assistant, "A1-0412-01", patientId=cab.patient.id), 409, "pack_used")
    assert again["patientName"] == "Sami Trabelsi" and again["usedAt"] == "2026-10-30T09:00:00+01:00"
    listed = client.get(f"/api/hygiene/pack-uses?appointmentId={cab.appointment.id}", headers=cab.assistant).json()
    assert [u["code"] for u in listed] == ["A1-0412-01"] and listed[0]["undoable"] is False  # somebody else's
    # without an appointment, from the patient file
    assert use(client, cab.assistant, "A1-0412-02", patientId=cab.patient.id).status_code == 201
    state = client.get("/api/hygiene/cycles", headers=cab.assistant).json()["cycles"][0]["packs"]
    assert [p["state"] for p in state] == ["used", "used"]
    assert state[0]["use"]["patientName"] == "Sami Trabelsi"


def test_expired_unknown_and_not_sterile_packs_are_refused_with_a_clear_reason(
    client: TestClient, cab: Any, clock: Any,
) -> None:
    client.patch("/api/labels/settings", json={"shelfLifeDays": {"sachet": 1}}, headers=cab.owner)
    gear = autoclave(client, cab.assistant)
    cycle(client, cab.assistant, gear["id"], number=1, runAt="2026-10-28T10:00:00+01:00")
    expired = assert_problem(use(client, cab.assistant, "A1-0001-01", appointmentId=cab.appointment.id), 422, "pack_expired")
    assert expired["expiresOn"] == "2026-10-29" and "périmé" in expired["detail"]
    assert_problem(use(client, cab.assistant, "A1-9999-01", appointmentId=cab.appointment.id), 422, "pack_unknown")
    assert_problem(use(client, cab.assistant, "kit", appointmentId=cab.appointment.id), 422, "pack_unknown")
    fresh = cycle(client, cab.assistant, gear["id"], number=2)
    res = client.patch(f"/api/hygiene/cycles/{fresh['id']}", json={"result": "not_ok", "reason": "Indicateur biologique positif"},
                       headers=cab.owner)
    assert res.status_code == 200, res.text
    assert [p["state"] for p in res.json()["packs"]] == ["not_sterile", "not_sterile"]
    refused = assert_problem(use(client, cab.assistant, "A1-0002-01", appointmentId=cab.appointment.id), 422,
                             "pack_not_sterile")
    assert "non conforme" in refused["detail"]
    assert_problem(use(client, cab.assistant, "A1-0002-01"), 422, "validation")  # for whom?


def test_the_desk_finds_packs_by_what_it_types(client: TestClient, cab: Any) -> None:
    gear = autoclave(client, cab.assistant)
    old = cycle(client, cab.assistant, gear["id"], number=411, runAt="2026-10-29T10:00:00+01:00",
                packs=[{"content": "Kit extraction", "quantity": 1}])
    cycle(client, cab.assistant, gear["id"], number=412, packs=[{"content": "Kit examen", "quantity": 3}])
    use(client, cab.assistant, "A1-0412-01", appointmentId=cab.appointment.id)
    found = client.get("/api/hygiene/packs", headers=cab.dentist).json()  # nothing typed: what can be used, newest first
    assert [p["code"] for p in found] == ["A1-0412-02", "A1-0412-03", old["packs"][0]["code"]]
    assert found[0]["state"] == "usable" and found[0]["number"] == 412 and found[0]["labelCode"] == "A1"
    assert [p["code"] for p in client.get("/api/hygiene/packs?q=412-3", headers=cab.dentist).json()] == ["A1-0412-03"]
    by_cycle = client.get("/api/hygiene/packs?q=0412", headers=cab.dentist).json()
    assert [p["code"] for p in by_cycle] == ["A1-0412-02", "A1-0412-03", "A1-0412-01"]  # usable first, then the used one
    assert by_cycle[-1]["state"] == "used"
    assert [p["code"] for p in client.get("/api/hygiene/packs?q=extrac", headers=cab.dentist).json()] == ["A1-0411-01"]


def test_a_use_is_taken_back_by_its_author_soon_or_by_the_owner_with_a_reason(
    client: TestClient, cab: Any, clock: Any,
) -> None:
    gear = autoclave(client, cab.assistant)
    cycle(client, cab.assistant, gear["id"], number=412, packs=[{"content": "Kit examen", "quantity": 3}])
    first = use(client, cab.assistant, "A1-0412-01", appointmentId=cab.appointment.id).json()
    assert client.delete(f"/api/hygiene/pack-uses/{first['id']}", headers=cab.assistant).status_code == 204
    assert use(client, cab.assistant, "A1-0412-01", appointmentId=cab.appointment.id).status_code == 201  # usable again
    second = use(client, cab.assistant, "A1-0412-02", appointmentId=cab.appointment.id).json()
    clock.advance(minutes=16)
    assert_problem(client.delete(f"/api/hygiene/pack-uses/{second['id']}", headers=cab.assistant), 403, "undo_too_late")
    assert_problem(client.request("DELETE", f"/api/hygiene/pack-uses/{second['id']}", json={}, headers=cab.owner), 422,
                   "reason_required")
    res = client.request("DELETE", f"/api/hygiene/pack-uses/{second['id']}", json={"reason": "Mauvais patient"},
                         headers=cab.owner)
    assert res.status_code == 204, res.text
    log = client.get("/api/audit-log?entity=sterile_pack_use", headers=cab.owner).json()
    assert [e["reason"] for e in log] == ["Mauvais patient", ""]
    assert log[0]["before"] == {"code": "A1-0412-02", "content": "Kit examen", "patient": "Sami Trabelsi",
                                "usedAt": "2026-10-30T09:00:00+01:00", "usedBy": "Nisrine Hamza"}


def test_the_owner_traces_a_pack_to_its_patient_and_a_patient_to_his_packs(
    client: TestClient, cab: Any, make_patient: Factory,
) -> None:
    gear = autoclave(client, cab.assistant)
    made = cycle(client, cab.assistant, gear["id"], number=412, packs=[{"content": "Kit examen", "quantity": 2}])
    use(client, cab.assistant, "A1-0412-01", appointmentId=cab.appointment.id)
    res = client.get("/api/hygiene/trace?code=A1-0412-01", headers=cab.owner)
    assert res.status_code == 200, res.text
    traced = res.json()
    assert traced["pack"]["code"] == "A1-0412-01" and traced["pack"]["cycleId"] == made["id"]
    assert traced["use"]["patientName"] == "Sami Trabelsi" and traced["use"]["appointmentId"] == cab.appointment.id
    assert client.get("/api/hygiene/trace?code=a1-412-2", headers=cab.owner).json()["use"] is None
    assert_problem(client.get("/api/hygiene/trace?code=A1-0999-01", headers=cab.owner), 404, "not_found")
    patient = client.get(f"/api/hygiene/trace?patientId={cab.patient.id}", headers=cab.owner).json()
    assert patient["patient"] == {"id": cab.patient.id, "name": "Sami Trabelsi"}
    assert [u["code"] for u in patient["uses"]] == ["A1-0412-01"]
    nobody = make_patient(cab.practice)
    assert client.get(f"/api/hygiene/trace?patientId={nobody.id}", headers=cab.owner).json()["uses"] == []
    assert_problem(client.get("/api/hygiene/trace", headers=cab.owner), 422, "validation")
    assert [u["code"] for u in client.get(f"/api/hygiene/pack-uses?patientId={cab.patient.id}", headers=cab.owner).json()] == [
        "A1-0412-01"]


def test_the_owner_corrects_or_deletes_a_cycle_with_a_reason(client: TestClient, cab: Any) -> None:
    gear = autoclave(client, cab.assistant)
    made = cycle(client, cab.assistant, gear["id"], number=412)
    res = client.patch(f"/api/hygiene/cycles/{made['id']}", json={"program": "134 °C – 3,5 min", "reason": "Faute de frappe"},
                       headers=cab.owner)
    assert res.status_code == 200 and res.json()["program"] == "134 °C – 3,5 min"
    assert_problem(client.patch(f"/api/hygiene/cycles/{made['id']}", json={"program": "x"}, headers=cab.owner), 422,
                   "validation")
    use(client, cab.assistant, "A1-0412-01", appointmentId=cab.appointment.id)
    assert_problem(client.request("DELETE", f"/api/hygiene/cycles/{made['id']}", json={"reason": "Doublon"},
                                  headers=cab.owner), 409, "cycle_in_use")
    spare = cycle(client, cab.assistant, gear["id"], number=413)
    assert_problem(client.request("DELETE", f"/api/hygiene/cycles/{spare['id']}", json={}, headers=cab.owner), 422,
                   "validation")
    assert client.request("DELETE", f"/api/hygiene/cycles/{spare['id']}", json={"reason": "Saisi deux fois"},
                          headers=cab.owner).status_code == 204
    log = client.get("/api/audit-log?entity=sterilization_cycle", headers=cab.owner).json()
    assert [(e["action"], e["reason"]) for e in log] == [("delete", "Saisi deux fois"), ("update", "Faute de frappe")]
    assert log[1]["before"] == {"cycle": "A1 n° 412", "program": "134 °C – 18 min"}
    assert log[1]["after"] == {"program": "134 °C – 3,5 min"}
    assert log[0]["before"]["cycle"] == "A1 n° 413" and log[0]["before"]["packCount"] == 2
    # an autoclave with cycles stays in the register: deactivate it instead
    assert_problem(client.delete(f"/api/hygiene/equipment/{gear['id']}", headers=cab.owner), 409, "equipment_in_use")


def test_the_practice_export_contains_the_sterilisation_tables(client: TestClient, cab: Any) -> None:
    gear = autoclave(client, cab.assistant)
    cycle(client, cab.assistant, gear["id"])
    use(client, cab.assistant, "A1-0001-01", appointmentId=cab.appointment.id)
    data = client.get("/api/practice/export", headers=cab.owner).json()
    assert len(data["sterilizationCycles"]) == 1 and len(data["sterilePacks"]) == 2
    assert data["sterilePackUses"][0]["usedByName"] == "Nisrine Hamza"
    assert data["practice"]["labelSettings"] == {}


# --- every id stays in its practice, every role keeps to its rights (DoD 3) -----------------------------------------


def test_every_id_of_another_practice_is_not_found(client: TestClient, cab: Any, make_user: Factory, auth_headers: Factory,
                                                   make_patient: Factory, make_appointment: Factory) -> None:
    gear = autoclave(client, cab.assistant)
    made = cycle(client, cab.assistant, gear["id"])
    used = use(client, cab.assistant, "A1-0001-01", appointmentId=cab.appointment.id).json()
    stranger_user = make_user(role="owner")
    stranger = auth_headers(stranger_user)
    for method, path, body in [
        ("GET", f"/api/hygiene/cycles/{made['id']}", None),
        ("PATCH", f"/api/hygiene/cycles/{made['id']}", {"note": "x", "reason": "x"}),
        ("DELETE", f"/api/hygiene/cycles/{made['id']}", {"reason": "x"}),
        ("DELETE", f"/api/hygiene/pack-uses/{used['id']}", {"reason": "x"}),
        ("GET", "/api/hygiene/trace?code=A1-0001-01", None),
        ("GET", f"/api/hygiene/trace?patientId={cab.patient.id}", None),
    ]:
        assert_problem(client.request(method, path, json=body, headers=stranger), 404, "not_found")
    assert_problem(use(client, stranger, "A1-0001-02", appointmentId=cab.appointment.id), 422, "invalid_appointment")
    assert_problem(use(client, stranger, "A1-0001-02", patientId=cab.patient.id), 422, "invalid_patient")
    their = make_patient(type("P", (), {"id": stranger_user.practice_id}))
    assert_problem(use(client, stranger, "A1-0001-02", patientId=their.id), 422, "pack_unknown")  # our pack, their patient
    assert_problem(use(client, cab.assistant, "A1-0001-02", patientId=their.id), 422, "invalid_patient")
    other_patient = make_patient(cab.practice)
    assert_problem(use(client, cab.assistant, "A1-0001-02", appointmentId=cab.appointment.id, patientId=other_patient.id),
                   422, "invalid_patient")
    assert_problem(client.post("/api/hygiene/cycles", json={"equipmentId": gear["id"], "result": "ok"}, headers=stranger),
                   422, "invalid_equipment")
    assert client.get("/api/hygiene/cycles?from=2026-10-01", headers=stranger).json()["cycles"] == []
    assert client.get("/api/hygiene/packs", headers=stranger).json() == []
    assert client.get(f"/api/hygiene/pack-uses?appointmentId={cab.appointment.id}", headers=stranger).json() == []
    assert client.get("/api/hygiene/cycles/setup", headers=stranger).json()["autoclaves"] == []


def test_every_endpoint_keeps_to_the_roles(client: TestClient, cab: Any, make_user: Factory, auth_headers: Factory) -> None:
    gear = autoclave(client, cab.assistant)
    made = cycle(client, cab.assistant, gear["id"])
    used = use(client, cab.assistant, "A1-0001-01", appointmentId=cab.appointment.id).json()
    for headers in (cab.assistant, cab.dentist):
        for method, path, body in [
            ("PATCH", f"/api/hygiene/cycles/{made['id']}", {"note": "x", "reason": "x"}),
            ("DELETE", f"/api/hygiene/cycles/{made['id']}", {"reason": "x"}),
            ("GET", "/api/hygiene/trace?code=A1-0001-01", None),
            ("GET", f"/api/hygiene/pack-uses?patientId={cab.patient.id}", None),
        ]:
            assert_problem(client.request(method, path, json=body, headers=headers), 403, "forbidden")
    assert_problem(client.request("DELETE", f"/api/hygiene/pack-uses/{used['id']}", headers=cab.dentist), 403, "forbidden")
    assert_problem(client.patch("/api/labels/settings", json={}, headers=cab.dentist), 403, "forbidden")
    admin = auth_headers(make_user(role="admin"))
    for method, path in [
        ("GET", "/api/labels/settings"), ("PATCH", "/api/labels/settings"), ("GET", "/api/hygiene/cycles"),
        ("GET", "/api/hygiene/cycles/setup"), ("POST", "/api/hygiene/cycles"), ("GET", f"/api/hygiene/cycles/{made['id']}"),
        ("PATCH", f"/api/hygiene/cycles/{made['id']}"), ("DELETE", f"/api/hygiene/cycles/{made['id']}"),
        ("GET", "/api/hygiene/packs"), ("POST", "/api/hygiene/pack-uses"),
        ("GET", f"/api/hygiene/pack-uses?appointmentId={cab.appointment.id}"),
        ("DELETE", f"/api/hygiene/pack-uses/{used['id']}"), ("GET", "/api/hygiene/trace?code=A1-0001-01"),
    ]:
        assert_problem(client.request(method, path, headers=admin), 403, "forbidden")
        assert_problem(client.request(method, path), 401, "unauthorized")
