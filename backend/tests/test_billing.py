"""Subscriptions (section 11.4): plans, invoices with gapless numbers, the daily job, owner billing page with Flouci,
admin overview and manual payments. Flouci is replaced by a fake provider here (see tests/test_flouci.py)."""

import threading
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, insert, select

from daftar.billing import add_months, create_invoice, next_invoice_number, run_billing
from daftar.payment_provider import CreatedPayment, VerifiedPayment
from daftar.tables import invoice, practice
from tests.conftest import T0
from tests.helpers import assert_problem

Factory = Callable[..., Any]
TODAY = date(2026, 10, 30)


class FakeProvider:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.payments: dict[str, VerifiedPayment] = {}
        self.verified: list[str] = []

    def create_payment(self, **request: Any) -> CreatedPayment:
        self.created.append(request)
        pid = f"pay{len(self.created)}"
        return CreatedPayment(payment_id=pid, link=f"https://checkout.flouci.example/{pid}")

    def verify_payment(self, payment_id: str) -> VerifiedPayment:
        self.verified.append(payment_id)
        return self.payments.get(payment_id, VerifiedPayment(status="PENDING", amount_millimes=0, tracking_id=None))

    def check_signature(self, header: str | None, body: bytes, now: datetime) -> bool:
        return header == "valid"


@pytest.fixture
def fake(app: Any) -> FakeProvider:
    provider = FakeProvider()
    app.state.payment_provider = provider
    return provider


def _invoice(db: Engine, practice_row: Any, number: str = "DAF-2026-0001", **values: Any) -> Any:
    row = {"practice_id": practice_row.id, "number": number, "plan_code": "cabinet_mensuel",
           "period_start": date(2026, 11, 1), "period_end": date(2026, 11, 30), "amount_millimes": 49_000,
           "due_on": date(2026, 11, 1), "created_at": T0, **values}
    with db.begin() as conn:
        return conn.execute(insert(invoice).values(**row).returning(invoice)).one()


def _practice(db: Engine, practice_id: int) -> Any:
    with db.connect() as conn:
        return conn.execute(select(practice).where(practice.c.id == practice_id)).one()


def _invoices(db: Engine, practice_id: int | None = None) -> list[Any]:
    query = select(invoice).order_by(invoice.c.id)
    if practice_id is not None:
        query = query.where(invoice.c.practice_id == practice_id)
    with db.connect() as conn:
        return conn.execute(query).all()


# --- helpers ---------------------------------------------------------------------------------------------------

def test_add_months_clamps_to_the_end_of_the_month() -> None:
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 11, 15), 2) == date(2027, 1, 15)
    assert add_months(date(2026, 3, 1), 12) == date(2027, 3, 1)


def test_invoice_numbers_count_per_year_and_go_beyond_four_digits(db: Engine, make_practice: Factory) -> None:
    p = make_practice()
    with db.begin() as conn:
        assert next_invoice_number(conn, 2026) == "DAF-2026-0001"
    _invoice(db, p, "DAF-2026-0001")
    _invoice(db, p, "DAF-2026-9999")
    _invoice(db, p, "DAF-2025-0042")
    with db.begin() as conn:
        assert next_invoice_number(conn, 2026) == "DAF-2026-10000"
        assert next_invoice_number(conn, 2025) == "DAF-2025-0043"
        assert next_invoice_number(conn, 2027) == "DAF-2027-0001"


def test_invoice_numbers_are_race_free(db: Engine, make_practice: Factory) -> None:
    """Two transactions creating invoices at the same time never get the same number (advisory lock)."""
    p = make_practice(status="active", plan_code="cabinet_mensuel", paid_until=date(2026, 11, 30))
    first_has_number = threading.Event()
    numbers: list[str] = []
    errors: list[BaseException] = []

    def first() -> None:
        try:
            with db.begin() as conn:
                row = create_invoice(conn, p.id, T0, period_start=date(2026, 12, 1))
                numbers.append(row.number)
                first_has_number.set()
                threading.Event().wait(0.5)  # keep the transaction (and the lock) open a moment
        except BaseException as exc:  # pragma: no cover - reported below
            errors.append(exc)
            first_has_number.set()

    def second() -> None:
        first_has_number.wait()
        try:
            with db.begin() as conn:
                numbers.append(create_invoice(conn, p.id, T0, period_start=date(2027, 1, 1)).number)
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=first), threading.Thread(target=second)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert errors == []
    assert sorted(numbers) == ["DAF-2026-0001", "DAF-2026-0002"]


