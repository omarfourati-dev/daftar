"""Import API (section 14, E5): upload → sheet/header → mapping → preview (no writes) → commit (one transaction)
→ report CSV; templates; deletion of the file after commit or 24 h."""

import csv
import io
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, update

from daftar import imports as imports_module
from daftar.imports import delete_expired_imports
from daftar.tables import appointment, import_job, patient, practice, treatment
from tests.conftest import T0
from tests.helpers import assert_problem
from tests.import_helpers import csv_bytes, xlsx

Factory = Callable[..., Any]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

PATIENTS = xlsx(
    ("Patients", [
        ["N° dossier", "Nom", "Prénom", "Tél", "Date de naissance", "Allergies", "Reste à payer", "Langue"],
        ["D-001", "Trabelsi", "Amira", 20123456, datetime(1985, 3, 1), "Pénicilline", "120,500", "ar"],
        ["D-002", "Ben Ali", "Sami", 98765432.0, None, None, None, None],
        ["D-003", "Gharbi", "", "20 111 222", None, None, None, None],
        ["D-004", "Jlassi", "Mehdi", "123", None, None, "-5", None],
    ]),
    ("Archives", [["Nom complet", "GSM"], ["Ben Amor Salah", "22333444"]]),
)
MAPPING = {"externalRef": 0, "lastName": 1, "firstName": 2, "phone": 3, "birthDate": 4, "alerts": 5,
           "openingBalance": 6, "lang": 7}


@pytest.fixture
def owner(make_practice: Factory, make_user: Factory) -> Any:
    return make_user(make_practice(practitioners=["Dr. Salah Ben Amor", "Dr. Ines Chaabane"]), "owner")


def _pid(user: Any) -> Any:
    return type("P", (), {"id": user.practice_id})()


def upload(client: TestClient, headers: dict[str, str], data: bytes = PATIENTS, name: str = "patients.xlsx") -> Any:
    return client.post("/api/imports", files={"file": (name, data, XLSX)}, headers=headers)


def _count(db: Engine, table: Any) -> int:
    with db.connect() as conn:
        return conn.execute(select(func.count()).select_from(table)).scalar_one()


# --- upload and sheet ------------------------------------------------------------------------------------------

def test_upload_describes_the_file_and_suggests_a_mapping(client: TestClient, db: Engine, owner: Any, auth_headers: Factory) -> None:
    res = upload(client, auth_headers(owner))
    assert res.status_code == 201, res.text
    body = res.json()
    uuid.UUID(body["id"])
    assert (body["filename"], body["sheets"], body["sheet"], body["headerRow"], body["rowCount"]) == (
        "patients.xlsx", ["Patients", "Archives"], "Patients", 1, 4)
    assert body["columns"][3] == {"index": 3, "header": "Tél", "samples": ["20123456", "98765432", "20 111 222"]}
    assert body["columns"][4]["samples"] == ["01/03/1985"]
    assert {k: v for k, v in body["suggestedMapping"].items() if v is not None} == MAPPING
    with db.connect() as conn:
        job = conn.execute(select(import_job)).one()
    assert (job.practice_id, job.created_by, job.expires_at, job.committed_at) == (owner.practice_id, owner.id, T0 + timedelta(hours=24), None)


def test_choose_another_sheet_and_header_row(client: TestClient, owner: Any, auth_headers: Factory) -> None:
    h = auth_headers(owner)
    job = upload(client, h).json()["id"]
    res = client.post(f"/api/imports/{job}/sheet", json={"sheet": "Archives", "headerRow": 1}, headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["sheet"], body["rowCount"], [c["header"] for c in body["columns"]]) == ("Archives", 1, ["Nom complet", "GSM"])
    assert (body["suggestedMapping"]["fullName"], body["suggestedMapping"]["phone"]) == (0, 1)
    body = client.post(f"/api/imports/{job}/sheet", json={"sheet": "Archives", "headerRow": 0}, headers=h).json()
    assert ([c["header"] for c in body["columns"]], body["rowCount"]) == (["Colonne A", "Colonne B"], 2)
    assert_problem(client.post(f"/api/imports/{job}/sheet", json={"sheet": "Nope", "headerRow": 1}, headers=h), 422, "unknown_sheet")
    assert_problem(client.post(f"/api/imports/{job}/sheet", json={"sheet": "Archives", "headerRow": 21}, headers=h), 422, "validation")


@pytest.mark.parametrize(
    ("name", "data", "status", "code"),
    [
        ("big.csv", b"x" * (2 * 1024 * 1024 + 1), 413, "file_too_large"),
        ("photo.png", b"\x89PNG\r\n\x1a\n\x00\x00", 422, "unsupported_file"),
        ("vide.csv", b"", 422, "empty_file"),
    ],
)
def test_upload_refuses_unusable_files(client: TestClient, db: Engine, owner: Any, auth_headers: Factory,
                                       name: str, data: bytes, status: int, code: str) -> None:
    assert_problem(upload(client, auth_headers(owner), data, name), status, code)
    assert _count(db, import_job) == 0


