from pathlib import Path
from prometheus_client import CollectorRegistry, Gauge, generate_latest, write_to_textfile
from sqlalchemy import func, select

from controls_monitor.config import SEVERITY_ORDER
from controls_monitor.models import ControlResult, ControlRun

PREFIX = "controls_monitor_"


class MetricsError(Exception):
    pass


def build_registry(session, run_id):
    run = session.get(ControlRun, run_id)
    if run is None:
        raise MetricsError(f"run {run_id} not found")
    results = session.scalars(
        select(ControlResult).where(ControlResult.run_id == run_id).order_by(ControlResult.id)
    ).all()

    registry = CollectorRegistry()

    def gauge(name, doc, labels=()):
        return Gauge(PREFIX + name, doc, labels, registry=registry)

    if run.finished_at is not None:
        gauge("run_duration_seconds", "Wall-clock duration of the run.").set(
            (run.finished_at - run.started_at).total_seconds()
        )
        gauge("last_run_timestamp_seconds", "Unix time the run finished.").set(
            run.finished_at.timestamp()
        )

    last_success = session.scalar(
        select(func.max(ControlRun.finished_at)).where(ControlRun.status == "success")
    )
    if last_success is not None:
        gauge(
            "last_successful_run_timestamp_seconds",
            "Unix time of the most recent run in which every control executed.",
        ).set(last_success.timestamp())

    gauge("last_run_success", "1 if every control executed in the run, else 0.").set(
        1 if run.status == "success" else 0
    )

    exceptions = gauge(
        "exceptions", "Exceptions found by a control in the run.", ["control_id", "severity"]
    )
    duration = gauge("control_duration_seconds", "Time a control took.", ["control_id"])
    errored = gauge(
        "control_errored", "1 if the control crashed instead of finishing.", ["control_id"]
    )
    for r in results:
        exceptions.labels(r.control_id, r.severity).set(r.exception_count)
        duration.labels(r.control_id).set(r.duration_ms / 1000)
        errored.labels(r.control_id).set(1 if r.status == "error" else 0)

    fail_on = (run.config_snapshot or {}).get("fail_on_severity", "high")
    gauge(
        "exceptions_at_or_above_threshold",
        "Exceptions at or above the run's fail threshold (what would fail CI).",
    ).set(
        sum(
            r.exception_count
            for r in results
            if SEVERITY_ORDER[r.severity] >= SEVERITY_ORDER[fail_on]
        )
    )

    runs = gauge("runs", "Number of stored runs, by status.", ["status"])
    counts = dict(
        session.execute(select(ControlRun.status, func.count()).group_by(ControlRun.status)).all()
    )
    for status in ("success", "error", "running"):
        runs.labels(status).set(counts.get(status, 0))

    return registry


def render(session, run_id):
    return generate_latest(build_registry(session, run_id)).decode("utf-8")


def write_metrics(session, run_id, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_to_textfile(str(path), build_registry(session, run_id))
    return path