# --- daily job -------------------------------------------------------------------------------------------------

def test_job_invoices_active_practices_ten_days_before_the_end(db: Engine, make_practice: Factory) -> None:
    due = make_practice(status="active", plan_code="cabinet_mensuel", paid_until=TODAY + timedelta(days=10))
    later = make_practice(status="active", plan_code="cabinet_mensuel", paid_until=TODAY + timedelta(days=11))
    yearly = make_practice(status="active", plan_code="cabinet_annuel", paid_until=TODAY + timedelta(days=3))
    make_practice(status="pilot", plan_code="cabinet_mensuel", paid_until=TODAY)
    make_practice(status="trial", plan_code="cabinet_mensuel", paid_until=TODAY)
    make_practice(status="active", plan_code="pilot", paid_until=TODAY)  # free plan
    make_practice(status="active", plan_code="cabinet_mensuel", paid_until=TODAY, is_demo=True,
                  demo_expires_at=T0 + timedelta(hours=1))
    make_practice(status="active", plan_code="cabinet_mensuel", paid_until=None)
    with db.begin() as conn:
        run_billing(conn, T0)
    with db.begin() as conn:
        run_billing(conn, T0)  # idempotent
    rows = _invoices(db)
    assert [(r.practice_id, r.period_start, r.period_end, r.amount_millimes, r.due_on, r.status) for r in rows] == [
        (due.id, date(2026, 11, 10), date(2026, 12, 9), 49_000, date(2026, 11, 10), "open"),
        (yearly.id, date(2026, 11, 3), date(2027, 11, 2), 490_000, date(2026, 11, 3), "open"),
    ]
    assert [r.number for r in rows] == ["DAF-2026-0001", "DAF-2026-0002"]
    assert all(r.plan_code == _practice(db, r.practice_id).plan_code for r in rows)
    assert not _invoices(db, later.id)


def test_job_does_not_invoice_a_period_twice_but_after_a_void(db: Engine, make_practice: Factory) -> None:
    p = make_practice(status="active", plan_code="cabinet_mensuel", paid_until=TODAY + timedelta(days=5))
    _invoice(db, p, "DAF-2026-0007", period_start=TODAY + timedelta(days=6), status="void")
    with db.begin() as conn:
        run_billing(conn, T0)
    assert [r.status for r in _invoices(db, p.id)] == ["void", "open"]


def test_job_moves_late_practices_to_past_due_and_then_suspends(db: Engine, make_practice: Factory) -> None:
    on_time = make_practice(status="active", plan_code="cabinet_mensuel", paid_until=TODAY)
    late = make_practice(status="active", plan_code="cabinet_mensuel", paid_until=TODAY - timedelta(days=1))
    grace = make_practice(status="past_due", plan_code="cabinet_mensuel", paid_until=TODAY - timedelta(days=14))
    over = make_practice(status="past_due", plan_code="cabinet_mensuel", paid_until=TODAY - timedelta(days=15))
    very_late = make_practice(status="active", plan_code="cabinet_mensuel", paid_until=TODAY - timedelta(days=40))
    pilot = make_practice(status="pilot", plan_code="pilot", paid_until=TODAY - timedelta(days=40))
    with db.begin() as conn:
        run_billing(conn, T0)
    status = {p.id: _practice(db, p.id).status for p in (on_time, late, grace, over, very_late, pilot)}
    assert status == {on_time.id: "active", late.id: "past_due", grace.id: "past_due", over.id: "suspended",
                      very_late.id: "suspended", pilot.id: "pilot"}


