# Daftar – Backend

Python 3.13 · FastAPI · SQLAlchemy 2 **Core** (kein ORM) · psycopg 3 · Alembic · PyJWT · argon2-cffi · prometheus-client.
Ein Prozess liefert `/api/*`, `/healthz`, `/metrics`, die Landing (`landing/`) und die SPA (`web/build`).

## Starten und testen

```bash
cd backend
py -3.13 -m venv .venv            # Linux/macOS: python3.13 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
docker run -d --name daftar-postgres -e POSTGRES_PASSWORD=daftar -e POSTGRES_USER=daftar -p 55436:5432 postgres:17-alpine
.venv/Scripts/python -m pytest                      # legt daftar_test an, migriert einmal, leert Tabellen je Test
.venv/Scripts/python -m tests.mutation_check        # optional: beweist, dass die Tests echte Fehler finden (~10 min)

# Server lokal (Port 8080 ist auf Omars Rechner belegt):
set DATABASE_URL=postgresql+psycopg://daftar:daftar@localhost:55436/daftar
set JWT_SECRET=lokal-nur-zum-entwickeln-0123456789abcdef
set ADMIN_EMAIL=admin@daftar.test & set ADMIN_PASSWORD=local-admin-password-123 & set PORT=18084
.venv/Scripts/alembic upgrade head && .venv/Scripts/python -m daftar
```

`TEST_DATABASE_URL` überschreibt die Test-DB (Standard `postgresql+psycopg://daftar:daftar@localhost:55436/daftar_test`).

## Aufbau (`daftar/`)

| Datei | Inhalt |
|---|---|
| `app.py` | `create_app(settings, clock=None, *, engine=None, run_jobs=True)` – verdrahtet alles, statische Weiche, Manifeste |
| `routers.py` | **die eine Stelle**, an der API-Router registriert werden (`ROUTERS`) |
| `settings.py` | `Settings.from_env()` – `DATABASE_URL`, `JWT_SECRET` (≥ 32), `ADMIN_*`, `PORT`, `BASE_DOMAIN`, `FLOUCI_*`, `LANDING_DIR`, `WEB_DIR` |
| `context.py` | `AppContext` (settings, clock, engine, metrics, tokens, login_throttle, `limiter(...)`) |
| `deps.py` | FastAPI-Abhängigkeiten: `Ctx`, `Conn`, `ClientIp`, `CurrentUser`, `StaffUser`, `StaffWriter`, `OwnerUser`, `PractitionerUser`, `AdminUser`, `require_roles` |
| `tables.py` | SQLAlchemy-Core-Tabellen (Spiegel der Migration), Status-Konstanten, Constraint-Namen |
| `schemas.py` | `ApiModel` (camelCase), `TunisDateTime`, `InstantIn`, `Name`, `Text`, `Email`, `Role`, `Lang` |
| `problems.py` | `ApiError` + `bad_request`, `not_found`, `conflict`, `forbidden`, `unauthorized`, `unprocessable`, `too_many_requests` |
| `clock.py` | `Clock`, `SystemClock`, `FixedClock`, `today_tunis`, `now_tunis`, `tunis_day_bounds`, `at_tunis`, `iso_tunis` |
| `phone.py` | `normalize_phone`, `phone_digits`, Pydantic-Typen `Phone`, `OptionalPhone` |
| `money.py` | `Millimes`, `PositiveMillimes`, `dinars()`, `format_millimes()` |
| `hours.py` | `DEFAULT_WEEKLY_HOURS`, Typ `WeeklyHours`, `windows_for(hours, day)`, `agenda_range(hours)` |
| `slugs.py` | `slug_problem`, `suggest_slug`, `demo_slug`, `RESERVED_SLUGS` |
| `catalog.py` | `SPECIALTIES`, `DEFAULT_CATALOGS`, `insert_default_services(conn, practice_id, specialty)` |
| `tunisia.py` | `GOVERNORATES` (24 Codes) |
| `throttle.py` | `LoginThrottle`, `RateLimiter` |
| `metrics.py` | `Metrics` (eigene Registry je App, `counter/gauge/histogram` get-or-create) |
| `jobs.py` | `Job(name, every, run)` und die Liste `JOBS` |
| `auth.py` | `/api/auth/*`, `load_me`, `session_for`, `issue_token`, `bump_token_version` |
| `invitations.py` | `/api/invitations/preview|accept`, `create_invitation(...)`, `delete_stale_invitations(...)` |
| `hosts.py` | Hosts: Hauptdomain, App-Host `app.<BASE_DOMAIN>` (`is_app_host`, `site_origin`), Praxis-Subdomains (`subdomain_label`, `practice_by_slug`, `practice_for_host`), `GET /api/public/tls-check` |
| `branding.py` | Manifeste und Icons je Praxis (`initials`, `short_name`, `render_icon`) |
| `static.py`, `http.py` | Auslieferung je Host (Hauptdomain: Landing + 301 der App-Pfade; `app.`: SPA; Praxis), CSP, HSTS, Sicherheits-Header, Request-Log, HTTP-Metriken |

