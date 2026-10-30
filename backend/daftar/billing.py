"""Subscriptions of the practices (section 11.4): plans, invoices, the daily job, Flouci, admin bookkeeping.

Rules
- Invoice numbers ``DAF-<year>-<n>`` (n ≥ 4 digits) count up per calendar year without gaps or duplicates: a
  transaction-scoped advisory lock serialises everybody who creates an invoice (two parallel creations wait for
  each other instead of both taking the same number).
- Job ``billing`` (hourly, idempotent): an ``active`` practice on a paid plan gets the invoice of its next period
  10 days before ``paid_until``; after ``paid_until`` it becomes ``past_due``; more than 14 days after it becomes
  ``suspended`` (writing blocked with 402, reading/export/billing still work). Pilot and trial practices, free
  plans and demos are left alone.
- Paid (Flouci or by hand) → ``active`` and ``paid_until`` = end of the invoice period (never shortened).
- Flouci is only asked, never believed blindly: a payment counts when Verify Payment says ``SUCCESS`` with the
  invoice's amount (and its number as tracking id). The webhook body is never trusted.

Owner: ``GET /api/billing`` · ``POST /api/billing/invoices/{id}/pay`` → ``{paymentUrl}`` ·
``POST /api/billing/invoices/{id}/verify`` → ``{invoice, providerStatus}`` (all allowed while suspended – paying is
how a practice gets unblocked). Public: ``POST /api/public/flouci/webhook``. Admin: ``GET /api/admin/billing``,
``POST /api/admin/practices/{id}/invoices``, ``POST /api/admin/invoices/{id}/mark-paid {method}``,
``POST /api/admin/invoices/{id}/void``.
"""

from __future__ import annotations

import calendar
import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import Connection, Integer, cast, func, insert, select, update

from .clock import TUNIS
from .context import AppContext
from .deps import AdminUser, ClientIp, Conn, Ctx, OwnerUser
from .hosts import normalize_host
from .payment_provider import Provider, ProviderError, VerifiedPayment
from .problems import ApiError, bad_request, conflict, not_found, unprocessable
from .schemas import ApiModel, TunisDateTime
from .tables import invoice, plan, practice

log = logging.getLogger("daftar")

router = APIRouter(prefix="/api/billing", tags=["billing"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])
public_router = APIRouter(prefix="/api/public/flouci", tags=["public"])

#: Key of the advisory lock that serialises invoice numbering ("DAFT").
INVOICE_LOCK = 0x44414654
INVOICE_AHEAD = timedelta(days=10)
GRACE = timedelta(days=14)
WEBHOOK_PER_IP = 60
WEBHOOK_MAX_BYTES = 10_000
_HOST = re.compile(r"^[a-z0-9.-]+(?::\d{1,5})?$")

InvoiceMethod = Literal["flouci", "virement", "especes", "autre"]


# --- models ----------------------------------------------------------------------------------------------------

class PlanOut(ApiModel):
    code: str
    name_fr: str
    name_ar: str
    price_millimes: int
    period_months: int


class InvoiceOut(ApiModel):
    id: int
    number: str
    plan_code: str
    period_start: date
    period_end: date
    amount_millimes: int
    status: str
    due_on: date
    paid_at: TunisDateTime | None
    method: str | None
    created_at: TunisDateTime


class BillingOut(ApiModel):
    plan: PlanOut
    status: str
    paid_until: date | None
    plans: list[PlanOut]
    invoices: list[InvoiceOut]
    online_payment_available: bool


class PaymentLinkOut(ApiModel):
    payment_url: str


class VerifyOut(ApiModel):
    invoice: InvoiceOut
    provider_status: str


class MarkPaidIn(ApiModel):
    method: InvoiceMethod


class AdminBillingRow(ApiModel):
    practice_id: int
    name: str
    slug: str
    plan_code: str
    status: str
    paid_until: date | None
    open_invoices: int
    open_millimes: int


# --- invoices --------------------------------------------------------------------------------------------------

def add_months(day: date, months: int) -> date:
    """Same day ``months`` later, clamped to the end of the month (31.01. + 1 → 28.02.)."""
    years, index = divmod(day.month - 1 + months, 12)
    year, month = day.year + years, index + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def next_invoice_number(conn: Connection, year: int) -> str:
    """The next free number of ``year`` – call it only while holding the invoice lock (:func:`create_invoice`)."""
    prefix = f"DAF-{year}-"
    highest = conn.execute(
        select(func.max(cast(func.split_part(invoice.c.number, "-", 3), Integer))).where(
            invoice.c.number.startswith(prefix)
        )
    ).scalar()
    return f"{prefix}{(highest or 0) + 1:04d}"