def test_the_billing_job_is_registered() -> None:
    from daftar.jobs import JOBS

    assert any(job.name == "billing" for job in JOBS)


# --- owner -----------------------------------------------------------------------------------------------------

def test_owner_sees_plan_status_and_invoices(client: TestClient, db: Engine, make_practice: Factory, make_user: Factory,
                                             auth_headers: Factory) -> None:
    p = make_practice(status="active", plan_code="cabinet_mensuel", paid_until=date(2026, 10, 31))
    owner = make_user(p, "owner")
    old = _invoice(db, p, "DAF-2026-0001", period_start=date(2026, 10, 1), period_end=date(2026, 10, 31),
                   status="paid", paid_at=T0 - timedelta(days=30), method="virement")
    new = _invoice(db, p, "DAF-2026-0002")
    _invoice(db, make_practice(), "DAF-2026-0003")  # another practice
    res = client.get("/api/billing", headers=auth_headers(owner))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["plan"] == {"code": "cabinet_mensuel", "nameFr": "Cabinet – mensuel", "nameAr": "العيادة – شهري",
                            "priceMillimes": 49_000, "periodMonths": 1}
    assert (body["status"], body["paidUntil"], body["onlinePaymentAvailable"]) == ("active", "2026-10-31", False)
    assert [pl["code"] for pl in body["plans"]] == ["pilot", "cabinet_mensuel", "cabinet_annuel"]
    assert [i["id"] for i in body["invoices"]] == [new.id, old.id]
    assert body["invoices"][1] == {"id": old.id, "number": "DAF-2026-0001", "planCode": "cabinet_mensuel",
                                   "periodStart": "2026-10-01", "periodEnd": "2026-10-31", "amountMillimes": 49_000,
                                   "status": "paid", "dueOn": "2026-11-01", "paidAt": "2026-09-30T09:00:00+01:00",
                                   "method": "virement", "createdAt": "2026-10-30T09:00:00+01:00"}


def test_online_payment_is_available_with_a_provider(client: TestClient, fake: FakeProvider, make_user: Factory,
                                                      auth_headers: Factory) -> None:
    assert client.get("/api/billing", headers=auth_headers(make_user())).json()["onlinePaymentAvailable"] is True


def test_billing_is_for_the_owner_also_when_suspended(client: TestClient, make_practice: Factory, make_user: Factory,
                                                      auth_headers: Factory) -> None:
    p = make_practice(status="suspended")
    assert client.get("/api/billing", headers=auth_headers(make_user(p, "owner"))).status_code == 200
    for role in ("dentist", "assistant", "admin"):
        assert_problem(client.get("/api/billing", headers=auth_headers(make_user(p if role != "admin" else None, role))),
                       403, "forbidden")
    assert_problem(client.get("/api/billing"), 401, "unauthorized")


def test_pay_with_flouci(client: TestClient, db: Engine, fake: FakeProvider, make_practice: Factory, make_user: Factory,
                         auth_headers: Factory) -> None:
    p = make_practice(status="suspended", plan_code="cabinet_mensuel")
    inv = _invoice(db, p, "DAF-2026-0005")
    res = client.post(f"/api/billing/invoices/{inv.id}/pay", headers=auth_headers(make_user(p, "owner")))
    assert res.status_code == 200, res.text
    assert res.json() == {"paymentUrl": "https://checkout.flouci.example/pay1"}
    (request,) = fake.created
    assert request == {
        "amount_millimes": 49_000,
        "tracking_id": "DAF-2026-0005",
        "success_url": f"https://daftar.omarfourati.de/app/abonnement?invoice={inv.id}&result=success",
        "fail_url": f"https://daftar.omarfourati.de/app/abonnement?invoice={inv.id}&result=fail",
        "webhook_url": "https://daftar.omarfourati.de/api/public/flouci/webhook",
    }
    assert _invoices(db, p.id)[0].provider_payment_id == "pay1"