def test_upload_needs_a_file(client: TestClient, owner: Any, auth_headers: Factory) -> None:
    assert_problem(client.post("/api/imports", headers=auth_headers(owner)), 422, "validation")


def test_import_roles_and_subscription(client: TestClient, make_practice: Factory, make_user: Factory, auth_headers: Factory) -> None:
    p = make_practice()
    assert upload(client, auth_headers(make_user(p, "assistant"))).status_code == 201
    assert_problem(upload(client, auth_headers(make_user(p, "dentist"))), 403, "forbidden")
    assert_problem(upload(client, auth_headers(make_user(role="admin"))), 403, "forbidden")
    assert_problem(upload(client, {}), 401, "unauthorized")
    assert_problem(upload(client, auth_headers(make_user(make_practice(status="suspended"), "owner"))), 402, "subscription_suspended")


def test_demo_practices_cannot_import(client: TestClient, db: Engine, make_practice: Factory, make_user: Factory,
                                     auth_headers: Factory) -> None:
    """Security review H1/H2: every visitor is the owner of a demo – no uploads there (the file is never read)."""
    demo = make_practice(is_demo=True, demo_expires_at=T0 + timedelta(hours=24))
    for role in ("owner", "assistant"):
        body = assert_problem(upload(client, auth_headers(make_user(demo, role))), 403, "demo_import_disabled")
        assert "démo" in body["detail"]
    assert_problem(upload(client, auth_headers(make_user(demo, "owner")), b"PK broken", "x.xlsx"), 403,
                   "demo_import_disabled")
    assert _count(db, import_job) == 0


def test_uploads_are_limited_per_user(client: TestClient, make_practice: Factory, make_user: Factory,
                                      auth_headers: Factory, clock: Any) -> None:
    """10 uploads per user and hour – failed ones count too (a broken file costs the same parsing)."""
    p = make_practice()
    owner, assistant = make_user(p, "owner"), make_user(p, "assistant")
    h = auth_headers(owner)
    for i in range(10):
        data, name = (PATIENTS, "patients.xlsx") if i % 2 else (b"PK broken", "x.xlsx")
        assert upload(client, h, data, name).status_code in (201, 422)
    res = upload(client, h)
    assert_problem(res, 429, "too_many_requests")
    assert int(res.headers["Retry-After"]) > 0
    assert upload(client, auth_headers(assistant)).status_code == 201  # per user, not per practice
    clock.advance(hours=1, seconds=1)
    assert upload(client, h).status_code == 201


def test_at_most_three_open_imports_per_practice(client: TestClient, db: Engine, make_practice: Factory,
                                                 make_user: Factory, auth_headers: Factory, clock: Any) -> None:
    """Security review H2: a new upload deletes the oldest open job (each keeps up to 2 MB for 24 h)."""
    p = make_practice()
    owner, assistant = make_user(p, "owner"), make_user(p, "assistant")
    other = make_user(make_practice(), "owner")
    other_job = upload(client, auth_headers(other)).json()["id"]
    h = auth_headers(owner)
    done = upload(client, h).json()["id"]
    assert client.post(f"/api/imports/{done}/commit", json={"kind": "patients", "mapping": MAPPING}, headers=h).status_code == 200
    jobs = []
    for user in (owner, assistant, owner, assistant):
        clock.advance(minutes=1)
        jobs.append(upload(client, auth_headers(user)).json()["id"])
    with db.connect() as conn:
        open_jobs = conn.execute(select(import_job.c.id).where(import_job.c.practice_id == p.id,
                                                               import_job.c.committed_at.is_(None))
                                 .order_by(import_job.c.created_at)).scalars().all()
        kept = {str(i) for i in conn.execute(select(import_job.c.id)).scalars()}
    assert [str(i) for i in open_jobs] == jobs[1:]
    assert {done, other_job} <= kept  # the report of a committed import and other practices stay
    assert_problem(client.post(f"/api/imports/{jobs[0]}/sheet", json={"sheet": "Patients", "headerRow": 1},
                               headers=h), 404, "not_found")


def test_jobs_of_other_practices_and_unknown_jobs_are_404(client: TestClient, owner: Any, make_user: Factory,
                                                         auth_headers: Factory) -> None:
    job = upload(client, auth_headers(owner)).json()["id"]
    stranger = auth_headers(make_user(role="owner"))
    body = {"kind": "patients", "mapping": MAPPING, "options": {}}
    for res in (
        client.post(f"/api/imports/{job}/sheet", json={"sheet": "Patients", "headerRow": 1}, headers=stranger),
        client.post(f"/api/imports/{job}/preview", json=body, headers=stranger),
        client.post(f"/api/imports/{job}/commit", json=body, headers=stranger),
        client.get(f"/api/imports/{job}/report.csv", headers=stranger),
        client.post(f"/api/imports/{uuid.uuid4()}/preview", json=body, headers=auth_headers(owner)),
    ):
        assert_problem(res, 404, "not_found")


# --- preview ---------------------------------------------------------------------------------------------------

