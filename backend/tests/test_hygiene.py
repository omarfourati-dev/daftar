"""Hygiene API (spec stock-hygiène 3, 5.1, 5.2, 8): equipment, tasks, "Hygiène du jour", proofs, history."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import assert_problem

Factory = Callable[..., Any]
#: T0 is Friday 30.10.2026 09:00 in Tunis; the practice is open Monday–Saturday (database default).


@pytest.fixture
def cab(make_practice: Factory, make_user: Factory, auth_headers: Factory) -> Any:
    p = make_practice("Cabinet Sfax", specialty="dentiste")
    return type("Cab", (), {
        "practice": p,
        "owner": auth_headers(make_user(p, "owner", name="Dr. Fadoua")),
        "assistant": auth_headers(make_user(p, "assistant", name="Nisrine")),
        "dentist": auth_headers(make_user(p, "dentist", name="Dr. Karim")),
    })


def task(client: TestClient, headers: dict[str, str], title: str = "Purge des conduits", **values: Any) -> dict[str, Any]:
    res = client.post("/api/hygiene/tasks", json={"title": title, "frequency": "daily", **values}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def tick(client: TestClient, headers: dict[str, str], task_id: int, **values: Any) -> Any:
    return client.post(f"/api/hygiene/tasks/{task_id}/done", json=values, headers=headers)


def today(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    res = client.get("/api/hygiene/today", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# --- equipment and tasks ------------------------------------------------------------------------------------------


def test_the_assistant_sets_up_equipment_and_tasks(client: TestClient, cab: Any) -> None:
    res = client.post("/api/hygiene/equipment", json={"name": "Autoclave", "kind": "autoclave", "serialNumber": "SN-44"},
                      headers=cab.assistant)
    assert res.status_code == 201, res.text
    autoclave = res.json()
    assert autoclave == {"id": autoclave["id"], "name": "Autoclave", "kind": "autoclave", "serialNumber": "SN-44", "note": "",
                         "active": True, "tasks": 0}
    created = task(client, cab.assistant, "Test Bowie-Dick", frequency="weekly", weekday=1, equipmentId=autoclave["id"],
                   instructions="Premier cycle de la semaine")
    assert created["equipmentName"] == "Autoclave" and created["startsOn"] == "2026-10-30"
    assert created["nextDueOn"] == "2026-11-02"  # next Monday
    assert (created["weekday"], created["intervalDays"], created["active"]) == (1, None, True)
    assert client.get("/api/hygiene/equipment", headers=cab.dentist).json()[0]["tasks"] == 1
    res = client.patch(f"/api/hygiene/tasks/{created['id']}", json={"frequency": "every_n_days", "intervalDays": 10},
                       headers=cab.owner)
    assert res.status_code == 200, res.text
    assert (res.json()["frequency"], res.json()["weekday"], res.json()["intervalDays"]) == ("every_n_days", None, 10)
    assert_problem(client.delete(f"/api/hygiene/equipment/{autoclave['id']}", headers=cab.owner), 409, "equipment_in_use")


@pytest.mark.parametrize(
    ("body", "code"),
    [({"title": "X", "frequency": "weekly"}, "invalid_rhythm"),
     ({"title": "X", "frequency": "every_n_days", "intervalDays": 1}, "invalid_rhythm"),
     ({"title": "X", "frequency": "daily", "weekday": 3}, "invalid_rhythm"),
     ({"title": "X", "frequency": "hourly"}, "validation"),
     ({"title": "", "frequency": "daily"}, "validation"),
     ({"title": "X", "frequency": "daily", "equipmentId": 999_999}, "invalid_equipment")],
)
def test_task_validation(client: TestClient, cab: Any, body: dict[str, Any], code: str) -> None:
    assert_problem(client.post("/api/hygiene/tasks", json=body, headers=cab.assistant), 422, code)


def test_setup_is_for_assistant_and_owner_and_ids_stay_in_their_practice(
    client: TestClient, cab: Any, make_user: Factory, auth_headers: Factory
) -> None:
    assert_problem(client.post("/api/hygiene/tasks", json={"title": "X", "frequency": "daily"}, headers=cab.dentist), 403,
                   "forbidden")
    assert_problem(client.post("/api/hygiene/equipment", json={"name": "X"}, headers=cab.dentist), 403, "forbidden")
    assert_problem(client.post("/api/hygiene/starter", headers=cab.dentist), 403, "forbidden")
    mine = task(client, cab.assistant)
    stranger = auth_headers(make_user(role="owner"))
    assert client.get("/api/hygiene/tasks", headers=stranger).json() == []
    assert today(client, stranger)["items"] == []
    assert_problem(client.patch(f"/api/hygiene/tasks/{mine['id']}", json={"title": "Y"}, headers=stranger), 404, "not_found")
    assert_problem(tick(client, stranger, mine["id"]), 404, "not_found")
    assert_problem(client.get("/api/hygiene/today"), 401, "unauthorized")


def test_start_plan_of_the_specialty_once(client: TestClient, cab: Any) -> None:
    res = client.post("/api/hygiene/starter", headers=cab.assistant)
    assert res.status_code == 200, res.text
    assert res.json()["equipment"] >= 5 and res.json()["tasks"] >= 8
    tasks = {t["title"]: t for t in client.get("/api/hygiene/tasks", headers=cab.assistant).json()}
    assert tasks["Test Bowie-Dick / Hélix de l’autoclave"]["equipmentName"] == "Autoclave"
    assert tasks["Maintenance de l’autoclave"]["startsOn"] == "2026-11-29"  # a month to plan it
    assert client.post("/api/hygiene/starter", headers=cab.assistant).json() == {"equipment": 0, "tasks": 0}


# --- Hygiène du jour ------------------------------------------------------------------------------------------------


def test_today_lists_overdue_first_then_due_then_done(client: TestClient, cab: Any, clock: Any) -> None:
    clock.set(clock.now() - timedelta(days=4))  # Monday 26.10.
    weekly = task(client, cab.assistant, "Test Bowie-Dick", frequency="weekly", weekday=1)
    clock.set(clock.now() + timedelta(days=4))  # Friday again: Monday's test was not done
    daily = task(client, cab.assistant, "Purge des conduits")
    task(client, cab.assistant, "Maintenance autoclave", frequency="yearly", startsOn="2027-01-15")  # not due yet
    body = today(client, cab.dentist)
    assert body["day"] == "2026-10-30" and body["open"] == 2
    assert [(i["title"], i["dueOn"], i["state"]) for i in body["items"]] == [
        ("Test Bowie-Dick", "2026-10-26", "overdue"), ("Purge des conduits", "2026-10-30", "due")]
    res = tick(client, cab.dentist, daily["id"], note="RAS")
    assert res.status_code == 201, res.text
    done = res.json()
    assert (done["state"], done["dueOn"], done["done"]["doneBy"], done["done"]["result"], done["done"]["note"]) == (
        "done", "2026-10-30", "Dr. Karim", "ok", "RAS")
    assert done["done"]["doneAt"] == "2026-10-30T09:00:00+01:00" and done["done"]["undoable"] is True
    body = today(client, cab.assistant)
    assert body["open"] == 1
    assert [i["state"] for i in body["items"]] == ["overdue", "done"]
    assert body["items"][1]["done"]["undoable"] is False  # somebody else ticked it
    assert client.get("/api/badges", headers=cab.assistant).json()["hygiene"] == 1
    assert client.get("/api/dashboard", headers=cab.assistant).json()["hygiene"]["open"] == 1
    late = tick(client, cab.assistant, weekly["id"], dueOn="2026-10-26", result="not_ok", note="Indicateur non viré")
    assert late.status_code == 201, late.text
    assert today(client, cab.assistant)["open"] == 0


def test_only_the_current_occurrence_can_be_ticked_once(client: TestClient, cab: Any, clock: Any) -> None:
    daily = task(client, cab.assistant)
    assert_problem(tick(client, cab.assistant, daily["id"], dueOn="2026-10-29"), 422, "not_due")  # yesterday's is gone
    assert_problem(tick(client, cab.assistant, daily["id"], dueOn="2026-10-31"), 422, "not_due")
    assert tick(client, cab.assistant, daily["id"]).status_code == 201
    assert_problem(tick(client, cab.assistant, daily["id"]), 409, "already_done")
    assert_problem(tick(client, cab.assistant, daily["id"], result="maybe"), 422, "validation")
    client.patch(f"/api/hygiene/tasks/{daily['id']}", json={"active": False}, headers=cab.owner)
    clock.advance(days=1)
    assert_problem(tick(client, cab.assistant, daily["id"]), 422, "task_inactive")
    assert today(client, cab.assistant)["items"] == []


def test_a_tick_is_undone_by_its_author_soon_or_by_the_owner_and_logged(client: TestClient, cab: Any, clock: Any) -> None:
    daily = task(client, cab.assistant)
    done = tick(client, cab.assistant, daily["id"]).json()["done"]
    assert_problem(client.delete(f"/api/hygiene/done/{done['id']}", headers=cab.dentist), 403, "forbidden")
    assert client.delete(f"/api/hygiene/done/{done['id']}", headers=cab.assistant).status_code == 204
    again = tick(client, cab.assistant, daily["id"]).json()["done"]
    clock.advance(minutes=20)
    assert_problem(client.delete(f"/api/hygiene/done/{again['id']}", headers=cab.assistant), 403, "undo_too_late")
    assert client.delete(f"/api/hygiene/done/{again['id']}", headers=cab.owner).status_code == 204
    log = client.get("/api/audit-log?entity=hygiene_task_done", headers=cab.owner).json()
    assert [(e["userName"], e["before"]["task"], e["before"]["doneBy"]) for e in log] == [
        ("Dr. Fadoua", "Purge des conduits", "Nisrine"), ("Nisrine", "Purge des conduits", "Nisrine")]


def test_a_task_with_proofs_is_deactivated_not_deleted(client: TestClient, cab: Any) -> None:
    used = task(client, cab.assistant)
    tick(client, cab.assistant, used["id"])
    assert_problem(client.delete(f"/api/hygiene/tasks/{used['id']}", headers=cab.assistant), 409, "task_in_use")
    spare = task(client, cab.assistant, "Erreur")
    assert client.delete(f"/api/hygiene/tasks/{spare['id']}", headers=cab.assistant).status_code == 204


def test_daily_tasks_wait_for_opening_days(client: TestClient, cab: Any, clock: Any, make_practice: Factory) -> None:
    daily = task(client, cab.assistant)
    clock.advance(days=2)  # Sunday 01.11.: closed – Saturday's purge is the current one
    body = today(client, cab.assistant)
    assert [(i["taskId"], i["dueOn"], i["state"]) for i in body["items"]] == [(daily["id"], "2026-10-31", "overdue")]


# --- history (lückenloser Nachweis) -------------------------------------------------------------------------------


def test_history_shows_done_late_and_missed_days(client: TestClient, cab: Any, clock: Any) -> None:
    clock.set(clock.now() - timedelta(days=4))  # Monday 26.10.
    daily = task(client, cab.assistant, "Purge des conduits")
    gear = client.post("/api/hygiene/equipment", json={"name": "Autoclave", "kind": "autoclave"}, headers=cab.assistant).json()
    weekly = task(client, cab.assistant, "Bowie-Dick", frequency="weekly", weekday=1, equipmentId=gear["id"])
    tick(client, cab.assistant, daily["id"])  # Monday
    clock.advance(days=1)
    tick(client, cab.dentist, daily["id"], result="not_ok", note="Pression faible")  # Tuesday
    clock.advance(days=3)  # Friday; Wednesday and Thursday missed; Monday's Bowie-Dick done late
    tick(client, cab.assistant, weekly["id"], dueOn="2026-10-26")
    res = client.get("/api/hygiene/history?from=2026-10-26&to=2026-10-30", headers=cab.dentist)
    assert res.status_code == 200, res.text
    rows = [(r["dueOn"], r["title"], r["status"], r["late"]) for r in res.json()["rows"]]
    assert rows == [
        ("2026-10-30", "Purge des conduits", "due", False),
        ("2026-10-29", "Purge des conduits", "missed", False),
        ("2026-10-28", "Purge des conduits", "missed", False),
        ("2026-10-27", "Purge des conduits", "done", False),
        ("2026-10-26", "Bowie-Dick", "done", True),
        ("2026-10-26", "Purge des conduits", "done", False),
    ]
    tuesday = res.json()["rows"][3]["done"]
    assert (tuesday["result"], tuesday["note"], tuesday["doneBy"]) == ("not_ok", "Pression faible", "Dr. Karim")
    only = client.get(f"/api/hygiene/history?from=2026-10-26&to=2026-10-30&equipmentId={gear['id']}", headers=cab.dentist)
    assert [r["title"] for r in only.json()["rows"]] == ["Bowie-Dick"]
    assert_problem(client.get("/api/hygiene/history?from=2026-10-30&to=2026-10-01", headers=cab.dentist), 422, "invalid_range")
    assert_problem(client.get("/api/hygiene/history?from=2025-01-01&to=2026-10-30", headers=cab.dentist), 422, "invalid_range")


def test_the_practice_export_contains_the_hygiene_tables(client: TestClient, cab: Any) -> None:
    daily = task(client, cab.assistant)
    tick(client, cab.assistant, daily["id"])
    data = client.get("/api/practice/export", headers=cab.owner).json()
    assert [t["title"] for t in data["hygieneTasks"]] == ["Purge des conduits"]
    assert [d["doneByName"] for d in data["hygieneTasksDone"]] == ["Nisrine"]
    assert data["equipment"] == []