def test_pay_returns_to_the_practice_subdomain(client: TestClient, db: Engine, fake: FakeProvider, make_practice: Factory,
                                               make_user: Factory, auth_headers: Factory) -> None:
    p = make_practice(slug="cabinet-lac")
    inv = _invoice(db, p)
    headers = {**auth_headers(make_user(p, "owner")), "Host": "cabinet-lac.daftar.omarfourati.de"}
    assert client.post(f"/api/billing/invoices/{inv.id}/pay", headers=headers).status_code == 200
    assert fake.created[0]["success_url"].startswith("https://cabinet-lac.daftar.omarfourati.de/app/abonnement?")
    headers["Host"] = "evil.example"
    client.post(f"/api/billing/invoices/{inv.id}/pay", headers=headers)
    assert fake.created[1]["success_url"].startswith("https://daftar.omarfourati.de/")


def test_pay_errors(client: TestClient, db: Engine, make_practice: Factory, make_user: Factory, auth_headers: Factory,
                    app: Any) -> None:
    p = make_practice()
    owner = auth_headers(make_user(p, "owner"))
    inv = _invoice(db, p)
    assert_problem(client.post(f"/api/billing/invoices/{inv.id}/pay", headers=owner), 409, "online_payment_unavailable")
    app.state.payment_provider = FakeProvider()
    paid = _invoice(db, p, "DAF-2026-0002", status="paid", paid_at=T0)
    assert_problem(client.post(f"/api/billing/invoices/{paid.id}/pay", headers=owner), 409, "invoice_not_open")
    foreign = _invoice(db, make_practice(), "DAF-2026-0003")
    assert_problem(client.post(f"/api/billing/invoices/{foreign.id}/pay", headers=owner), 404, "not_found")
    assert_problem(client.post(f"/api/billing/invoices/{inv.id}/pay", headers=auth_headers(make_user(p, "assistant"))),
                   403, "forbidden")


def test_verify_marks_a_paid_invoice_and_reactivates(client: TestClient, db: Engine, fake: FakeProvider,
                                                     make_practice: Factory, make_user: Factory, auth_headers: Factory) -> None:
    p = make_practice(status="suspended", plan_code="cabinet_mensuel", paid_until=date(2026, 10, 1))
    owner = make_user(p, "owner")
    inv = _invoice(db, p, provider_payment_id="pay9")
    fake.payments["pay9"] = VerifiedPayment(status="PENDING", amount_millimes=49_000, tracking_id=inv.number)
    res = client.post(f"/api/billing/invoices/{inv.id}/verify", headers=auth_headers(owner))
    assert res.status_code == 200, res.text
    assert (res.json()["providerStatus"], res.json()["invoice"]["status"]) == ("PENDING", "open")
    fake.payments["pay9"] = VerifiedPayment(status="SUCCESS", amount_millimes=49_000, tracking_id=inv.number)
    body = client.post(f"/api/billing/invoices/{inv.id}/verify", headers=auth_headers(owner)).json()
    assert (body["providerStatus"], body["invoice"]["status"], body["invoice"]["method"]) == ("SUCCESS", "paid", "flouci")
    assert body["invoice"]["paidAt"] == "2026-10-30T09:00:00+01:00"
    row = _practice(db, p.id)
    assert (row.status, row.paid_until) == ("active", date(2026, 11, 30))
    # writing works again
    assert client.post("/api/patients", json={"firstName": "A", "lastName": "B", "phone": "20123456"},
                       headers=auth_headers(owner)).status_code == 201


def test_verify_refuses_a_wrong_amount(client: TestClient, db: Engine, fake: FakeProvider, make_practice: Factory,
                                       make_user: Factory, auth_headers: Factory) -> None:
    p = make_practice(status="past_due", plan_code="cabinet_mensuel")
    inv = _invoice(db, p, provider_payment_id="pay1")
    fake.payments["pay1"] = VerifiedPayment(status="SUCCESS", amount_millimes=1_000, tracking_id=inv.number)
    res = client.post(f"/api/billing/invoices/{inv.id}/verify", headers=auth_headers(make_user(p, "owner")))
    assert_problem(res, 409, "payment_mismatch")
    assert _invoices(db, p.id)[0].status == "open" and _practice(db, p.id).status == "past_due"