def test_preview_normalises_reports_errors_and_writes_nothing(client: TestClient, db: Engine, owner: Any, auth_headers: Factory) -> None:
    h = auth_headers(owner)
    job = upload(client, h).json()["id"]
    res = client.post(f"/api/imports/{job}/preview", json={"kind": "patients", "mapping": MAPPING, "options": {}}, headers=h)
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["willCreate"], body["willUpdate"], body["willSkip"], body["errorCount"]) == (2, 0, 0, 2)
    assert body["errors"] == [
        {"row": 4, "field": "firstName", "message": "Prénom manquant.", "value": ""},
        {"row": 5, "field": "phone", "message": "Numéro de téléphone invalide.", "value": "123"},
        {"row": 5, "field": "openingBalance", "message": "Montant négatif refusé.", "value": "-5"},
    ]
    assert body["sample"][0] == {
        "row": 2, "firstName": "Amira", "lastName": "Trabelsi", "phone": "+21620123456", "birthYear": 1985,
        "lang": "ar", "reminderConsent": False, "notes": "Réf. : D-001", "alerts": "Pénicilline",
        "openingBalanceMillimes": 120_500,
    }
    assert body["sample"][1]["phone"] == "+21698765432" and body["sample"][1]["lang"] == "fr"
    assert body["duplicates"] == [] and body["conflicts"] == []
    assert _count(db, patient) == 0


@pytest.mark.parametrize(
    ("mapping", "code"),
    [
        ({"lastName": 1, "firstName": 2}, "missing_required_field"),  # no phone
        ({"phone": 3, "lastName": 1}, "missing_required_field"),  # last name without first name
        ({"phone": 3, "fullName": 1, "shoeSize": 2}, "unknown_field"),
        ({"phone": 3, "fullName": 1, "date": 2}, "unknown_field"),  # an appointment field
        ({"phone": 3, "fullName": 12}, "invalid_column"),
        ({"phone": -1, "fullName": 1}, "invalid_column"),
    ],
)
def test_mapping_is_validated(client: TestClient, owner: Any, auth_headers: Factory, mapping: dict[str, Any], code: str) -> None:
    h = auth_headers(owner)
    job = upload(client, h).json()["id"]
    assert_problem(client.post(f"/api/imports/{job}/preview", json={"kind": "patients", "mapping": mapping}, headers=h), 422, code)


def test_options_are_validated(client: TestClient, owner: Any, auth_headers: Factory) -> None:
    h = auth_headers(owner)
    job = upload(client, h).json()["id"]
    for options in ({"duplicates": "merge"}, {"nameOrder": "random"}, {"dateFormat": "yyyy"}, {"defaultLang": "en"}):
        res = client.post(f"/api/imports/{job}/preview", json={"kind": "patients", "mapping": MAPPING, "options": options}, headers=h)
        assert_problem(res, 422, "validation")
    assert_problem(client.post(f"/api/imports/{job}/preview", json={"kind": "invoices", "mapping": MAPPING}, headers=h), 422, "validation")


def test_full_name_option_and_defaults(client: TestClient, db: Engine, owner: Any, auth_headers: Factory) -> None:
    h = auth_headers(owner)
    data = csv_bytes(["Patient;Téléphone", "Amira Ben Ali;20123456", "Trabelsi;20999999"])
    job = upload(client, h, data, "liste.csv").json()["id"]
    body = client.post(f"/api/imports/{job}/preview", json={
        "kind": "patients", "mapping": {"fullName": 0, "phone": 1},
        "options": {"nameOrder": "first_last", "defaultLang": "ar", "reminderConsent": True}}, headers=h).json()
    assert body["sample"][0] | {} == {"row": 2, "firstName": "Amira", "lastName": "Ben Ali", "phone": "+21620123456",
                                      "birthYear": None, "lang": "ar", "reminderConsent": True, "notes": "", "alerts": "",
                                      "openingBalanceMillimes": None}
    assert body["errors"] == [{"row": 3, "field": "fullName", "message": "Nom complet incomplet (nom et prénom attendus).",
                               "value": "Trabelsi"}]


# --- duplicates ------------------------------------------------------------------------------------------------

DUPES = csv_bytes([
    "Nom;Prénom;Tél;Année de naissance;Alertes;Solde",
    "Trabelsi;Amira;20 123 456;1985;Diabète;50",   # = existing patient (case and spaces do not matter)
    "Trabelsi;Yassine;20 123 456;2015;;",          # same phone, other first name: a child, not a duplicate
    "Gharbi;Leila;98765432;;;",                    # new
    "gharbi;LEILA;98 765 432;;;",                  # same person twice in the file
])
DUPES_MAPPING = {"lastName": 0, "firstName": 1, "phone": 2, "birthYear": 3, "alerts": 4, "openingBalance": 5}


