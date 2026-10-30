"""Mutation check for practice, team, admin, appointments, queue and online booking (runner: tests/mutation_check.py).

Run from backend/:  .venv/Scripts/python -m tests.termine.mutation_check   (about 15 minutes; not part of pytest)
"""

from __future__ import annotations

from tests import mutation_check as runner

T = "tests/termine/"
MUTATIONS: list[tuple[str, str, str, str]] = [
    # practice settings, practitioners, services, closures, onboarding
    ("daftar/practice_settings.py", '    if "weekly_hours" in values:\n        values["onboarding"] = flag("hours")\n', "", T + "test_onboarding.py"),
    ("daftar/practice_settings.py", "if getattr(self, name) is None and name not in self.nullable_fields:", "if False:", T + "test_practice_settings.py"),
    ("daftar/practice_settings.py", r'pattern=r"^(?:https://\S+)?$"', 'pattern=r"^.*$"', T + "test_practice_settings.py"),
    ("daftar/practitioners.py", "    if used:", "    if False:", T + "test_practitioners_services.py"),
    ("daftar/practitioners.py", "app_user.c.id == user_id, app_user.c.practice_id == practice_id", "app_user.c.id == user_id", T + "test_practitioners_services.py"),
    ("daftar/closures.py", "if ends_on < starts_on or ends_on - starts_on > MAX_SPAN:", "if ends_on < starts_on:", T + "test_closures.py"),
    ("daftar/onboarding.py", "    if key not in MANUAL:", "    if False:", T + "test_onboarding.py"),
    ("daftar/onboarding.py", "service.c.active, service.c.price_millimes.is_not(None)", "service.c.active", T + "test_onboarding.py"),
    # team and password reset
    ("daftar/staff.py", "    if member.id == user.user_id:", "    if False:", T + "test_staff.py"),
    ("daftar/staff.py", '    if member.role == "owner":', "    if False:", T + "test_staff.py"),
    ("daftar/staff.py", "            invitation.c.role.in_(STAFF_ROLES),\n            invitation.c.used_at", "            invitation.c.used_at", T + "test_staff.py"),
    ("daftar/password_reset.py", "    conn.execute(delete(password_reset).where(password_reset.c.user_id == user_id, password_reset.c.used_at.is_(None)))\n", "", T + "test_staff.py"),
    ("daftar/password_reset.py", "password_hash=hash_password(body.password), token_version=app_user.c.token_version + 1", "password_hash=hash_password(body.password)", T + "test_staff.py"),
    ("daftar/password_reset.py", "            password_reset.c.expires_at > now,", "            True,", T + "test_staff.py"),
    # admin customer master
    ("daftar/admin_practices.py", 'if problem == "reserved" or slug.startswith(DEMO_PREFIX):', 'if problem == "reserved":', T + "test_admin_practices.py"),
    ("daftar/admin_practices.py", "        query = query.where(practice.c.is_demo.is_(False))", "        pass", T + "test_admin_practices.py"),
    ("daftar/admin_practices.py", '        if constraint_name(exc) == "practice_slug_key":', "        if False:", T + "test_admin_practices.py"),
    # scheduling and appointments
    ("daftar/scheduling.py", "PAST_GRACE = timedelta(minutes=15)", "PAST_GRACE = timedelta(minutes=16)", T + "test_appointments.py"),
    ("daftar/scheduling.py", "            if t >= until or len(found) == SUGGESTION_COUNT:", "            if len(found) == SUGGESTION_COUNT:", T + "test_appointments.py"),
    ("daftar/scheduling.py", "    starts = [t for t in grid(cal, day, duration_min) if t >= not_before]", "    starts = grid(cal, day, duration_min)", T + "test_availability.py"),
    ("daftar/scheduling.py", "        if patient_id is not None and any(b.patient_id == patient_id for b in overlapping):", "        if False:", T + "test_appointments.py"),
    ("daftar/scheduling.py", "func.coalesce(appointment.c.practitioner_id, 0) == (practitioner_id or 0)", "appointment.c.practitioner_id == practitioner_id", T + "test_appointments.py"),
    ("daftar/scheduling.py", "        if constraint_name(exc) not in OVERLAP_CONSTRAINTS:\n            raise\n        # the other", "        raise\n        # the other", T + "test_appointments.py"),
    ("daftar/scheduling.py", "    if not fits_opening_hours(cal.weekly_hours, starts_at, ends_at):", "    if False:", T + "test_appointments.py"),
    ("daftar/appointments.py", '    "done": frozenset({"in_treatment"}),', '    "done": frozenset({"in_treatment", "cancelled"}),', T + "test_appointment_status.py"),
    ("daftar/appointments.py", '    if target == "no_show" and current.starts_at > now:', "    if False:", T + "test_appointment_status.py"),
    ("daftar/appointments.py", '(target in ("arrived", "in_treatment") and day != today)', "False", T + "test_appointment_status.py"),
    ("daftar/appointments.py", "    if moving and current.status not in OPEN:", "    if False:", T + "test_appointments.py"),
    ("daftar/appointments.py", "        appointment.c.ends_at < now - OVERDUE_AFTER,", "        appointment.c.ends_at < now,", T + "test_appointments.py"),
    ("daftar/appointments.py", "    if (last - first).days >= MAX_RANGE_DAYS:", "    if (last - first).days > MAX_RANGE_DAYS:", T + "test_appointments.py"),
    ("daftar/appointments.py", "        .where(payment.c.appointment_id == appointment.c.id, payment.c.is_deposit)", "        .where(payment.c.appointment_id == appointment.c.id)", T + "test_appointments.py"),
    ("daftar/appointments.py", "            _arrive(conn, practice_id, appt, now, today)", "            pass", T + "test_appointment_status.py"),
    ("daftar/series.py", "    if conflicts and not body.skip_conflicts:", "    if False:", T + "test_series.py"),
    ("daftar/series.py", "            appointment.c.status.in_(OPEN),", "            True,", T + "test_series.py"),
    # waiting room
    ("daftar/queue.py", "            ahead = position - 1 + called", "            ahead = position - 1", T + "test_queue.py"),
    ("daftar/queue.py", "        if active is not None:", "        if False:", T + "test_queue.py"),
    ("daftar/queue.py", "    lock_queue(conn, practice_id)\n    number", "    number", T + "test_queue.py"),
    ("daftar/queue.py", "        .limit(3)", "        .limit(4)", T + "test_queue.py"),
    ("daftar/queue.py", "                appointment.c.status.in_(MIRRORED_APPOINTMENT_STATUSES),", "                True,", T + "test_queue.py"),
    ("daftar/queue.py", '    ctx.limiter("public-queue", PUBLIC_LIMIT, PUBLIC_WINDOW).enforce(ip)', "    pass", T + "test_queue.py"),
    # online booking
    ("daftar/booking.py", "func.lower(func.btrim(patient.c.last_name)) == body.last_name.strip().lower()", "patient.c.last_name == body.last_name", T + "test_booking.py"),
    ("daftar/booking.py", "    if row is None or row.status in CLOSED_STATUSES:", "    if row is None:", T + "test_booking.py"),
    ("daftar/booking.py", '    _limit(ctx, "booking-ip", BOOKING_LIMIT, BOOKING_WINDOW, ip)', "    pass", T + "test_booking.py"),
    ("daftar/booking.py", "can_cancel=current in OPEN and now <= cancel_until", "can_cancel=True", T + "test_booking.py"),
    ("daftar/booking.py", "    if day < local_day(now) or day > last_day or not resources:", "    if not resources:", T + "test_booking.py"),
    ("daftar/booking.py", '        raise _slot_taken() from exc', "        raise", T + "test_booking.py"),
    ("daftar/booking.py", "    if body.website:  # a bot", "    if False:  # a bot", T + "test_booking.py"),
    ("daftar/booking.py", "        if no_shows >= row.booking_block_no_shows:", "        if no_shows > row.booking_block_no_shows:", T + "test_booking.py"),
    # 16.1 next free times, 16.2 patient suivant
    ("daftar/availability.py", "    for offset in range(NEXT_DAYS + 1):", "    for offset in range(NEXT_DAYS):", T + "test_availability_next.py"),
    ("daftar/availability.py", "practitioner_id=free[0]", "practitioner_id=free[-1]", T + "test_availability_next.py"),
    ("daftar/availability.py", "                                   patient_id=patient_id, closed=closed):", "                                   closed=closed):", T + "test_availability_next.py"),
    ("daftar/queue.py", "        appointment.c.starts_at <= now + DUE_BEFORE,", "        appointment.c.starts_at <= now + DUE_BEFORE + timedelta(minutes=1),", T + "test_queue_next.py"),
    ("daftar/queue.py", "            mine = w.appointment_id == appt.id or (w.appointment_id is None and w.patient_id == appt.patient_id)", "            mine = w.appointment_id == appt.id", T + "test_queue_next.py"),
    ("daftar/queue.py", "        waiting = [w for w in waiting if w.appointment_id is None or w.doctor in (None, practitioner_id)]", "        pass", T + "test_queue_next.py"),
    ("daftar/queue.py", "    for appt in conn.execute(due.order_by(appointment.c.starts_at, appointment.c.id)).all():", "    for appt in conn.execute(due.order_by(appointment.c.id)).all():", T + "test_queue_next.py"),
    ("daftar/queue_next.py", "    queue.lock_queue(conn, user.pid)  # held", "    pass  # held", T + "test_queue_next.py"),
    ("daftar/queue_next.py", "        appointment.c.starts_at <= now - LATE_AFTER,", "        appointment.c.starts_at <= now,", T + "test_queue_next.py"),
    ("daftar/queue_next.py", "        ~present,\n", "", T + "test_queue_next.py"),
]

if __name__ == "__main__":
    runner.MUTATIONS[:] = MUTATIONS
    raise SystemExit(runner.main())