def test_verify_needs_a_started_payment(client: TestClient, db: Engine, fake: FakeProvider, make_practice: Factory,
                                        make_user: Factory, auth_headers: Factory) -> None:
    p = make_practice()
    inv = _invoice(db, p)
    assert_problem(client.post(f"/api/billing/invoices/{inv.id}/verify", headers=auth_headers(make_user(p, "owner"))),
                   409, "payment_not_started")
    assert fake.verified == []


# --- webhook ---------------------------------------------------------------------------------------------------

WEBHOOK = "/api/public/flouci/webhook"


def test_webhook_verifies_with_flouci_and_never_trusts_the_body(client: TestClient, db: Engine, fake: FakeProvider,
                                                                make_practice: Factory) -> None:
    p = make_practice(status="past_due", plan_code="cabinet_mensuel", paid_until=date(2026, 10, 20))
    inv = _invoice(db, p, "DAF-2026-0004", provider_payment_id="pay1")
    claim = {"event": "payment.succeeded", "payment_id": "pay1", "amount": 49_000, "developer_tracking_id": inv.number}
    fake.payments["pay1"] = VerifiedPayment(status="FAILURE", amount_millimes=49_000, tracking_id=inv.number)
    res = client.post(WEBHOOK, json=claim, headers={"X-Flouci-Signature": "valid"})
    assert res.status_code == 200, res.text
    assert fake.verified == ["pay1"] and _invoices(db, p.id)[0].status == "open"
    fake.payments["pay1"] = VerifiedPayment(status="SUCCESS", amount_millimes=49_000, tracking_id=inv.number)
    assert client.post(WEBHOOK, json={**claim, "event": "payment.failed"}, headers={"X-Flouci-Signature": "valid"}).status_code == 200
    row = _invoices(db, p.id)[0]
    assert (row.status, row.method) == ("paid", "flouci")
    assert _practice(db, p.id).status == "active"
    # a repeated delivery changes nothing
    assert client.post(WEBHOOK, json=claim, headers={"X-Flouci-Signature": "valid"}).status_code == 200


def test_webhook_finds_the_invoice_through_the_verified_tracking_id(client: TestClient, db: Engine, fake: FakeProvider,
                                                                    make_practice: Factory) -> None:
    p = make_practice(status="active", plan_code="cabinet_mensuel")
    inv = _invoice(db, p, "DAF-2026-0004", provider_payment_id="pay-newer")
    fake.payments["pay-older"] = VerifiedPayment(status="SUCCESS", amount_millimes=49_000, tracking_id=inv.number)
    client.post(WEBHOOK, json={"payment_id": "pay-older"}, headers={"X-Flouci-Signature": "valid"})
    assert _invoices(db, p.id)[0].status == "paid"


def test_webhook_ignores_a_verified_payment_with_another_amount(client: TestClient, db: Engine, fake: FakeProvider,
                                                                make_practice: Factory) -> None:
    p = make_practice(status="past_due", plan_code="cabinet_mensuel")
    inv = _invoice(db, p, "DAF-2026-0004", provider_payment_id="pay1")
    fake.payments["pay1"] = VerifiedPayment(status="SUCCESS", amount_millimes=1_000, tracking_id=inv.number)
    assert client.post(WEBHOOK, json={"payment_id": "pay1"}, headers={"X-Flouci-Signature": "valid"}).status_code == 200
    assert _invoices(db, p.id)[0].status == "open" and _practice(db, p.id).status == "past_due"


