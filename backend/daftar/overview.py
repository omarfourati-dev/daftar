"""Overview of a practice: ``GET /api/dashboard``, ``GET /api/badges`` and ``GET /api/stats?month=`` (owner).

Dashboard (section 5, online requests from 11.3)::

    {today, appointments:{total, byStatus:{<every status>: n}}, upcoming:[Appointment] (today, from now, max 5),
     onlineRequests:[Appointment] (requested, not over yet, max 20), onlineRequestsCount,
     queue:{waiting, called, inTreatment}, cashTodayMillimes, remindersPending (tomorrow), dueTotalMillimes,
     patientsCount, unverifiedCashDays:[{day, differenceMillimes, closedBy}] (owner only, section 16.3; else [])}

``appointments.total`` leaves cancelled appointments out (``byStatus`` still lists them).

Badges (section 15, polled every 60 s – kept cheap): ``{onlineRequests, overdue}``; overdue = today's
``scheduled``/``confirmed`` appointments that ended more than 15 minutes ago (same rule as the day closing).

Statistics (section 15, H1): appointments of the month by status (``total`` counts every status), no-show rate
= no_show / (done + no_show) rounded to 4 decimals (0 without data), revenue = payments of the month,
new patients, top 5 services (by catalog name, cancelled appointments not counted), and the previous month.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import Connection, func, select

from .appointment_view import AppointmentOut, load_appointments
from .clock import TUNIS, now_tunis, today_tunis, tunis_day_bounds
from .deps import Conn, Ctx, OwnerUser, StaffUser
from .finance import UnverifiedDay, due_total, unverified_cash_days
from .reminders import pending_count
from .schemas import ApiModel
from .tables import APPOINTMENT_STATUSES, appointment, patient, payment, queue_entry, service

router = APIRouter(prefix="/api", tags=["overview"])

UPCOMING_LIMIT = 5
REQUESTS_LIMIT = 20
OVERDUE_AFTER = timedelta(minutes=15)
TOP_SERVICES = 5
#: Not shown as "upcoming" on the dashboard (done, gone, or a request that has its own list).
NOT_UPCOMING = ("cancelled", "no_show", "done", "requested")


class AppointmentCounts(ApiModel):
    total: int
    by_status: dict[str, int]


class QueueCounts(ApiModel):
    waiting: int
    called: int
    in_treatment: int


class DashboardOut(ApiModel):
    today: date
    appointments: AppointmentCounts
    upcoming: list[AppointmentOut]
    online_requests: list[AppointmentOut]
    online_requests_count: int
    queue: QueueCounts
    cash_today_millimes: int
    reminders_pending: int
    due_total_millimes: int
    patients_count: int
    unverified_cash_days: list[UnverifiedDay]


class BadgesOut(ApiModel):
    online_requests: int
    overdue: int


class MonthAppointments(ApiModel):
    total: int
    done: int
    no_show: int
    cancelled: int
    online: int


class TopService(ApiModel):
    name: str
    count: int


class MonthStats(ApiModel):
    month: str
    appointments: MonthAppointments
    no_show_rate: float
    revenue_millimes: int
    new_patients: int
    top_services: list[TopService]


class StatsOut(MonthStats):
    previous: MonthStats


def _open_requests(practice_id: int, now: datetime) -> list[Any]:
    return [appointment.c.practice_id == practice_id, appointment.c.status == "requested", appointment.c.ends_at > now]


def _count(conn: Connection, table: Any, *conditions: Any) -> int:
    return conn.execute(select(func.count()).select_from(table).where(*conditions)).scalar_one()


@router.get("/dashboard")
def dashboard(user: StaffUser, ctx: Ctx, conn: Conn) -> DashboardOut:
    now = ctx.clock.now()
    today = today_tunis(ctx.clock)
    start, end = tunis_day_bounds(today)
    pid = user.pid
    by_status = dict.fromkeys(APPOINTMENT_STATUSES, 0)
    for status, n in conn.execute(
        select(appointment.c.status, func.count())
        .where(appointment.c.practice_id == pid, appointment.c.starts_at >= start, appointment.c.starts_at < end)
        .group_by(appointment.c.status)
    ):
        by_status[status] = n
    upcoming = load_appointments(
        conn, pid, appointment.c.starts_at >= now, appointment.c.starts_at < end,
        appointment.c.status.not_in(NOT_UPCOMING), limit=UPCOMING_LIMIT,
    )
    requests = load_appointments(conn, pid, *_open_requests(pid, now)[1:], limit=REQUESTS_LIMIT)
    queue = dict(
        conn.execute(
            select(queue_entry.c.status, func.count())
            .where(queue_entry.c.practice_id == pid, queue_entry.c.day == today)
            .group_by(queue_entry.c.status)
        ).all()
    )
    cash_today = conn.execute(
        select(func.coalesce(func.sum(payment.c.amount_millimes), 0)).where(
            payment.c.practice_id == pid, payment.c.paid_at >= start, payment.c.paid_at < end
        )
    ).scalar_one()
    return DashboardOut(
        today=today,
        appointments=AppointmentCounts(
            total=sum(n for s, n in by_status.items() if s != "cancelled"), by_status=by_status
        ),
        upcoming=upcoming,
        online_requests=requests,
        online_requests_count=_count(conn, appointment, *_open_requests(pid, now)),
        queue=QueueCounts(
            waiting=queue.get("waiting", 0), called=queue.get("called", 0), in_treatment=queue.get("in_treatment", 0)
        ),
        cash_today_millimes=int(cash_today),
        reminders_pending=pending_count(conn, pid, today + timedelta(days=1)),
        due_total_millimes=due_total(conn, pid),
        patients_count=_count(conn, patient, patient.c.practice_id == pid),
        unverified_cash_days=unverified_cash_days(conn, pid) if user.is_owner else [],
    )


@router.get("/badges")
def badges(user: StaffUser, ctx: Ctx, conn: Conn) -> BadgesOut:
    now = ctx.clock.now()
    start, _ = tunis_day_bounds(today_tunis(ctx.clock))
    overdue = _count(
        conn,
        appointment,
        appointment.c.practice_id == user.pid,
        appointment.c.starts_at >= start,
        appointment.c.status.in_(("scheduled", "confirmed")),
        appointment.c.ends_at < now - OVERDUE_AFTER,
    )
    return BadgesOut(online_requests=_count(conn, appointment, *_open_requests(user.pid, now)), overdue=overdue)


# --- statistics ------------------------------------------------------------------------------------------------

def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    nxt = (year + 1, 1) if month == 12 else (year, month + 1)
    return datetime(year, month, 1, tzinfo=TUNIS), datetime(*nxt, 1, tzinfo=TUNIS)


def _previous(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def month_stats(conn: Connection, practice_id: int, year: int, month: int) -> MonthStats:
    start, end = _month_bounds(year, month)
    in_month = (appointment.c.practice_id == practice_id, appointment.c.starts_at >= start, appointment.c.starts_at < end)
    counts = dict(
        conn.execute(select(appointment.c.status, func.count()).where(*in_month).group_by(appointment.c.status)).all()
    )
    online = _count(conn, appointment, *in_month, appointment.c.source == "online")
    done, no_show = counts.get("done", 0), counts.get("no_show", 0)
    revenue = conn.execute(
        select(func.coalesce(func.sum(payment.c.amount_millimes), 0)).where(
            payment.c.practice_id == practice_id, payment.c.paid_at >= start, payment.c.paid_at < end
        )
    ).scalar_one()
    new_patients = _count(
        conn, patient, patient.c.practice_id == practice_id, patient.c.created_at >= start, patient.c.created_at < end
    )
    n = func.count().label("n")
    top = conn.execute(
        select(service.c.name_fr, n)
        .select_from(appointment.join(service, service.c.id == appointment.c.service_id))
        .where(*in_month, appointment.c.status != "cancelled")
        .group_by(service.c.name_fr)
        .order_by(n.desc(), service.c.name_fr)
        .limit(TOP_SERVICES)
    ).all()
    return MonthStats(
        month=f"{year:04d}-{month:02d}",
        appointments=MonthAppointments(
            total=sum(counts.values()), done=done, no_show=no_show, cancelled=counts.get("cancelled", 0), online=online
        ),
        no_show_rate=round(no_show / (done + no_show), 4) if done + no_show else 0.0,
        revenue_millimes=int(revenue),
        new_patients=new_patients,
        top_services=[TopService(name=name, count=count) for name, count in top],
    )


@router.get("/stats")
def stats(
    user: OwnerUser,
    ctx: Ctx,
    conn: Conn,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
) -> StatsOut:
    if month is None:
        local = now_tunis(ctx.clock)
        year, mon = local.year, local.month
    else:
        year, mon = int(month[:4]), int(month[5:])
    current = month_stats(conn, user.pid, year, mon)
    previous = month_stats(conn, user.pid, *_previous(year, mon))
    return StatsOut(**current.model_dump(by_alias=False), previous=previous)
