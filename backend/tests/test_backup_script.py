"""ops/backup.sh (fixlist 7) – run in the image it runs in production (postgres:17-alpine) against the test database.

The container reaches the database on the host as ``host.docker.internal`` (Docker Desktop and Linux with
``--add-host=host.docker.internal:host-gateway``). The password only travels as the environment variable PGPASSWORD,
like in docker-compose.prod.yml and in the restore command of the README. Skipped when Docker is not available.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from tests.conftest import TEST_DATABASE_URL

SCRIPT = Path(__file__).resolve().parents[2] / "ops" / "backup.sh"
IMAGE = "postgres:17-alpine"
DUMP_NAME = re.compile(r"^daftar-\d{4}-\d{2}-\d{2}_\d{4}\.dump$")
DAY = 86400


def _docker_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=30).returncode == 0
    except subprocess.TimeoutExpired:
        return False


pytestmark = pytest.mark.skipif(not _docker_ready(), reason="Docker is not available")

URL = make_url(TEST_DATABASE_URL)
DB_HOST = "host.docker.internal" if URL.host in ("localhost", "127.0.0.1") else URL.host


def in_container(backups: Path, *command: str, password: str | None = None, **env: str) -> subprocess.CompletedProcess[str]:
    """``docker run postgres:17-alpine <command>`` with the script and ``backups`` mounted, connected to the test DB."""
    settings = {"PGHOST": DB_HOST, "PGPORT": str(URL.port or 5432), "PGUSER": URL.username or "",
                "PGDATABASE": URL.database or "", "TZ": "CET-1CEST,M3.5.0,M10.5.0/3", **env}  # as in docker-compose.prod.yml
    args = ["docker", "run", "--rm", "--add-host=host.docker.internal:host-gateway",
            "--mount", f"type=bind,source={SCRIPT},target=/ops/backup.sh,readonly",
            "--mount", f"type=bind,source={backups},target=/backups",
            "-e", "PGPASSWORD"]
    for name, value in settings.items():
        args += ["-e", f"{name}={value}"]
    secret = URL.password if password is None else password
    return subprocess.run([*args, IMAGE, *command], env={**os.environ, "PGPASSWORD": secret or ""},
                          capture_output=True, text=True, encoding="utf-8", timeout=180)


def age(path: Path, days: float) -> None:
    then = time.time() - days * DAY
    os.utime(path, (then, then))


def test_a_backup_is_a_dump_and_old_ones_are_deleted(tmp_path: Path, make_practice: Any) -> None:
    make_practice("Cabinet Sauvegarde", slug="cabinet-sauvegarde")
    backups = tmp_path.resolve()
    old, recent, other = backups / "daftar-2026-10-01_0230.dump", backups / "daftar-2026-10-20_0230.dump", backups / "notes.txt"
    for path, days in ((old, 15), (recent, 10), (other, 30)):
        path.write_bytes(b"PGDMP old")
        age(path, days)

    res = in_container(backups, "sh", "/ops/backup.sh")

    assert res.returncode == 0, res.stdout + res.stderr
    assert URL.password not in res.stdout + res.stderr
    made = [p for p in backups.iterdir() if DUMP_NAME.match(p.name) and p not in (old, recent)]
    assert len(made) == 1, sorted(p.name for p in backups.iterdir())
    assert made[0].read_bytes()[:5] == b"PGDMP"  # pg_dump's custom format
    assert made[0].stat().st_size > 10_000
    assert not old.exists()  # older than 14 days
    assert recent.exists() and other.exists()  # younger, or not a backup
    assert not list(backups.glob("*.partial"))
    assert made[0].name in res.stdout


def test_the_dump_restores_into_an_empty_database(tmp_path: Path, make_practice: Any) -> None:
    """The restore command of the README, against a throwaway database."""
    make_practice("Cabinet Sauvegarde", slug="cabinet-sauvegarde")
    backups = tmp_path.resolve()
    assert in_container(backups, "sh", "/ops/backup.sh").returncode == 0
    dump = next(p.name for p in backups.iterdir() if DUMP_NAME.match(p.name))
    scratch = "daftar_restore_check"
    admin = create_engine(URL.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch}"'))
            conn.execute(text(f'CREATE DATABASE "{scratch}"'))
        res = in_container(backups, "pg_restore", "--dbname", scratch, "--clean", "--if-exists", "--no-owner",
                           "--single-transaction", "--exit-on-error", f"/backups/{dump}")
        assert res.returncode == 0, res.stderr
        restored = create_engine(URL.set(database=scratch))
        with restored.connect() as conn:
            assert conn.execute(text("SELECT name FROM practice WHERE slug = 'cabinet-sauvegarde'")).scalar_one() == "Cabinet Sauvegarde"
            assert conn.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 1
        restored.dispose()
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch}" WITH (FORCE)'))
        admin.dispose()


def test_a_failed_backup_leaves_nothing_and_never_prints_the_password(tmp_path: Path) -> None:
    backups = tmp_path.resolve()
    res = in_container(backups, "sh", "/ops/backup.sh", password="falsches-geheimnis-4711")
    assert res.returncode != 0
    assert "falsches-geheimnis-4711" not in res.stdout + res.stderr
    assert "FAILED" in res.stdout + res.stderr
    assert list(backups.iterdir()) == []


def _epoch(*local: int) -> int:
    """A Berlin wall-clock time on 30./31.10.2026 (CET, UTC+1 – summer time ended on 25.10.)."""
    return int(datetime(*local, tzinfo=UTC).timestamp()) - 3600


def test_the_daily_run_waits_for_half_past_two(tmp_path: Path) -> None:
    cases = {
        _epoch(2026, 10, 30, 1, 30): 3600,  # an hour before
        _epoch(2026, 10, 30, 2, 30): DAY,  # just done → tomorrow
        _epoch(2026, 10, 30, 3, 0): DAY - 1800,
        _epoch(2026, 10, 30, 23, 59): 2 * 3600 + 31 * 60,
    }
    loop = "; ".join(f"NOW={now} sh /ops/backup.sh --next" for now in cases)
    res = in_container(tmp_path.resolve(), "sh", "-c", loop)
    assert res.returncode == 0, res.stderr
    assert [int(line) for line in res.stdout.split()] == list(cases.values())
