"""Startup tasks: the admin account from ADMIN_EMAIL / ADMIN_PASSWORD.

- no account with ADMIN_EMAIL → create the admin (role ``admin``, no practice);
- the account exists → keep its password (a password changed in the app wins) unless ADMIN_RESET_PASSWORD=true;
- the e-mail belongs to a practice account → leave it alone and warn.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, insert, select, update

from .context import AppContext
from .passwords import hash_password, length_problem, password_problem, verify_password
from .settings import SettingsError
from .tables import app_user

log = logging.getLogger("daftar")


def bootstrap_admin(ctx: AppContext) -> None:
    s = ctx.settings
    with ctx.engine.begin() as conn:
        if not (s.admin_email and s.admin_password):
            admins = conn.execute(select(func.count()).select_from(app_user).where(app_user.c.role == "admin")).scalar_one()
            if admins == 0:
                log.warning("no admin account – set ADMIN_EMAIL and ADMIN_PASSWORD to create one")
            return
        if problem := length_problem(s.admin_password):
            raise SettingsError(f"ADMIN_PASSWORD: {problem[1]}")
        if password_problem(s.admin_password, s.admin_email):  # the stricter rules of the app: warn, keep starting
            log.warning("ADMIN_PASSWORD is easy to guess (a run, one repeated character or the e-mail) – change it")
        row = conn.execute(
            select(app_user.c.id, app_user.c.role, app_user.c.password_hash).where(app_user.c.email == s.admin_email)
        ).first()
        if row is None:
            conn.execute(
                insert(app_user).values(
                    email=s.admin_email,
                    password_hash=hash_password(s.admin_password),
                    role="admin",
                    practice_id=None,
                    name="Admin",
                    lang="fr",
                    created_at=ctx.clock.now(),
                )
            )
            log.info("admin account created")
        elif row.role != "admin":
            log.warning("ADMIN_EMAIL belongs to a practice account – left unchanged")
        elif s.admin_reset_password and not verify_password(s.admin_password, row.password_hash):
            conn.execute(
                update(app_user)
                .where(app_user.c.id == row.id)
                .values(password_hash=hash_password(s.admin_password), token_version=app_user.c.token_version + 1)
            )
            log.info("admin password reset from ADMIN_PASSWORD")