def test_webhook_rejects_bad_signatures_and_ignores_unknown_payments(client: TestClient, fake: FakeProvider) -> None:
    assert_problem(client.post(WEBHOOK, json={"payment_id": "pay1"}), 400, "invalid_signature")
    assert_problem(client.post(WEBHOOK, json={"payment_id": "pay1"}, headers={"X-Flouci-Signature": "forged"}), 400,
                   "invalid_signature")
    assert fake.verified == []
    assert client.post(WEBHOOK, json={"payment_id": "unknown"}, headers={"X-Flouci-Signature": "valid"}).status_code == 200
    assert_problem(client.post(WEBHOOK, content=b"not json", headers={"X-Flouci-Signature": "valid"}), 400, "bad_request")
    assert_problem(client.post(WEBHOOK, json={"payment_id": 5}, headers={"X-Flouci-Signature": "valid"}), 400, "bad_request")


def test_webhook_without_flouci_keys_is_404(client: TestClient) -> None:
    assert_problem(client.post(WEBHOOK, json={"payment_id": "pay1"}, headers={"X-Flouci-Signature": "valid"}), 404, "not_found")


def test_webhook_is_rate_limited(client: TestClient, fake: FakeProvider) -> None:
    headers = {"X-Flouci-Signature": "forged", "X-Forwarded-For": "9.9.9.9"}
    for _ in range(60):
        client.post(WEBHOOK, json={"payment_id": "x"}, headers=headers)
    assert_problem(client.post(WEBHOOK, json={"payment_id": "x"}, headers=headers), 429, "too_many_requests")


# --- admin -----------------------------------------------------------------------------------------------------

def test_admin_overview(client: TestClient, db: Engine, make_practice: Factory, make_user: Factory, auth_headers: Factory) -> None:
    a = make_practice("Cabinet A", status="past_due", plan_code="cabinet_mensuel", paid_until=date(2026, 10, 20))
    b = make_practice("Cabinet B")
    make_practice("Démo", is_demo=True, demo_expires_at=T0 + timedelta(hours=1))
    _invoice(db, a, "DAF-2026-0001")
    _invoice(db, a, "DAF-2026-0002", status="paid", paid_at=T0)
    _invoice(db, a, "DAF-2026-0003", status="void")
    res = client.get("/api/admin/billing", headers=auth_headers(make_user(role="admin")))
    assert res.status_code == 200, res.text
    rows = res.json()
    invoices = [row.pop("invoices") for row in rows]
    assert rows == [
        {"practiceId": a.id, "name": "Cabinet A", "slug": a.slug, "planCode": "cabinet_mensuel", "status": "past_due",
         "paidUntil": "2026-10-20", "openInvoices": 1, "openMillimes": 49_000},
        {"practiceId": b.id, "name": "Cabinet B", "slug": b.slug, "planCode": "pilot", "status": "pilot",
         "paidUntil": None, "openInvoices": 0, "openMillimes": 0},
    ]
    # the admin needs the invoices themselves to record a bank transfer or void one (web /app/admin/abonnements)
    assert [(i["number"], i["status"]) for i in invoices[0]] == [
        ("DAF-2026-0003", "void"), ("DAF-2026-0002", "paid"), ("DAF-2026-0001", "open")]
    assert invoices[0][2]["amountMillimes"] == 49_000 and invoices[0][2]["dueOn"] == "2026-11-01"
    assert invoices[1] == []


def test_admin_overview_lists_at_most_twelve_invoices_per_practice(
        client: TestClient, db: Engine, make_practice: Factory, make_user: Factory, auth_headers: Factory) -> None:
    a = make_practice("Cabinet A", plan_code="cabinet_mensuel")
    for n in range(1, 15):
        _invoice(db, a, f"DAF-2026-{n:04d}", status="paid", paid_at=T0)
    res = client.get("/api/admin/billing", headers=auth_headers(make_user(role="admin")))
    numbers = [i["number"] for i in res.json()[0]["invoices"]]
    assert numbers == [f"DAF-2026-{n:04d}" for n in range(14, 2, -1)]


