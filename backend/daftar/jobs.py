"""Periodic background jobs, run inside the app process (one container) while it is up.

Register a job by adding it to :data:`JOBS`::

    Job("demo-cleanup", timedelta(minutes=30), demo.cleanup)     # def cleanup(ctx: AppContext) -> None

A job runs first ``every`` after startup, then every ``every``; it runs in a worker thread (it may use the
database through ``ctx.engine.begin()``), errors are logged and the job keeps its schedule.
Tests create the app with ``run_jobs=False`` and call job functions directly.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

import anyio

from .context import AppContext
from .invitations import delete_stale_invitations
from .demo import cleanup_demos  # be-patienten
from .pilot import cleanup_pilot_requests  # be-patienten

log = logging.getLogger("daftar")


@dataclass(frozen=True)
class Job:
    name: str
    every: timedelta
    run: Callable[[AppContext], None]


def cleanup_invitations(ctx: AppContext) -> None:
    with ctx.engine.begin() as conn:
        deleted = delete_stale_invitations(conn, ctx.clock.now())
    if deleted:
        log.info("deleted %d stale invitations", deleted)


JOBS: list[Job] = [
    Job("invitation-cleanup", timedelta(minutes=30), cleanup_invitations),
    Job("pilot-request-cleanup", timedelta(hours=24), cleanup_pilot_requests),  # be-patienten
    Job("demo-cleanup", timedelta(minutes=30), cleanup_demos),  # be-patienten
]


async def run_forever(job: Job, ctx: AppContext) -> None:
    while True:
        await asyncio.sleep(job.every.total_seconds())
        try:
            await anyio.to_thread.run_sync(job.run, ctx)
        except Exception:
            log.exception("job %s failed", job.name)