@pytest.mark.parametrize(
    ("rule", "counts"),
    [("skip", (2, 0, 2)), ("update", (2, 1, 1)), ("create", (4, 0, 0))],
)
def test_duplicate_rule_in_preview(client: TestClient, owner: Any, make_patient: Factory, auth_headers: Factory,
                                   rule: str, counts: tuple[int, int, int]) -> None:
    existing = make_patient(_pid(owner), first_name="AMIRA", last_name="trabelsi", phone="+21620123456")
    h = auth_headers(owner)
    job = upload(client, h, DUPES, "d.csv").json()["id"]
    body = client.post(f"/api/imports/{job}/preview", json={"kind": "patients", "mapping": DUPES_MAPPING,
                                                             "options": {"duplicates": rule}}, headers=h).json()
    assert (body["willCreate"], body["willUpdate"], body["willSkip"]) == counts
    assert body["duplicates"] == [{"row": 2, "patientId": existing.id, "name": "Amira Trabelsi"},
                                  {"row": 5, "patientId": None, "name": "LEILA gharbi"}]


def test_commit_with_update_fills_the_existing_file_once(client: TestClient, db: Engine, owner: Any, make_patient: Factory,
                                                         auth_headers: Factory) -> None:
    existing = make_patient(_pid(owner), first_name="Amira", last_name="Trabelsi", phone="+21620123456", notes="Ancien")
    h = auth_headers(owner)
    for _ in range(2):  # the same file twice: the balance is taken over only once
        job = upload(client, h, DUPES, "d.csv").json()["id"]
        res = client.post(f"/api/imports/{job}/commit", json={"kind": "patients", "mapping": DUPES_MAPPING,
                                                              "options": {"duplicates": "update"}}, headers=h)
        assert res.status_code == 200, res.text
    with db.connect() as conn:
        row = conn.execute(select(patient).where(patient.c.id == existing.id)).one()
        balances = conn.execute(select(treatment.c.price_millimes).where(treatment.c.patient_id == existing.id)).scalars().all()
        assert conn.execute(select(func.count()).select_from(patient)).scalar_one() == 3
    assert (row.birth_year, row.alerts, row.notes, row.first_name) == (1985, "Diabète", "Ancien", "Amira")
    assert balances == [50_000]


def test_update_with_the_same_person_twice_in_the_file_takes_the_balance_once(
    client: TestClient, db: Engine, owner: Any, make_patient: Factory, auth_headers: Factory
) -> None:
    """Code review M2: the second line of an existing patient is a duplicate in the file, not a second update."""
    existing = make_patient(_pid(owner), first_name="Amira", last_name="Trabelsi", phone="+21620123456")
    twice = csv_bytes(["Nom;Prénom;Tél;Solde", "Trabelsi;Amira;20 123 456;50", "TRABELSI;amira;20123456;50"])
    h = auth_headers(owner)
    job = upload(client, h, twice, "t.csv").json()["id"]
    body = {"kind": "patients", "mapping": {"lastName": 0, "firstName": 1, "phone": 2, "openingBalance": 3},
            "options": {"duplicates": "update"}}
    preview = client.post(f"/api/imports/{job}/preview", json=body, headers=h).json()
    assert (preview["willCreate"], preview["willUpdate"], preview["willSkip"]) == (0, 1, 1)
    assert client.post(f"/api/imports/{job}/commit", json=body, headers=h).json() == {
        "created": 0, "updated": 1, "skipped": 1, "errorCount": 0, "patientsCreated": 0}
    with db.connect() as conn:
        balances = conn.execute(select(treatment.c.price_millimes).where(treatment.c.patient_id == existing.id)).scalars().all()
    assert balances == [50_000]


def test_update_adds_medical_alerts_and_never_drops_one(
    client: TestClient, db: Engine, owner: Any, make_patient: Factory, auth_headers: Factory
) -> None:
    """Code review M3: "Sous anticoagulant" must survive an import that brings "Pénicilline"."""
    amira = make_patient(_pid(owner), first_name="Amira", last_name="Trabelsi", phone="+21620123456", alerts="Anticoagulant")
    full = make_patient(_pid(owner), first_name="Sami", last_name="Ben Ali", phone="+21698765432", alerts="x" * 495)
    data = csv_bytes(["Nom;Prénom;Tél;Allergies", "Trabelsi;Amira;20123456;Pénicilline", "Ben Ali;Sami;98765432;Latex"])
    body = {"kind": "patients", "mapping": {"lastName": 0, "firstName": 1, "phone": 2, "alerts": 3},
            "options": {"duplicates": "update"}}
    h = auth_headers(owner)
    for _ in range(2):  # twice: nothing is added a second time
        job = upload(client, h, data, "a.csv").json()["id"]
        assert client.post(f"/api/imports/{job}/commit", json=body, headers=h).status_code == 200
    with db.connect() as conn:
        alerts = dict(conn.execute(select(patient.c.id, patient.c.alerts)).all())  # type: ignore[arg-type]
    assert alerts[amira.id] == "Anticoagulant\nPénicilline"
    assert alerts[full.id] == "x" * 495  # no room left: unchanged, and the report says so
    report = client.get(f"/api/imports/{job}/report.csv", headers=h).content.decode("utf-8-sig")
    assert "Latex" in report and "Alertes médicales" in report