## Ein Fachmodul anlegen

```python
# daftar/patients.py
from fastapi import APIRouter
from sqlalchemy import insert, select

from .deps import Conn, Ctx, StaffUser, StaffWriter
from .phone import Phone
from .problems import not_found
from .schemas import ApiModel, Name, Text, TunisDateTime
from .tables import patient

router = APIRouter(prefix="/api/patients", tags=["patients"])


class PatientIn(ApiModel):
    first_name: Name
    last_name: Name
    phone: Phone            # normalisiert, 422 code "invalid_phone"
    notes: Text = ""


class PatientOut(ApiModel):
    id: int
    first_name: str
    last_name: str
    phone: str
    created_at: TunisDateTime   # "2026-10-30T09:30:00+01:00"


@router.post("", status_code=201)
def create(body: PatientIn, user: StaffWriter, ctx: Ctx, conn: Conn) -> PatientOut:
    row = conn.execute(
        insert(patient).values(practice_id=user.pid, created_at=ctx.clock.now(), **body.model_dump(by_alias=False))
        .returning(patient)
    ).one()
    return PatientOut.model_validate(row, from_attributes=True)


@router.get("/{patient_id}")
def get(patient_id: int, user: StaffUser, conn: Conn) -> PatientOut:
    row = conn.execute(select(patient).where(patient.c.id == patient_id, patient.c.practice_id == user.pid)).first()
    if row is None:
        raise not_found()   # auch für fremde Praxen – nie 403
    return PatientOut.model_validate(row, from_attributes=True)
```

Dann in `daftar/routers.py`: `from . import patients` und `patients.router` in `ROUTERS`.

Regeln: jede Abfrage filtert auf `user.pid`; schreibende Endpunkte nehmen `StaffWriter` (402 bei gesperrtem Abo);
Zeit nur über `ctx.clock`; Geld nur in Millimes; Fehler nur über `problems.py` (mit `code`, den das Web übersetzt).
Überschneidende Termine wirft die Datenbank ab (`IntegrityError`, `daftar.db.constraint_name(exc)` ist
`appointment_practitioner_no_overlap` bzw. `appointment_patient_no_overlap`) → 409 mit den Konflikten.

## Tests schreiben

Fixtures aus `tests/conftest.py`: `client`, `app`, `db`, `clock` (`FixedClock`, Fr 30.10.2026 09:00 Tunis),
`settings`, `make_practice`, `make_practitioner`, `make_service`, `make_user`, `auth_headers`, `make_patient`,
`make_appointment`, `make_queue_entry`, `make_treatment`, `make_payment`, `make_invitation`;
Helfer in `tests/helpers.py`: `assert_problem(res, status, code)`, `login(client, email, password, ip, host=APP_HOST)`
(angemeldet wird auf `app.daftar.omarfourati.de`; auf der Hauptdomain geht das nicht).

```python
def test_foreign_practice_is_404(client, make_practice, make_user, make_patient, auth_headers):
    mine, other = make_practice(), make_practice()
    stranger = make_patient(other)
    res = client.get(f"/api/patients/{stranger.id}", headers=auth_headers(make_user(mine, "assistant")))
    assert_problem(res, 404, "not_found")
```

## Migrationen

`migrations/versions/0001_initial.py` enthält das komplette Schema (Abschnitte 4, 11–14, Backlog), `0002` die
Ergänzungen aus Abschnitt 15 (`practice.onboarding`, `patient.alerts` ≤ 500). Neue Änderungen: `0003_…` mit
`down_revision = "0002"`, Tabellen in `tables.py` spiegeln (der Test `test_tables_py_mirrors_the_migrated_schema`
prüft das).