def create_invoice(conn: Connection, practice_id: int, now: datetime, *, period_start: date) -> Any:
    """Invoice of the practice's current plan for the period starting ``period_start`` (race-free number)."""
    conn.execute(select(func.pg_advisory_xact_lock(INVOICE_LOCK)))
    p = conn.execute(
        select(practice.c.plan_code, plan.c.price_millimes, plan.c.period_months)
        .select_from(practice.join(plan, plan.c.code == practice.c.plan_code))
        .where(practice.c.id == practice_id)
    ).one()
    today = now.astimezone(TUNIS).date()
    return conn.execute(
        insert(invoice)
        .values(
            practice_id=practice_id,
            number=next_invoice_number(conn, today.year),
            plan_code=p.plan_code,
            period_start=period_start,
            period_end=add_months(period_start, p.period_months) - timedelta(days=1),
            amount_millimes=p.price_millimes,
            status="open",
            due_on=max(period_start, today),
            created_at=now,
        )
        .returning(invoice)
    ).one()


def _invoice_exists(conn: Connection, practice_id: int, period_start: date) -> bool:
    return conn.execute(
        select(invoice.c.id).where(
            invoice.c.practice_id == practice_id, invoice.c.period_start == period_start, invoice.c.status != "void"
        )
    ).first() is not None


def settle(conn: Connection, inv: Any, method: str, now: datetime) -> Any:
    """Marks an open invoice as paid and reactivates the practice until the end of the invoice period."""
    row = conn.execute(
        update(invoice).where(invoice.c.id == inv.id).values(status="paid", paid_at=now, method=method).returning(invoice)
    ).one()
    conn.execute(
        update(practice)
        .where(practice.c.id == inv.practice_id)
        .values(status="active", paid_until=func.greatest(func.coalesce(practice.c.paid_until, inv.period_end), inv.period_end))
    )
    return row


def _paid_plans() -> Any:
    return select(plan.c.code).where(plan.c.price_millimes > 0)


def run_billing(conn: Connection, now: datetime) -> dict[str, int]:
    """The daily rules (idempotent): next invoices, ``past_due`` after ``paid_until``, ``suspended`` 14 days later."""
    today = now.astimezone(TUNIS).date()
    due = conn.execute(
        select(practice.c.id, practice.c.paid_until)
        .where(
            practice.c.status == "active",
            practice.c.is_demo.is_(False),
            practice.c.paid_until.is_not(None),
            practice.c.paid_until <= today + INVOICE_AHEAD,
            practice.c.plan_code.in_(_paid_plans()),
        )
        .order_by(practice.c.id)
    ).all()
    created = 0
    for p in due:
        start = p.paid_until + timedelta(days=1)
        if not _invoice_exists(conn, p.id, start):
            create_invoice(conn, p.id, now, period_start=start)
            created += 1
    billed = (practice.c.is_demo.is_(False), practice.c.plan_code.in_(_paid_plans()))
    late = conn.execute(
        update(practice).where(practice.c.status == "active", practice.c.paid_until < today, *billed).values(status="past_due")
    ).rowcount
    suspended = conn.execute(
        update(practice)
        .where(practice.c.status == "past_due", practice.c.paid_until < today - GRACE, *billed)
        .values(status="suspended")
    ).rowcount
    return {"invoices": created, "past_due": late or 0, "suspended": suspended or 0}


def billing_job(ctx: AppContext) -> None:
    with ctx.engine.begin() as conn:
        result = run_billing(conn, ctx.clock.now())
    if any(result.values()):
        log.info("billing: %s", result)


# --- owner -----------------------------------------------------------------------------------------------------

def _own_invoice(conn: Connection, practice_id: int, invoice_id: int) -> Any:
    row = conn.execute(
        select(invoice).where(invoice.c.id == invoice_id, invoice.c.practice_id == practice_id).with_for_update()
    ).first()
    if row is None:
        raise not_found()
    return row


def _origin(request: Request, base_domain: str) -> str:
    """Where the payer comes back to: the practice's own host (main domain or its sub-domain), else the main domain."""
    raw = (request.headers.get("host") or "").strip().lower()
    name = normalize_host(raw)
    host = raw if _HOST.fullmatch(raw) and (name == base_domain or name.endswith("." + base_domain)) else base_domain
    scheme = "http" if normalize_host(host) == "localhost" or normalize_host(host).endswith(".localhost") else "https"
    return f"{scheme}://{host}"