def test_admin_creates_the_next_invoice(client: TestClient, db: Engine, make_practice: Factory, make_user: Factory,
                                        auth_headers: Factory) -> None:
    admin = auth_headers(make_user(role="admin"))
    renewing = make_practice(status="active", plan_code="cabinet_annuel", paid_until=date(2026, 12, 31))
    res = client.post(f"/api/admin/practices/{renewing.id}/invoices", headers=admin)
    assert res.status_code == 201, res.text
    assert (res.json()["periodStart"], res.json()["periodEnd"], res.json()["amountMillimes"], res.json()["number"]) == (
        "2027-01-01", "2027-12-31", 490_000, "DAF-2026-0001")
    assert_problem(client.post(f"/api/admin/practices/{renewing.id}/invoices", headers=admin), 409, "invoice_exists")
    starting = make_practice(status="trial", plan_code="cabinet_mensuel")
    body = client.post(f"/api/admin/practices/{starting.id}/invoices", headers=admin).json()
    assert (body["periodStart"], body["periodEnd"], body["dueOn"]) == ("2026-10-30", "2026-11-29", "2026-10-30")
    assert_problem(client.post(f"/api/admin/practices/{make_practice().id}/invoices", headers=admin), 422, "plan_is_free")
    assert_problem(client.post("/api/admin/practices/999999/invoices", headers=admin), 404, "not_found")


def test_admin_marks_an_invoice_paid(client: TestClient, db: Engine, make_practice: Factory, make_user: Factory,
                                     auth_headers: Factory) -> None:
    admin = auth_headers(make_user(role="admin"))
    p = make_practice(status="suspended", plan_code="cabinet_mensuel", paid_until=date(2026, 12, 15))
    inv = _invoice(db, p)
    assert_problem(client.post(f"/api/admin/invoices/{inv.id}/mark-paid", json={"method": "cash"}, headers=admin), 422, "validation")
    res = client.post(f"/api/admin/invoices/{inv.id}/mark-paid", json={"method": "virement"}, headers=admin)
    assert res.status_code == 200, res.text
    assert (res.json()["status"], res.json()["method"]) == ("paid", "virement")
    row = _practice(db, p.id)
    assert (row.status, row.paid_until) == ("active", date(2026, 12, 15))  # never shortened
    assert_problem(client.post(f"/api/admin/invoices/{inv.id}/mark-paid", json={"method": "especes"}, headers=admin),
                   409, "invoice_not_open")
    assert_problem(client.post("/api/admin/invoices/999999/mark-paid", json={"method": "autre"}, headers=admin), 404, "not_found")


def test_admin_voids_an_open_invoice(client: TestClient, db: Engine, make_practice: Factory, make_user: Factory,
                                     auth_headers: Factory) -> None:
    admin = auth_headers(make_user(role="admin"))
    p = make_practice()
    inv = _invoice(db, p)
    paid = _invoice(db, p, "DAF-2026-0002", status="paid", paid_at=T0)
    assert client.post(f"/api/admin/invoices/{inv.id}/void", headers=admin).json()["status"] == "void"
    assert_problem(client.post(f"/api/admin/invoices/{inv.id}/void", headers=admin), 409, "invoice_not_open")
    assert_problem(client.post(f"/api/admin/invoices/{paid.id}/void", headers=admin), 409, "invoice_not_open")


@pytest.mark.parametrize("role", ["owner", "dentist", "assistant"])
def test_admin_billing_is_admin_only(client: TestClient, db: Engine, make_practice: Factory, make_user: Factory,
                                     auth_headers: Factory, role: str) -> None:
    p = make_practice(plan_code="cabinet_mensuel")
    inv = _invoice(db, p)
    h = auth_headers(make_user(p, role))
    assert_problem(client.get("/api/admin/billing", headers=h), 403, "forbidden")
    assert_problem(client.post(f"/api/admin/practices/{p.id}/invoices", headers=h), 403, "forbidden")
    assert_problem(client.post(f"/api/admin/invoices/{inv.id}/mark-paid", json={"method": "autre"}, headers=h), 403, "forbidden")
    assert_problem(client.post(f"/api/admin/invoices/{inv.id}/void", headers=h), 403, "forbidden")