# --- commit ----------------------------------------------------------------------------------------------------

def test_commit_creates_patients_with_opening_balances_and_deletes_the_file(
    client: TestClient, db: Engine, owner: Any, auth_headers: Factory
) -> None:
    h = auth_headers(owner)
    job = upload(client, h).json()["id"]
    res = client.post(f"/api/imports/{job}/commit", json={"kind": "patients", "mapping": MAPPING, "options": {}}, headers=h)
    assert res.status_code == 200, res.text
    assert res.json() == {"created": 2, "updated": 0, "skipped": 0, "errorCount": 2, "patientsCreated": 2}
    with db.connect() as conn:
        rows = conn.execute(select(patient).order_by(patient.c.id)).all()
        balances = conn.execute(select(treatment.c.label, treatment.c.price_millimes, treatment.c.performed_on,
                                       treatment.c.patient_id)).all()
        job_row = conn.execute(select(import_job)).one()
    amira = rows[0]
    assert (amira.first_name, amira.phone, amira.birth_year, amira.lang, amira.alerts, amira.notes) == (
        "Amira", "+21620123456", 1985, "ar", "Pénicilline", "Réf. : D-001")
    assert amira.birth_date == date(1985, 3, 1)  # the full date, for specimen labels
    assert [(b.label, b.price_millimes, b.performed_on, b.patient_id) for b in balances] == [
        ("Reprise de solde", 120_500, date(2026, 10, 30), amira.id)]
    assert job_row.committed_at == T0 and job_row.file_bytes is None
    with db.connect() as conn:  # "Erste Schritte": the import step stays done after the job is deleted
        assert conn.execute(select(practice.c.onboarding).where(practice.c.id == owner.practice_id)).scalar_one()["import"] is True
    assert 'daftar_appointments_created_total{source="import"} 0.0' in client.get("/metrics").text
    body = {"kind": "patients", "mapping": MAPPING}
    assert_problem(client.post(f"/api/imports/{job}/commit", json=body, headers=h), 409, "import_already_committed")
    assert_problem(client.post(f"/api/imports/{job}/preview", json=body, headers=h), 409, "import_already_committed")


def test_commit_is_one_transaction(client: TestClient, app: Any, db: Engine, owner: Any, auth_headers: Factory,
                                   monkeypatch: pytest.MonkeyPatch) -> None:
    h = auth_headers(owner)
    job = upload(client, h).json()["id"]

    def boom(*_: Any, **__: Any) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(imports_module, "_insert_balances", boom)
    quiet = TestClient(app, raise_server_exceptions=False)
    res = quiet.post(f"/api/imports/{job}/commit", json={"kind": "patients", "mapping": MAPPING}, headers=h)
    assert_problem(res, 500, "server_error")
    assert _count(db, patient) == 0
    with db.connect() as conn:
        assert conn.execute(select(import_job.c.committed_at)).scalar_one() is None


def test_arabic_csv_from_excel_in_windows_1256(client: TestClient, db: Engine, owner: Any, auth_headers: Factory) -> None:
    data = csv_bytes(["اللقب;الاسم;الهاتف;المتبقي", "الطرابلسي;أميرة;20123456;12,500", "بن علي;سامي;98 765 432;"], encoding="cp1256")
    h = auth_headers(owner)
    up = upload(client, h, data, "مرضى.csv").json()
    mapping = {k: v for k, v in up["suggestedMapping"].items() if v is not None}
    assert mapping == {"lastName": 0, "firstName": 1, "phone": 2, "openingBalance": 3}
    res = client.post(f"/api/imports/{up['id']}/commit", json={"kind": "patients", "mapping": mapping}, headers=h)
    assert res.json()["created"] == 2
    with db.connect() as conn:
        names = conn.execute(select(patient.c.last_name, patient.c.first_name).order_by(patient.c.id)).all()
        assert conn.execute(select(treatment.c.price_millimes)).scalar_one() == 12_500
    assert [tuple(n) for n in names] == [("الطرابلسي", "أميرة"), ("بن علي", "سامي")]


def test_phones_with_arabic_digits_are_imported_and_other_digits_are_row_errors(
    client: TestClient, db: Engine, owner: Any, auth_headers: Factory
) -> None:
    """Security review N1: one such number used to fail the whole commit with a 500 (and names in the log)."""
    data = csv_bytes(["Nom;Prénom;Tél", "Trabelsi;Amira;٢٠ ١٢٣ ٤٥٦", "Ben Ali;Sami;۹۸۷۶۵۴۳۲", "Gharbi;Leila;２０１２３４５６"])
    h = auth_headers(owner)
    up = upload(client, h, data, "patients.csv").json()
    mapping = {"lastName": 0, "firstName": 1, "phone": 2}
    preview = client.post(f"/api/imports/{up['id']}/preview", json={"kind": "patients", "mapping": mapping}, headers=h).json()
    assert (preview["willCreate"], preview["errorCount"]) == (2, 1)
    res = client.post(f"/api/imports/{up['id']}/commit", json={"kind": "patients", "mapping": mapping}, headers=h)
    assert res.status_code == 200, res.text
    with db.connect() as conn:
        phones = conn.execute(select(patient.c.phone).order_by(patient.c.id)).scalars().all()
    assert phones == ["+21620123456", "+21698765432"]