def _provider_error() -> ApiError:
    return ApiError(502, "Le service de paiement ne répond pas. Réessayez plus tard.", code="payment_provider_error")


@router.get("")
def billing(user: OwnerUser, conn: Conn, provider: Provider) -> BillingOut:
    p = conn.execute(select(practice.c.plan_code, practice.c.status, practice.c.paid_until).where(practice.c.id == user.pid)).one()
    plans = [PlanOut.model_validate(r, from_attributes=True)
             for r in conn.execute(select(plan).where(plan.c.active.is_(True)).order_by(plan.c.price_millimes, plan.c.code))]
    current = conn.execute(select(plan).where(plan.c.code == p.plan_code)).one()
    invoices = conn.execute(
        select(invoice).where(invoice.c.practice_id == user.pid).order_by(invoice.c.period_start.desc(), invoice.c.id.desc())
    )
    return BillingOut(
        plan=PlanOut.model_validate(current, from_attributes=True),
        status=p.status,
        paid_until=p.paid_until,
        plans=plans,
        invoices=[InvoiceOut.model_validate(r, from_attributes=True) for r in invoices],
        online_payment_available=provider is not None,
    )


@router.post("/invoices/{invoice_id}/pay")
def pay(invoice_id: int, request: Request, user: OwnerUser, ctx: Ctx, conn: Conn, provider: Provider) -> PaymentLinkOut:
    inv = _own_invoice(conn, user.pid, invoice_id)
    if inv.status != "open":
        raise conflict("Cette facture n'est plus à payer.", code="invoice_not_open")
    if provider is None:
        raise conflict("Le paiement en ligne n'est pas encore disponible.", code="online_payment_unavailable")
    origin = _origin(request, ctx.settings.base_domain)
    back = f"{origin}/app/abonnement?invoice={inv.id}&result="
    try:
        created = provider.create_payment(
            amount_millimes=inv.amount_millimes,
            tracking_id=inv.number,
            success_url=back + "success",
            fail_url=back + "fail",
            webhook_url=f"https://{ctx.settings.base_domain}/api/public/flouci/webhook",
        )
    except ProviderError as exc:
        raise _provider_error() from exc
    conn.execute(update(invoice).where(invoice.c.id == inv.id).values(provider_payment_id=created.payment_id))
    return PaymentLinkOut(payment_url=created.link)


def _matches(inv: Any, verified: VerifiedPayment) -> bool:
    return verified.amount_millimes == inv.amount_millimes and verified.tracking_id in (None, inv.number)


@router.post("/invoices/{invoice_id}/verify")
def verify(invoice_id: int, user: OwnerUser, ctx: Ctx, conn: Conn, provider: Provider) -> VerifyOut:
    inv = _own_invoice(conn, user.pid, invoice_id)
    if inv.status != "open":
        return VerifyOut(invoice=InvoiceOut.model_validate(inv, from_attributes=True), provider_status=inv.status.upper())
    if provider is None:
        raise conflict("Le paiement en ligne n'est pas encore disponible.", code="online_payment_unavailable")
    if not inv.provider_payment_id:
        raise conflict("Aucun paiement en ligne n'a été lancé pour cette facture.", code="payment_not_started")
    try:
        verified = provider.verify_payment(inv.provider_payment_id)
    except ProviderError as exc:
        raise _provider_error() from exc
    if verified.status == "SUCCESS":
        if not _matches(inv, verified):
            log.warning("billing: Flouci payment of invoice %s does not match (amount/number)", inv.id)
            raise conflict("Le paiement ne correspond pas à la facture.", code="payment_mismatch")
        inv = settle(conn, inv, "flouci", ctx.clock.now())
    return VerifyOut(invoice=InvoiceOut.model_validate(inv, from_attributes=True), provider_status=verified.status)


# --- Flouci webhook --------------------------------------------------------------------------------------------

async def raw_body(request: Request) -> bytes:
    body = await request.body()
    if len(body) > WEBHOOK_MAX_BYTES:
        raise bad_request()
    return body


