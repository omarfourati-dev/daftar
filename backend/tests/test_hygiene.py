"""Hygiene API (spec stock-hygiène 3, 5.1, 5.2, 8): equipment, tasks, "Hygiène du jour", proofs, history."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from daftar.hygiene_register import sync_all
from daftar.tables import hygiene_task_due
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
    assert client.request("DELETE", f"/api/hygiene/done/{again['id']}", json={"reason": "Fait par erreur"},
                          headers=cab.owner).status_code == 204
    assert [i["state"] for i in today(client, cab.assistant)["items"]] == ["due"]  # to do again
    log = client.get("/api/audit-log?entity=hygiene_task_done", headers=cab.owner).json()
    assert [(e["userName"], e["before"]["task"], e["before"]["doneBy"], e["reason"]) for e in log] == [
        ("Dr. Fadoua", "Purge des conduits", "Nisrine", "Fait par erreur"), ("Nisrine", "Purge des conduits", "Nisrine", "")]


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


# --- the register is a document (review H1): written down day by day, never rewritten ------------------------------


def register(client: TestClient, headers: dict[str, str], first: str, last: str) -> list[tuple[str, str, str]]:
    res = client.get(f"/api/hygiene/history?from={first}&to={last}", headers=headers)
    assert res.status_code == 200, res.text
    return [(r["dueOn"], r["title"], r["status"]) for r in res.json()["rows"]]


def test_changing_or_deactivating_a_task_keeps_the_register(client: TestClient, cab: Any, clock: Any) -> None:
    clock.set(clock.now() - timedelta(days=4))  # Monday 26.10.
    daily = task(client, cab.assistant, "Purge des conduits")
    assert tick(client, cab.assistant, daily["id"]).status_code == 201
    clock.advance(days=4)  # Friday 30.10.: Tuesday to Thursday were forgotten, nobody opened the app
    res = client.patch(f"/api/hygiene/tasks/{daily['id']}", json={"frequency": "weekly", "weekday": 1}, headers=cab.assistant)
    assert res.status_code == 200, res.text
    assert res.json()["nextDueOn"] == "2026-11-02"
    past = [("2026-10-29", "Purge des conduits", "missed"), ("2026-10-28", "Purge des conduits", "missed"),
            ("2026-10-27", "Purge des conduits", "missed"), ("2026-10-26", "Purge des conduits", "done")]
    assert register(client, cab.dentist, "2026-10-26", "2026-10-30") == past  # the new rhythm counts from today
    assert client.patch(f"/api/hygiene/tasks/{daily['id']}", json={"active": False}, headers=cab.assistant).status_code == 200
    assert register(client, cab.dentist, "2026-10-26", "2026-10-30") == past  # deactivating hides no gap
    clock.advance(days=3)  # Monday 02.11.: a deactivated task is not due any more
    assert today(client, cab.assistant)["items"] == []
    assert register(client, cab.dentist, "2026-10-26", "2026-11-02") == past
    log = client.get("/api/audit-log?entity=hygiene_task", headers=cab.owner).json()
    assert [(e["action"], e["userName"], e["before"], e["after"]) for e in log] == [
        ("update", "Nisrine", {"active": True}, {"active": False}),
        ("update", "Nisrine", {"frequency": "daily", "weekday": None}, {"frequency": "weekly", "weekday": 1}),
    ]


def test_a_more_frequent_rhythm_does_not_rewrite_the_past(client: TestClient, cab: Any, clock: Any) -> None:
    clock.set(clock.now() - timedelta(days=4))  # Monday 26.10.
    weekly = task(client, cab.assistant, "Bowie-Dick", frequency="weekly", weekday=1)
    tick(client, cab.assistant, weekly["id"])
    clock.advance(days=4)
    every_day = {"frequency": "daily", "weekday": None, "intervalDays": None, "title": "Bowie-Dick",
                 "startsOn": "2026-10-26", "instructions": "", "equipmentId": None, "active": True}  # the dialog sends all
    assert client.patch(f"/api/hygiene/tasks/{weekly['id']}", json=every_day, headers=cab.owner).status_code == 200
    assert register(client, cab.dentist, "2026-10-26", "2026-10-30") == [
        ("2026-10-30", "Bowie-Dick", "due"), ("2026-10-26", "Bowie-Dick", "done")]
    log = client.get("/api/audit-log?entity=hygiene_task", headers=cab.owner).json()
    assert [(e["before"], e["after"]) for e in log] == [({"frequency": "weekly", "weekday": 1}, {"frequency": "daily", "weekday": None})]


def test_occurrences_never_start_before_the_task_was_created(client: TestClient, cab: Any) -> None:
    daily = task(client, cab.assistant, "Désinfection des surfaces", startsOn="2026-01-01")
    assert register(client, cab.dentist, "2026-01-01", "2026-10-30") == [("2026-10-30", "Désinfection des surfaces", "due")]
    yearly = task(client, cab.assistant, "Maintenance autoclave", frequency="yearly", startsOn="2026-03-02")  # last done
    assert yearly["nextDueOn"] == "2027-03-02"
    assert [i["taskId"] for i in today(client, cab.assistant)["items"]] == [daily["id"]]


def test_a_task_with_a_past_occurrence_is_deactivated_not_deleted(client: TestClient, cab: Any, clock: Any) -> None:
    clock.set(clock.now() - timedelta(days=1))
    forgotten = task(client, cab.assistant, "Purge")  # never ticked: Thursday stays "non fait"
    clock.advance(days=1)
    assert_problem(client.delete(f"/api/hygiene/tasks/{forgotten['id']}", headers=cab.assistant), 409, "task_in_use")
    mistake = task(client, cab.assistant, "Erreur de saisie")  # created and due today, nothing done: may go
    assert client.delete(f"/api/hygiene/tasks/{mistake['id']}", headers=cab.assistant).status_code == 204
    assert [r[1] for r in register(client, cab.dentist, "2026-10-29", "2026-10-30")] == ["Purge", "Purge"]


def test_opening_hours_and_closures_change_the_plan_from_today_only(client: TestClient, cab: Any, clock: Any) -> None:
    clock.set(clock.now() - timedelta(days=4))  # Monday 26.10.
    daily = task(client, cab.assistant, "Purge")
    clock.advance(days=4)  # Friday: nobody looked since Monday
    hours = {str(d): [["08:00", "13:00"]] for d in (1, 2, 4)}  # from now on: Monday, Tuesday, Thursday
    assert client.patch("/api/practice", json={"weeklyHours": hours}, headers=cab.owner).status_code == 200
    assert [r[0] for r in register(client, cab.dentist, "2026-10-26", "2026-10-30")] == [
        "2026-10-29", "2026-10-28", "2026-10-27", "2026-10-26"]  # Wednesday was open then; Friday is closed now
    clock.advance(days=3)  # Monday 02.11.
    assert [i["dueOn"] for i in today(client, cab.assistant)["items"]] == ["2026-11-02"]
    res = client.post("/api/closures", json={"startsOn": "2026-11-02", "label": "Malade"}, headers=cab.owner)
    assert res.status_code == 201, res.text
    assert today(client, cab.assistant)["items"] == []  # closed today: nothing due, no gap
    assert_problem(tick(client, cab.assistant, daily["id"]), 422, "not_due")
    assert [r[0] for r in register(client, cab.dentist, "2026-10-29", "2026-11-02")] == ["2026-10-29"]


def test_the_job_writes_each_day_and_a_failed_job_is_caught_up_on_reading(
    client: TestClient, app: Any, cab: Any, clock: Any, db: Engine
) -> None:
    clock.set(clock.now() - timedelta(days=4))  # Monday 26.10.
    task(client, cab.assistant, "Purge")
    clock.advance(days=1, hours=-8)  # Tuesday 01:00
    sync_all(app.state.ctx)
    with db.connect() as conn:
        written = conn.execute(select(hygiene_task_due.c.due_on, hygiene_task_due.c.status)
                               .order_by(hygiene_task_due.c.due_on)).all()
    assert [(d.isoformat(), s) for d, s in written] == [("2026-10-26", "missed"), ("2026-10-27", "open")]
    clock.advance(days=3, hours=8)  # Friday: the job did not run since
    assert client.get("/api/badges", headers=cab.dentist).json()["hygiene"] == 1
    assert [r[2] for r in register(client, cab.dentist, "2026-10-26", "2026-10-30")] == ["due"] + ["missed"] * 4


def test_a_check_due_on_a_closed_day_is_on_time_the_next_opening_day(client: TestClient, cab: Any, clock: Any) -> None:
    monthly = task(client, cab.assistant, "Vérification des péremptions", frequency="monthly", startsOn="2026-10-15")
    assert monthly["nextDueOn"] == "2026-11-16"  # 15.11. is a Sunday
    clock.set(clock.now() + timedelta(days=17))  # Monday 16.11.
    assert [(i["dueOn"], i["state"]) for i in today(client, cab.assistant)["items"]] == [("2026-11-16", "due")]
    assert tick(client, cab.assistant, monthly["id"]).status_code == 201
    rows = client.get("/api/hygiene/history?from=2026-11-01&to=2026-11-16", headers=cab.dentist).json()["rows"]
    assert [(r["dueOn"], r["status"], r["late"]) for r in rows] == [("2026-11-16", "done", False)]


def test_a_weekly_test_not_done_yet_is_overdue_not_missed(client: TestClient, cab: Any, clock: Any) -> None:
    clock.set(clock.now() - timedelta(days=4))
    task(client, cab.assistant, "Bowie-Dick", frequency="weekly", weekday=1)
    clock.advance(days=4)
    assert register(client, cab.dentist, "2026-10-26", "2026-10-30") == [("2026-10-26", "Bowie-Dick", "overdue")]
    clock.advance(days=3)  # the next Monday replaces it: now it is a gap
    assert register(client, cab.dentist, "2026-10-26", "2026-11-02") == [
        ("2026-11-02", "Bowie-Dick", "due"), ("2026-10-26", "Bowie-Dick", "missed")]


def test_renaming_keeps_the_names_of_the_register(client: TestClient, cab: Any, clock: Any) -> None:
    clock.set(clock.now() - timedelta(days=1))
    gear = client.post("/api/hygiene/equipment", json={"name": "Fauteuil 1"}, headers=cab.assistant).json()
    daily = task(client, cab.assistant, "Purge", equipmentId=gear["id"])
    tick(client, cab.assistant, daily["id"])
    clock.advance(days=1)
    client.patch(f"/api/hygiene/tasks/{daily['id']}", json={"title": "Purge des conduits"}, headers=cab.assistant)
    client.patch(f"/api/hygiene/equipment/{gear['id']}", json={"name": "Fauteuil bleu", "serialNumber": "SN-9"},
                 headers=cab.owner)
    rows = client.get("/api/hygiene/history?from=2026-10-29&to=2026-10-30", headers=cab.dentist).json()["rows"]
    assert [(r["title"], r["equipmentName"]) for r in rows] == [("Purge des conduits", "Fauteuil bleu"), ("Purge", "Fauteuil 1")]
    log = client.get("/api/audit-log?entity=equipment,hygiene_task", headers=cab.owner).json()
    assert [(e["entity"], e["entityId"], e["before"], e["after"]) for e in log] == [
        ("equipment", gear["id"], {"name": "Fauteuil 1", "serialNumber": ""}, {"name": "Fauteuil bleu", "serialNumber": "SN-9"}),
        ("hygiene_task", daily["id"], {"title": "Purge"}, {"title": "Purge des conduits"}),
    ]


# --- corrections of a proof (review N8) -----------------------------------------------------------------------------


def test_the_owner_corrects_a_proof_with_a_reason(client: TestClient, cab: Any, clock: Any) -> None:
    weekly = task(client, cab.assistant, "Bowie-Dick", frequency="weekly", weekday=5)
    done = tick(client, cab.dentist, weekly["id"]).json()["done"]
    clock.advance(days=1)
    path = f"/api/hygiene/done/{done['id']}"
    correction = {"result": "not_ok", "note": "Indicateur non viré", "reason": "Vu le lendemain"}
    assert_problem(client.patch(path, json=correction, headers=cab.assistant), 403, "forbidden")
    assert_problem(client.patch(path, json={**correction, "reason": ""}, headers=cab.owner), 422, "validation")
    res = client.patch(path, json=correction, headers=cab.owner)
    assert res.status_code == 200, res.text
    row = client.get("/api/hygiene/history?from=2026-10-30&to=2026-10-31", headers=cab.dentist).json()["rows"][0]
    assert (row["status"], row["done"]["result"], row["done"]["note"], row["done"]["doneBy"]) == (
        "done", "not_ok", "Indicateur non viré", "Dr. Karim")
    entry = client.get("/api/audit-log?entity=hygiene_task_done", headers=cab.owner).json()[0]
    assert (entry["action"], entry["reason"], entry["before"]["result"], entry["after"]["result"]) == (
        "update", "Vu le lendemain", "ok", "not_ok")
    assert (entry["before"]["task"], entry["before"]["dueOn"]) == ("Bowie-Dick", "2026-10-30")


def test_the_owner_needs_a_reason_to_delete_a_proof_later(client: TestClient, cab: Any, clock: Any) -> None:
    clock.set(clock.now() - timedelta(days=1))
    daily = task(client, cab.assistant)
    done = tick(client, cab.assistant, daily["id"]).json()["done"]
    clock.advance(days=1)
    path = f"/api/hygiene/done/{done['id']}"
    assert_problem(client.delete(path, headers=cab.owner), 422, "reason_required")
    assert client.request("DELETE", path, json={"reason": "Pas fait en réalité"}, headers=cab.owner).status_code == 204
    assert register(client, cab.dentist, "2026-10-29", "2026-10-29") == [("2026-10-29", "Purge des conduits", "missed")]
    entry = client.get("/api/audit-log?entity=hygiene_task_done", headers=cab.owner).json()[0]
    assert (entry["action"], entry["reason"]) == ("delete", "Pas fait en réalité")


# --- every id stays in its practice, every role keeps to its rights (review M4, DoD 3) ------------------------------


def test_every_id_of_another_practice_is_not_found(client: TestClient, cab: Any, make_user: Factory,
                                                   auth_headers: Factory) -> None:
    gear = client.post("/api/hygiene/equipment", json={"name": "Autoclave"}, headers=cab.assistant).json()
    mine = task(client, cab.assistant, equipmentId=gear["id"])
    done = tick(client, cab.assistant, mine["id"]).json()["done"]
    stranger = auth_headers(make_user(role="owner"))
    for method, path, body in [
        ("PATCH", f"/api/hygiene/equipment/{gear['id']}", {"name": "X"}),
        ("DELETE", f"/api/hygiene/equipment/{gear['id']}", None),
        ("PATCH", f"/api/hygiene/tasks/{mine['id']}", {"title": "X"}),
        ("DELETE", f"/api/hygiene/tasks/{mine['id']}", None),
        ("POST", f"/api/hygiene/tasks/{mine['id']}/done", {}),
        ("PATCH", f"/api/hygiene/done/{done['id']}", {"result": "not_ok", "reason": "x"}),
        ("DELETE", f"/api/hygiene/done/{done['id']}", {"reason": "x"}),
    ]:
        assert_problem(client.request(method, path, json=body, headers=stranger), 404, "not_found")
    assert_problem(client.post("/api/hygiene/tasks", json={"title": "X", "frequency": "daily", "equipmentId": gear["id"]},
                               headers=stranger), 422, "invalid_equipment")
    assert_problem(client.patch(f"/api/hygiene/tasks/{mine['id']}", json={"equipmentId": 999_999}, headers=cab.owner), 422,
                   "invalid_equipment")
    assert client.get(f"/api/hygiene/history?equipmentId={gear['id']}", headers=stranger).json()["rows"] == []
    assert client.get("/api/hygiene/equipment", headers=stranger).json() == []
    assert client.get("/api/audit-log", headers=stranger).json() == []


def test_every_endpoint_keeps_to_the_roles(client: TestClient, cab: Any) -> None:
    gear = client.post("/api/hygiene/equipment", json={"name": "Autoclave"}, headers=cab.assistant).json()
    mine = task(client, cab.assistant)
    done = tick(client, cab.assistant, mine["id"]).json()["done"]
    for method, path, body in [
        ("PATCH", f"/api/hygiene/equipment/{gear['id']}", {"name": "X"}),
        ("DELETE", f"/api/hygiene/equipment/{gear['id']}", None),
        ("PATCH", f"/api/hygiene/tasks/{mine['id']}", {"title": "X"}),
        ("DELETE", f"/api/hygiene/tasks/{mine['id']}", None),
        ("PATCH", f"/api/hygiene/done/{done['id']}", {"result": "not_ok", "reason": "x"}),
        ("DELETE", f"/api/hygiene/done/{done['id']}", None),  # somebody else's tick
        ("GET", "/api/audit-log?entity=hygiene_task", None),
    ]:
        assert_problem(client.request(method, path, json=body, headers=cab.dentist), 403, "forbidden")
    assert_problem(client.request("PATCH", f"/api/hygiene/done/{done['id']}", json={"result": "ok", "reason": "x"},
                                  headers=cab.assistant), 403, "forbidden")
    for method, path in [("GET", "/api/hygiene/today"), ("GET", "/api/hygiene/tasks"), ("GET", "/api/hygiene/history"),
                         ("POST", f"/api/hygiene/tasks/{mine['id']}/done"), ("PATCH", f"/api/hygiene/done/{done['id']}")]:
        assert_problem(client.request(method, path), 401, "unauthorized")