# --- appointments ----------------------------------------------------------------------------------------------

def _appointments_file() -> bytes:
    return xlsx(("RDV", [
        ["Date", "Heure", "Durée", "Nom", "Prénom", "Tél", "Acte", "Médecin", "Remarque"],
        [datetime(2026, 10, 20), "09:00", 30, "Trabelsi", "Amira", 20123456, "Contrôle", "Dr Salah Ben Amor", "Suivi"],
        ["02/11/2026", "10h30", None, "Gharbi", "Leila", "98765432", "consultation", "ines chaabane", None],
        ["02/11/2026", "10:45", 20, "Jlassi", "Mehdi", "22333444", None, "Dr. Ines Chaabane", None],  # overlaps row 3
        ["03/11/2026", "08:00", 30, "Sassi", "Nour", None, None, None, None],  # new patient without phone
        ["03/11/2026", "09:00", 30, "Riahi", "Anis", "22000111", None, "Dr. Inconnu", None],
        ["04/11/2026", "09:00", 30, "Trabelsi", "Amira", "20123456", None, None, None],  # overlaps an existing one
        ["05/11/2026", "11:00", 30, "Trabelsi", "Amira", None, None, None, None],  # found by name alone
    ]))


APPT_MAPPING = {"date": 0, "time": 1, "durationMin": 2, "lastName": 3, "firstName": 4, "phone": 5, "service": 6,
                "practitioner": 7, "notes": 8}


def test_appointments_import(client: TestClient, db: Engine, owner: Any, make_patient: Factory, make_appointment: Factory,
                             make_service: Factory, auth_headers: Factory) -> None:
    p = _pid(owner)
    amira = make_patient(p, first_name="Amira", last_name="Trabelsi", phone="+21620123456")
    make_appointment(amira, starts_at=datetime(2026, 11, 4, 8, 15, tzinfo=UTC), duration_min=30)  # 09:15 Tunis, her own
    control = make_service(p, "Contrôle", 15)
    consult = make_service(p, "Consultation", 25)
    h = auth_headers(owner)
    job = upload(client, h, _appointments_file(), "rdv.xlsx").json()["id"]
    preview = client.post(f"/api/imports/{job}/preview", json={"kind": "appointments", "mapping": APPT_MAPPING}, headers=h).json()
    assert (preview["willCreate"], preview["willSkip"], preview["errorCount"], preview["willCreatePatients"]) == (3, 2, 2, 1)
    assert preview["conflicts"] == [
        {"row": 4, "startsAt": "2026-11-02T10:45:00+01:00", "message": "Chevauchement avec un autre rendez-vous."},
        {"row": 7, "startsAt": "2026-11-04T09:00:00+01:00", "message": "Chevauchement avec un autre rendez-vous."},
    ]
    assert [(e["row"], e["field"]) for e in preview["errors"]] == [(5, "phone"), (6, "practitioner")]
    assert _count(db, appointment) == 1

    res = client.post(f"/api/imports/{job}/commit", json={"kind": "appointments", "mapping": APPT_MAPPING}, headers=h)
    assert res.json() == {"created": 3, "updated": 0, "skipped": 2, "errorCount": 2, "patientsCreated": 1}
    assert 'daftar_appointments_created_total{source="import"} 3.0' in client.get("/metrics").text
    with db.connect() as conn:
        rows = conn.execute(select(appointment).where(appointment.c.id != 1).order_by(appointment.c.starts_at)).all()
        leila = conn.execute(select(patient).where(patient.c.first_name == "Leila")).one()
    past, leila_appt, amira_later = rows
    ines = next(x for x in owner_practitioners(db, owner) if x.name == "Dr. Ines Chaabane")
    salah = next(x for x in owner_practitioners(db, owner) if x.name == "Dr. Salah Ben Amor")
    assert (past.patient_id, past.status, past.service_id, past.duration_min, past.practitioner_id, past.notes) == (
        amira.id, "done", control.id, 30, salah.id, "Suivi")
    assert past.starts_at == datetime(2026, 10, 20, 8, 0, tzinfo=UTC)
    assert (leila_appt.patient_id, leila_appt.status, leila_appt.service_id, leila_appt.duration_min, leila_appt.practitioner_id) == (
        leila.id, "scheduled", consult.id, 25, ines.id)
    assert (leila.phone, leila.lang) == ("+21698765432", "fr")
    assert (amira_later.patient_id, amira_later.duration_min) == (amira.id, 30)
    assert amira_later.practitioner_id == salah.id  # no practitioner in the file: the first free one (code review H1)
    assert all(r.source == "staff" and r.created_by == owner.id for r in rows)


