"""Prometheus metrics (``GET /metrics``, publicly 404 via Caddy).

Every app has its own :class:`Metrics` (own registry – tests never share counters). Business code reaches it through
``ctx.metrics``:

    ctx.metrics.appointments_created.labels("online").inc()       # predefined counters, see below
    ctx.metrics.counter("daftar_reminders_sent_total", "Reminders marked as sent").inc()
    ctx.metrics.gauge("daftar_queue_waiting", "People waiting", ["practice"]).labels("1").set(3)

``counter``/``gauge``/``histogram`` are get-or-create, so calling them in a handler is fine.
Gauges that come from the database (practices, users, patients) are computed at scrape time by a collector.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable, Sequence

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    disable_created_metrics,
    generate_latest,
)
from prometheus_client.core import GaugeMetricFamily, Metric
from prometheus_client.gc_collector import GCCollector
from prometheus_client.platform_collector import PlatformCollector
from prometheus_client.process_collector import ProcessCollector
from prometheus_client.registry import Collector
from sqlalchemy import Engine, func, select

from .tables import app_user, patient, practice

log = logging.getLogger("daftar")
#: Label values of ``daftar_appointments_created_total{source}``.
APPOINTMENT_SOURCES = ("staff", "online", "series", "import")
disable_created_metrics()  # no *_created series next to every counter


class Metrics:
    content_type = CONTENT_TYPE_LATEST

    def __init__(self) -> None:
        self.registry = CollectorRegistry(auto_describe=True)
        ProcessCollector(registry=self.registry)
        PlatformCollector(registry=self.registry)
        GCCollector(registry=self.registry)
        self._lock = threading.Lock()
        self._own: dict[str, Counter | Gauge | Histogram] = {}

        self.http_requests = self.counter(
            "daftar_http_requests_total", "HTTP requests by route template and status", ["method", "route", "status"]
        )
        self.http_duration = self.histogram(
            "daftar_http_request_duration_seconds",
            "HTTP request duration by route template",
            ["method", "route"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
        )
        #: result: ok | failed | throttled
        self.logins = self.counter("daftar_logins_total", "Login attempts by result", ["result"])
        for result in ("ok", "failed", "throttled"):
            self.logins.labels(result)
        # Business counters of the design (section 5 “Betrieb”) – the feature modules increment them.
        #: source: staff (agenda) | online (booking page) | series (recurring, by staff) | import (Excel/CSV)
        self.appointments_created = self.counter(
            "daftar_appointments_created_total", "Appointments created by source", ["source"]
        )
        for source in APPOINTMENT_SOURCES:  # exported with 0 from the start, so increase() sees the first one
            self.appointments_created.labels(source)
        self.demo_started = self.counter("daftar_demo_started_total", "Demo practices started")
        self.pilot_requests = self.counter("daftar_pilot_requests_total", "Pilot requests received")

    # --- get-or-create -------------------------------------------------------------------------------------------

    def counter(self, name: str, documentation: str, labelnames: Sequence[str] = ()) -> Counter:
        return self._get(name, lambda: Counter(name, documentation, labelnames, registry=self.registry))

    def gauge(self, name: str, documentation: str, labelnames: Sequence[str] = ()) -> Gauge:
        return self._get(name, lambda: Gauge(name, documentation, labelnames, registry=self.registry))

    def histogram(
        self, name: str, documentation: str, labelnames: Sequence[str] = (), buckets: Sequence[float] | None = None
    ) -> Histogram:
        kwargs = {"buckets": buckets} if buckets else {}
        return self._get(name, lambda: Histogram(name, documentation, labelnames, registry=self.registry, **kwargs))

    def _get(self, name: str, make: Callable[[], Counter | Gauge | Histogram]):  # type: ignore[no-untyped-def]
        with self._lock:
            metric = self._own.get(name)
            if metric is None:
                metric = make()
                self._own[name] = metric
            return metric

    def add_collector(self, collect: Callable[[], Iterable[Metric]]) -> None:
        """Values computed at scrape time, e.g. counts from the database."""
        self.registry.register(_FnCollector(collect))

    def render(self) -> bytes:
        return generate_latest(self.registry)


class _FnCollector(Collector):
    def __init__(self, fn: Callable[[], Iterable[Metric]]) -> None:
        self._fn = fn

    def collect(self) -> Iterable[Metric]:
        try:
            return list(self._fn())
        except Exception:  # a scrape must never fail because the database is down
            log.warning("metrics collector failed", exc_info=True)
            return []

    def describe(self) -> Iterable[Metric]:
        return []


def database_gauges(engine: Engine) -> Callable[[], Iterable[Metric]]:
    """``daftar_practices{kind="pilot|demo"}``, ``daftar_users`` (without the admin), ``daftar_patients``."""

    def collect() -> Iterable[Metric]:
        with engine.connect() as conn:
            kinds = dict(conn.execute(select(practice.c.is_demo, func.count()).group_by(practice.c.is_demo)).all())
            users = conn.execute(select(func.count()).select_from(app_user).where(app_user.c.role != "admin")).scalar_one()
            patients = conn.execute(select(func.count()).select_from(patient)).scalar_one()
        practices = GaugeMetricFamily("daftar_practices", "Practices by kind", labels=["kind"])
        practices.add_metric(["pilot"], kinds.get(False, 0))
        practices.add_metric(["demo"], kinds.get(True, 0))
        yield practices
        yield GaugeMetricFamily("daftar_users", "User accounts in practices", value=users)
        yield GaugeMetricFamily("daftar_patients", "Patients in all practices", value=patients)

    return collect
