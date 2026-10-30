"""Proves the tests catch real breaks: applies one deliberate bug at a time, expects pytest to fail, restores.

Run from backend/:  .venv/Scripts/python -m tests.mutation_check   (takes a few minutes; not part of pytest)
Each mutation is (file, original snippet, broken snippet, test selection). A mutation that leaves the tests green
is reported as SURVIVED and the script exits with 1.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

MUTATIONS: list[tuple[str, str, str, str]] = [
    ("daftar/phone.py", "if len(text) == 8:", "if len(text) == 9:", "tests/test_phone.py"),
    ("daftar/phone.py", "len(digits) != len(TUNISIA) + 8", "len(digits) != len(TUNISIA) + 9", "tests/test_phone.py"),
    ("daftar/money.py", '{grouped},{rest:03d} DT"', '{grouped},{rest} DT"', "tests/test_money.py"),
    ("daftar/money.py", "Field(gt=0, le=MAX_MILLIMES, strict=True)", "Field(ge=0, le=MAX_MILLIMES)", "tests/test_money.py"),
    ("daftar/clock.py", "return now_tunis(clock).date()", "return clock.now().date()", "tests/test_clock.py"),
    ("daftar/settings.py", "jwt_secret='***'", "jwt_secret={self.jwt_secret!r}", "tests/test_settings.py"),
    ("daftar/settings.py", "if len(self.jwt_secret) < MIN_JWT_SECRET:", "if False:", "tests/test_settings.py"),
    ("daftar/throttle.py", "PER_EMAIL_IP = 5", "PER_EMAIL_IP = 6", "tests/test_throttle.py tests/test_auth.py"),
    ("daftar/throttle.py", 'self._b.hits.pop(f"p:{email}|{ip}", None)', "pass", "tests/test_throttle.py"),
    ("daftar/throttle.py", "while q and q[0] + self.window <= now:", "while False:", "tests/test_throttle.py"),
    ("daftar/tokens.py", 'if int(payload["exp"]) <= self._clock.now().timestamp():', "if False:", "tests/test_tokens_passwords.py tests/test_auth.py"),
    ("daftar/passwords.py", "MIN_LENGTH = 10", "MIN_LENGTH = 8", "tests/test_tokens_passwords.py tests/test_auth.py"),
    ("daftar/deps.py", "row.token_version != claims.token_version", "False", "tests/test_auth.py"),
    ("daftar/deps.py", 'last = forwarded.split(",")[-1].strip()', 'last = forwarded.split(",")[0].strip()', "tests/test_auth.py"),
    ("daftar/deps.py", "row.demo_expires_at <= ctx.clock.now()", "False", "tests/test_auth.py"),
    ("daftar/deps.py", "if user.role not in allowed:", "if False:", "tests/test_guards.py"),
    ("daftar/deps.py", "if self.practice_id is None:\n            raise forbidden()", "if False:\n            raise forbidden()", "tests/test_guards.py"),
    ("daftar/auth.py", 'password_hash=hash_password(body.next), token_version=app_user.c.token_version + 1', "password_hash=hash_password(body.next)", "tests/test_auth.py"),
    ("daftar/auth.py", "email = body.email.strip().lower()", "email = body.email", "tests/test_auth.py"),
    ("daftar/auth.py", 'ctx.metrics.logins.labels("failed").inc()', "pass", "tests/test_auth.py"),
    ("daftar/auth.py", "values = body.model_dump(exclude_none=True, by_alias=False)", "values = {}", "tests/test_auth.py"),
    ("daftar/invitations.py", 'return hashlib.sha256(token.encode("utf-8")).hexdigest()', 'return hashlib.sha256(token.encode("utf-8")).hexdigest()[::-1]', "tests/test_invitations.py"),
    ("daftar/invitations.py", "conn.execute(update(invitation).where(invitation.c.id == row.id).values(used_at=now))", "pass", "tests/test_invitations.py"),
    ("daftar/invitations.py", "role=row.role,", 'role="dentist",', "tests/test_invitations.py"),
    ("daftar/invitations.py", "invitation.c.expires_at > now,", "True,", "tests/test_invitations.py"),
    ("daftar/invitations.py", 'ctx.login_throttle.clear_key(f"invitation:{ip}")\n    return PreviewOut', "return PreviewOut", "tests/test_invitations.py"),
    ("daftar/invitations.py", "invitation.c.expires_at < now - KEEP_EXPIRED", "invitation.c.expires_at < now", "tests/test_invitations.py"),
    ("daftar/static.py", "        or \"\\\\\" in path\n", "", "tests/test_static.py"),
    ("daftar/static.py", "def is_unsafe(path: str) -> bool:\n    return (", "def is_unsafe(path: str) -> bool:\n    return False and (", "tests/test_static.py"),
    ("daftar/static.py", 'cache = IMMUTABLE', 'cache = NO_CACHE', "tests/test_static.py"),
    ("daftar/static.py", "        if is_spa_route(path):\n            return RedirectResponse(app_origin", "        if False:\n            return RedirectResponse(app_origin", "tests/test_hosts.py"),
    ("daftar/static.py", '        if path == "/" + SPA_SHELL:', "        if False:", "tests/test_hosts.py"),
    ("daftar/static.py", 'SPA_PREFIXES = ("/app", "/connexion", "/invitation", "/reinitialiser")', 'SPA_PREFIXES = ("/app", "/connexion", "/invitation")', "tests/test_hosts.py"),
    ("daftar/static.py", 'if request.headers.get("if-none-match") == file.etag:', "if False:", "tests/test_static.py"),
    ("daftar/static.py", "return RedirectResponse(path + \"/\"", "return RedirectResponse(path + \"\"", "tests/test_static.py"),
    ("daftar/http.py", '"Referrer-Policy": "strict-origin-when-cross-origin",', "", "tests/test_http.py"),
    ("daftar/http.py", "script_src = \" \".join([\"'self'\", *(f\"'sha256-{h}'\" for h in script_hashes)])", "script_src = \"'self'\"", "tests/test_http.py"),
    ("daftar/http.py", "            response = problem_response(500", "            raise\n            response = problem_response(500", "tests/test_http.py"),
    ("daftar/http.py", "if self.log_requests and path not in QUIET_PATHS:", "if self.log_requests:", "tests/test_http.py"),
    ("daftar/app.py", "            if match is Match.PARTIAL:", "            if False:", "tests/test_http.py"),
    ("daftar/app.py", "            ping(engine)", "            pass", "tests/test_http.py"),
    ("daftar/metrics.py", 'practices.add_metric(["demo"], kinds.get(True, 0))', 'practices.add_metric(["demo"], kinds.get(False, 0))', "tests/test_http.py"),
    ("daftar/metrics.py", '.where(app_user.c.role != "admin")', "", "tests/test_http.py"),
    ("daftar/problems.py", '{"field": _field(tuple(e.get("loc", ()))), "type": e.get("type"), "message": e.get("msg")}', '{"field": _field(tuple(e.get("loc", ()))), "type": e.get("type"), "message": e.get("msg"), "input": str(e.get("input"))}', "tests/test_http.py tests/test_auth.py"),
    ("daftar/bootstrap.py", "elif s.admin_reset_password and not verify_password(s.admin_password, row.password_hash):", "elif not verify_password(s.admin_password, row.password_hash):", "tests/test_bootstrap.py"),
    ("daftar/bootstrap.py", 'elif row.role != "admin":', "elif False:", "tests/test_bootstrap.py"),
    ("daftar/tables.py", 'Column("tooth", Text, nullable=True)', 'Column("tooth", Text, nullable=False)', "tests/test_schema.py"),
    ("migrations/versions/0001_initial.py", "CONSTRAINT appointment_patient_fkey FOREIGN KEY (patient_id, practice_id)\n        REFERENCES patient (id, practice_id) ON DELETE CASCADE", "CONSTRAINT appointment_patient_fkey FOREIGN KEY (patient_id)\n        REFERENCES patient (id) ON DELETE CASCADE", "tests/test_schema.py"),
    ("migrations/versions/0001_initial.py", "FREE = \"status NOT IN ('cancelled', 'no_show')\"", "FREE = \"status NOT IN ('cancelled')\"", "tests/test_schema.py"),
    ("migrations/versions/0001_initial.py", "practice_id WITH =, (coalesce(practitioner_id, 0)) WITH =,", "practice_id WITH =, practitioner_id WITH =,", "tests/test_schema.py"),
    ("migrations/versions/0001_initial.py", "practice_id WITH =, patient_id WITH =, tstzrange", "practice_id WITH =, id WITH =, tstzrange", "tests/test_schema.py"),
    ("migrations/versions/0001_initial.py", "[a-z0-9-]{{1,38}}", "[a-z0-9-]{{0,38}}", "tests/test_schema.py"),
    ("migrations/versions/0001_initial.py", "\"'www', 'app',", "\"'app',", "tests/test_schema.py"),
    ("migrations/versions/0001_initial.py", "'العيادة – شهري', 49000, 1)", "'العيادة – شهري', 4900, 1)", "tests/test_schema.py"),
    ("migrations/versions/0001_initial.py", "CONSTRAINT appointment_duration_check CHECK (ends_at = starts_at + duration_min * interval '1 minute'),", "", "tests/test_schema.py"),
    ("daftar/hosts.py", "if not is_practice_host or found is None or found.is_demo or", "if not is_practice_host or found is None or", "tests/test_hosts.py"),
    ("daftar/hosts.py", 'return host.split(":", 1)[0].rstrip(".")', 'return host.split(":", 1)[0]', "tests/test_hosts.py"),
    ("daftar/static.py", 'spa = path == "/" or (path.startswith("/rdv/")', 'spa = path == "/" or (path.startswith("/rdvx/")', "tests/test_hosts.py"),
    ("daftar/static.py", "status_code=302)", "status_code=301)", "tests/test_hosts.py"),
    ("daftar/branding.py", "return (words[0][0] + words[-1][0]).upper()", "return (words[0][0] + words[1][0]).upper()", "tests/test_hosts.py"),
    ("daftar/branding.py", "draw.rectangle((0, 0, size, size), fill=(*color, 255))", "draw.rectangle((0, 0, size, size), fill=(0, 0, 0, 255))", "tests/test_hosts.py"),
    ("daftar/app.py", "        if host_practice is None:\n            return site.not_found(request)", "        if host_practice is None:\n            return site.respond(request, \"https://x\")", "tests/test_hosts.py"),
    ("daftar/app.py", "        if is_app_host(host, base):\n", "        if False:\n", "tests/test_hosts.py"),
    ("daftar/auth.py", "ok = host_practice is not None and row is not None and row.practice_id == host_practice.id", "ok = True", "tests/test_hosts.py"),
    ("daftar/auth.py", "    if ok and label != APP_LABEL:", "    if ok and label is not None and label != APP_LABEL:", "tests/test_hosts.py"),
    ("daftar/hosts.py", "    if is_app_host(domain, ctx.settings.base_domain):\n        return Response(status_code=200)\n", "", "tests/test_hosts.py"),
    ("daftar/hosts.py", 'return f"http://{name}" + (f":{port}" if port.isdigit() else "")', 'return f"http://{name}"', "tests/test_hosts.py"),
    ("daftar/http.py", "                if https:\n", "                if True:\n", "tests/test_http.py"),
    ("daftar/http.py", 'HSTS = "max-age=31536000"', 'HSTS = "max-age=31536000; includeSubDomains"', "tests/test_http.py"),
    ("daftar/deps.py", 'if user.practice_status == "suspended":', 'if user.practice_status == "canceled":', "tests/test_guards.py"),
    ("daftar/catalog.py", "for n, item in enumerate(items, start=1)", "for n, item in enumerate(items)", "tests/test_practice_data.py"),
    ("daftar/hours.py", "            if after[0] < before[1]:", "            if False:", "tests/test_practice_data.py"),
    ("daftar/slugs.py", "    if slug in RESERVED_SLUGS:", "    if False:", "tests/test_practice_data.py"),
    ("daftar/settings.py", "flouci_app_secret={'***' if self.flouci_app_secret else None!r}", "flouci_app_secret={self.flouci_app_secret!r}", "tests/test_settings.py"),
    ("migrations/versions/0001_initial.py", "kind IN ('patients', 'appointments')", "kind IN ('patients', 'appointments', 'invoices')", "tests/test_schema.py"),
    ("migrations/versions/0001_initial.py", "user_id     BIGINT      NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,", "user_id     BIGINT      NOT NULL REFERENCES app_user (id),", "tests/test_schema.py"),
    ("migrations/versions/0002_onboarding_alerts.py", "CHECK (char_length(alerts) <= 500)", "CHECK (char_length(alerts) <= 501)", "tests/test_schema.py"),
    ("daftar/auth.py", "            slug=row.slug,", "            slug=row.specialty,", "tests/test_auth.py"),
    ("daftar/static.py", "csp = ADS_CSP if root == self.landing and candidate in self._ad_pages else None", "csp = None", "tests/test_http.py"),
    ("daftar/static.py", "csp = ADS_CSP if root == self.landing and candidate in self._ad_pages else None", "csp = ADS_CSP", "tests/test_http.py"),
    ("daftar/static.py", 'AD_PAGES = ("index.html", "ar/index.html")', 'AD_PAGES = ("index.html",)', "tests/test_http.py"),
    ("daftar/static.py", '        if file.csp:\n            headers["Content-Security-Policy"] = file.csp', '        if file.csp and request.headers.get("if-none-match") != file.etag:\n            headers["Content-Security-Policy"] = file.csp', "tests/test_http.py"),
    ("daftar/http.py", "\"script-src 'self' 'unsafe-inline' https:; \"", "\"script-src 'self' 'unsafe-inline'; \"", "tests/test_http.py"),
]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    survived = 0
    for file, original, broken, selection in MUTATIONS:
        path = BACKEND / file
        source = path.read_text(encoding="utf-8")
        if original not in source:
            print(f"MISSING   {file}: {original[:60]!r}")
            survived += 1
            continue
        path.write_text(source.replace(original, broken, 1), encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *selection.split()],
                cwd=BACKEND,
                capture_output=True,
                text=True,
            )
        finally:
            path.write_text(source, encoding="utf-8")
        verdict = "killed  " if result.returncode != 0 else "SURVIVED"
        survived += result.returncode == 0
        print(f"{verdict}  {file}: {original.splitlines()[0][:70]}")
    print(f"\n{len(MUTATIONS) - survived}/{len(MUTATIONS)} mutations killed")
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