def test_a_rdv_column_of_days_takes_the_time_column(client: TestClient, db: Engine, owner: Any, auth_headers: Factory) -> None:
    """Code review M5 (all visits at 00:00) and N10 ("05/01/27" became 1927 and "done")."""
    data = xlsx(("RDV", [["RDV", "Heure", "Nom", "Prénom", "Tél"],
                         [datetime(2026, 11, 5), "09:00", "Trabelsi", "Amira", "20123456"],
                         [datetime(2026, 11, 5), "09:30", "Gharbi", "Leila", "98765432"],
                         ["05/01/27", "10:00", "Jlassi", "Mehdi", "22333444"]]))
    h = auth_headers(owner)
    up = upload(client, h, data, "rdv.xlsx").json()
    suggested = up["suggestedMapping"]
    assert (suggested["date"], suggested["time"], suggested["datetime"]) == (0, 1, None)
    saved_before = {"datetime": 0, "time": 1, "lastName": 2, "firstName": 3, "phone": 4}  # a template from before the fix
    res = client.post(f"/api/imports/{up['id']}/commit", json={"kind": "appointments", "mapping": saved_before}, headers=h)
    assert res.json() == {"created": 3, "updated": 0, "skipped": 0, "errorCount": 0, "patientsCreated": 3}
    with db.connect() as conn:
        rows = conn.execute(select(appointment.c.starts_at, appointment.c.status).order_by(appointment.c.starts_at)).all()
    assert [tuple(r) for r in rows] == [
        (datetime(2026, 11, 5, 8, 0, tzinfo=UTC), "scheduled"), (datetime(2026, 11, 5, 8, 30, tzinfo=UTC), "scheduled"),
        (datetime(2027, 1, 5, 9, 0, tzinfo=UTC), "scheduled")]


def test_imported_appointments_without_practitioner_get_the_only_one(
    client: TestClient, db: Engine, make_practice: Factory, make_user: Factory, make_patient: Factory,
    make_appointment: Factory, auth_headers: Factory,
) -> None:
    """Code review H1: no appointment next to the doctor's calendar – an overlap with the doctor is listed, not imported."""
    p = make_practice(practitioners=["Dr. X"])
    (x,) = p.practitioners
    make_appointment(make_patient(p), practitioner_id=x.id, starts_at=datetime(2026, 11, 4, 8, 0, tzinfo=UTC))  # 09:00
    h = auth_headers(make_user(p, "owner"))
    data = xlsx(("RDV", [["Date", "Heure", "Nom", "Prénom", "Tél"],
                         ["04/11/2026", "09:00", "Trabelsi", "Amira", "20123456"],
                         ["04/11/2026", "10:00", "Gharbi", "Leila", "98765432"]]))
    job = upload(client, h, data, "rdv.xlsx").json()["id"]
    mapping = {"date": 0, "time": 1, "lastName": 2, "firstName": 3, "phone": 4}
    res = client.post(f"/api/imports/{job}/commit", json={"kind": "appointments", "mapping": mapping}, headers=h)
    assert res.json() == {"created": 1, "updated": 0, "skipped": 1, "errorCount": 0, "patientsCreated": 1}
    with db.connect() as conn:
        rows = conn.execute(select(appointment.c.practitioner_id).order_by(appointment.c.starts_at)).scalars().all()
    assert rows == [x.id, x.id]


def owner_practitioners(db: Engine, owner: Any) -> list[Any]:
    from daftar.tables import practitioner

    with db.connect() as conn:
        return conn.execute(select(practitioner).where(practitioner.c.practice_id == owner.practice_id)).all()


def test_appointment_mapping_needs_date_time_and_name(client: TestClient, owner: Any, auth_headers: Factory) -> None:
    h = auth_headers(owner)
    job = upload(client, h, _appointments_file(), "rdv.xlsx").json()["id"]
    for mapping in ({"date": 0, "lastName": 3, "firstName": 4}, {"time": 1, "fullName": 3}, {"date": 0, "time": 1}):
        res = client.post(f"/api/imports/{job}/preview", json={"kind": "appointments", "mapping": mapping}, headers=h)
        assert_problem(res, 422, "missing_required_field")
    assert_problem(client.post(f"/api/imports/{job}/preview", json={"kind": "appointments", "mapping": {
        "date": 0, "time": 1, "fullName": 3, "openingBalance": 2}}, headers=h), 422, "unknown_field")


# --- report ----------------------------------------------------------------------------------------------------