@public_router.post("/webhook")
def flouci_webhook(
    request: Request,
    ctx: Ctx,
    conn: Conn,
    ip: ClientIp,
    provider: Provider,
    body: Annotated[bytes, Depends(raw_body)],
) -> dict[str, bool]:
    ctx.limiter("flouci-webhook-ip", WEBHOOK_PER_IP, timedelta(minutes=1)).enforce(ip)
    if provider is None:
        raise not_found()
    if not provider.check_signature(request.headers.get("x-flouci-signature"), body, ctx.clock.now()):
        raise bad_request("Signature invalide.", code="invalid_signature")
    try:
        data = json.loads(body)
    except ValueError:
        raise bad_request() from None
    payment_id = data.get("payment_id") if isinstance(data, dict) else None
    if not isinstance(payment_id, str) or not payment_id:
        raise bad_request()
    try:
        verified = provider.verify_payment(payment_id)  # the body says nothing – Flouci itself decides
    except ProviderError as exc:
        raise _provider_error() from exc
    if verified.status != "SUCCESS":
        return {"received": True}
    inv = None
    if verified.tracking_id:
        inv = conn.execute(select(invoice).where(invoice.c.number == verified.tracking_id).with_for_update()).first()
    if inv is None:
        inv = conn.execute(select(invoice).where(invoice.c.provider_payment_id == payment_id).with_for_update()).first()
    if inv is None or inv.status != "open":
        return {"received": True}
    if not _matches(inv, verified):
        log.warning("billing: Flouci webhook for invoice %s does not match (amount/number)", inv.id)
        return {"received": True}
    settle(conn, inv, "flouci", ctx.clock.now())
    return {"received": True}


# --- admin -----------------------------------------------------------------------------------------------------

@admin_router.get("/billing")
def admin_billing(_: AdminUser, conn: Conn) -> list[AdminBillingRow]:
    open_rows = (
        select(
            invoice.c.practice_id,
            func.count().label("n"),
            func.sum(invoice.c.amount_millimes).label("total"),
        )
        .where(invoice.c.status == "open")
        .group_by(invoice.c.practice_id)
        .subquery()
    )
    rows = conn.execute(
        select(
            practice.c.id, practice.c.name, practice.c.slug, practice.c.plan_code, practice.c.status,
            practice.c.paid_until, open_rows.c.n, open_rows.c.total,
        )
        .select_from(practice.outerjoin(open_rows, open_rows.c.practice_id == practice.c.id))
        .where(practice.c.is_demo.is_(False))
        .order_by(practice.c.name, practice.c.id)
    )
    return [
        AdminBillingRow(
            practice_id=r.id, name=r.name, slug=r.slug, plan_code=r.plan_code, status=r.status, paid_until=r.paid_until,
            open_invoices=r.n or 0, open_millimes=int(r.total or 0),
        )
        for r in rows
    ]


@admin_router.post("/practices/{practice_id}/invoices", status_code=201)
def admin_create_invoice(practice_id: int, _: AdminUser, ctx: Ctx, conn: Conn) -> InvoiceOut:
    p = conn.execute(
        select(practice.c.id, practice.c.paid_until, plan.c.price_millimes)
        .select_from(practice.join(plan, plan.c.code == practice.c.plan_code))
        .where(practice.c.id == practice_id, practice.c.is_demo.is_(False))
        .with_for_update(of=practice)
    ).first()
    if p is None:
        raise not_found()
    if p.price_millimes <= 0:
        raise unprocessable("Le plan de ce cabinet est gratuit.", code="plan_is_free")
    now = ctx.clock.now()
    start = p.paid_until + timedelta(days=1) if p.paid_until else now.astimezone(TUNIS).date()
    if _invoice_exists(conn, p.id, start):
        raise conflict("Une facture existe déjà pour cette période.", code="invoice_exists")
    return InvoiceOut.model_validate(create_invoice(conn, p.id, now, period_start=start), from_attributes=True)


def _open_invoice(conn: Connection, invoice_id: int) -> Any:
    row = conn.execute(select(invoice).where(invoice.c.id == invoice_id).with_for_update()).first()
    if row is None:
        raise not_found()
    if row.status != "open":
        raise conflict("Cette facture n'est plus ouverte.", code="invoice_not_open")
    return row


@admin_router.post("/invoices/{invoice_id}/mark-paid")
def admin_mark_paid(invoice_id: int, body: MarkPaidIn, _: AdminUser, ctx: Ctx, conn: Conn) -> InvoiceOut:
    inv = _open_invoice(conn, invoice_id)
    return InvoiceOut.model_validate(settle(conn, inv, body.method, ctx.clock.now()), from_attributes=True)


@admin_router.post("/invoices/{invoice_id}/void")
def admin_void(invoice_id: int, _: AdminUser, conn: Conn) -> InvoiceOut:
    inv = _open_invoice(conn, invoice_id)
    row = conn.execute(update(invoice).where(invoice.c.id == inv.id).values(status="void").returning(invoice)).one()
    return InvoiceOut.model_validate(row, from_attributes=True)