def test_report_csv_lists_problems_and_defuses_formulas(client: TestClient, owner: Any, make_patient: Factory,
                                                        auth_headers: Factory) -> None:
    make_patient(_pid(owner), first_name="Amira", last_name="Trabelsi", phone="+21620123456")
    data = csv_bytes([
        "Nom;Prénom;Tél",
        "Trabelsi;Amira;20123456",
        '=HYPERLINK("http://evil");@SUM(A1);+21612',
        "Gharbi;-Leila;-1",
    ])
    h = auth_headers(owner)
    job = upload(client, h, data, "x.csv").json()["id"]
    assert_problem(client.get(f"/api/imports/{job}/report.csv", headers=h), 409, "import_not_committed")
    client.post(f"/api/imports/{job}/commit", json={"kind": "patients", "mapping": {"lastName": 0, "firstName": 1, "phone": 2}}, headers=h)
    res = client.get(f"/api/imports/{job}/report.csv", headers=h)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/csv")
    assert res.headers["content-disposition"] == 'attachment; filename="rapport-import-2026-10-30.csv"'
    assert res.content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(res.content.decode("utf-8-sig")), delimiter=";"))
    assert rows[0] == ["Ligne", "Champ", "Message", "Valeur"]
    assert ["2", "Doublon", "Patient déjà présent (ignoré) : Amira Trabelsi", ""] in rows
    assert ["3", "Téléphone", "Numéro de téléphone invalide.", "'+21612"] in rows
    assert ["4", "Téléphone", "Numéro de téléphone invalide.", "'-1"] in rows
    for row in rows[1:]:
        for cell in row:
            assert not cell.startswith(("=", "+", "-", "@", "\t", "\r")), cell


# --- templates -------------------------------------------------------------------------------------------------

def test_templates(client: TestClient, make_practice: Factory, make_user: Factory, auth_headers: Factory) -> None:
    p = make_practice()
    h = auth_headers(make_user(p, "assistant"))
    res = client.post("/api/import-templates", json={"name": "Mon Excel", "kind": "patients", "mapping": MAPPING,
                                                     "options": {"duplicates": "update"}}, headers=h)
    assert res.status_code == 201, res.text
    tpl = res.json()
    assert (tpl["name"], tpl["kind"], tpl["mapping"]) == ("Mon Excel", "patients", MAPPING)
    assert tpl["options"]["duplicates"] == "update" and tpl["options"]["nameOrder"] == "last_first"
    assert [t["id"] for t in client.get("/api/import-templates", headers=h).json()] == [tpl["id"]]
    other = auth_headers(make_user(role="owner"))
    assert client.get("/api/import-templates", headers=other).json() == []
    assert_problem(client.delete(f"/api/import-templates/{tpl['id']}", headers=other), 404, "not_found")
    assert client.delete(f"/api/import-templates/{tpl['id']}", headers=h).status_code == 204
    assert client.get("/api/import-templates", headers=h).json() == []


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"name": "", "kind": "patients", "mapping": {}}, "validation"),
        ({"name": "x", "kind": "factures", "mapping": {}}, "validation"),
        ({"name": "x", "kind": "patients", "mapping": {"date": 1}}, "unknown_field"),
        ({"name": "x", "kind": "patients", "mapping": {"phone": -2}}, "invalid_column"),
        ({"name": "x", "kind": "patients", "mapping": {"phone": 100}}, "invalid_column"),
    ],
)
def test_template_validation(client: TestClient, owner: Any, auth_headers: Factory, body: dict[str, Any], code: str) -> None:
    assert_problem(client.post("/api/import-templates", json=body, headers=auth_headers(owner)), 422, code)


def test_template_roles(client: TestClient, make_practice: Factory, make_user: Factory, auth_headers: Factory) -> None:
    p = make_practice()
    assert_problem(client.get("/api/import-templates", headers=auth_headers(make_user(p, "dentist"))), 403, "forbidden")
    suspended = auth_headers(make_user(make_practice(status="suspended"), "owner"))
    assert client.get("/api/import-templates", headers=suspended).status_code == 200
    assert_problem(client.post("/api/import-templates", json={"name": "x", "kind": "patients", "mapping": {}}, headers=suspended),
                   402, "subscription_suspended")


# --- cleanup ---------------------------------------------------------------------------------------------------

def test_expired_imports_are_deleted(client: TestClient, db: Engine, owner: Any, auth_headers: Factory, clock: Any) -> None:
    h = auth_headers(owner)
    old = upload(client, h).json()["id"]
    clock.advance(hours=23)
    fresh = upload(client, h).json()["id"]
    clock.advance(hours=1, seconds=1)
    assert_problem(client.post(f"/api/imports/{old}/sheet", json={"sheet": "Patients", "headerRow": 1}, headers=h), 404, "not_found")
    with db.begin() as conn:
        assert delete_expired_imports(conn, clock.now()) == 1
    with db.connect() as conn:
        assert [str(i) for i in conn.execute(select(import_job.c.id)).scalars()] == [fresh]


def test_the_import_cleanup_job_is_registered() -> None:
    from daftar.jobs import JOBS

    assert any(job.name == "import-cleanup" for job in JOBS)


def test_committed_imports_keep_only_the_report(client: TestClient, db: Engine, owner: Any, auth_headers: Factory) -> None:
    h = auth_headers(owner)
    job = upload(client, h).json()["id"]
    client.post(f"/api/imports/{job}/commit", json={"kind": "patients", "mapping": MAPPING}, headers=h)
    with db.begin() as conn:
        conn.execute(update(import_job).values(expires_at=T0 - timedelta(seconds=1)))
        assert delete_expired_imports(conn, T0) == 1
