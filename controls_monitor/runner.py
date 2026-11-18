import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from controls_monitor.config import SEVERITY_ORDER
from controls_monitor.controls import build_controls
from controls_monitor.logging_setup import log_event
from controls_monitor.models import (
    ControlException,
    ControlResult,
    ControlRun,
)

logger = logging.getLogger("controls_monitor.runner")

EXIT_OK = 0
EXIT_EXCEPTIONS = 1  
EXIT_ERROR = 2  # a control itself crashed


@dataclass
class ControlOutcome:
    control_id: str
    name: str
    severity: str
    status: str  
    exception_count: int
    duration_ms: int
    error_message: str | None = None


@dataclass
class RunSummary:
    run_id: int
    status: str  # success / error
    outcomes: list = field(default_factory=list)
    exceptions_by_severity: dict = field(default_factory=dict)

    @property
    def total_exceptions(self):
        return sum(self.exceptions_by_severity.values())

    @property
    def errored(self):
        return [o for o in self.outcomes if o.status == "error"]

    def count_at_or_above(self, severity):
        floor = SEVERITY_ORDER[severity]
        return sum(
            count
            for sev, count in self.exceptions_by_severity.items()
            if SEVERITY_ORDER[sev] >= floor
        )


def exit_code(summary, fail_on):
    if summary.errored:
        return EXIT_ERROR
    if summary.count_at_or_above(fail_on) > 0:
        return EXIT_EXCEPTIONS
    return EXIT_OK


def _utcnow():
    return datetime.now(timezone.utc)


def run_all(session, config, controls=None, clock=None):
    clock = clock or _utcnow
    controls = build_controls(config) if controls is None else controls
    run_started = time.perf_counter()

    run = ControlRun(status="running", config_snapshot=config.snapshot())
    session.add(run)
    session.commit()
    run_id = run.id
    log_event(
        logger,
        "run_started",
        run_id=run_id,
        controls=[c.control_id for c in controls],
        fail_on_severity=config.fail_on_severity,
    )

    outcomes = []
    by_severity = {sev: 0 for sev in SEVERITY_ORDER}

    for control in controls:
        started = time.perf_counter()
        findings, error = [], None
        try:
            findings = control.run(session)
        except Exception as exc:  
            session.rollback()
            error = f"{type(exc).__name__}: {exc}"[:1000]
        duration_ms = int((time.perf_counter() - started) * 1000)

        status = "error" if error else ("failed" if findings else "passed")
        session.add(
            ControlResult(
                run_id=run_id,
                control_id=control.control_id,
                control_name=control.name,
                severity=control.severity,
                status=status,
                exception_count=len(findings),
                duration_ms=duration_ms,
                error_message=error,
            )
        )
        for finding in findings:
            session.add(
                ControlException(
                    run_id=run_id,
                    control_id=control.control_id,
                    severity=control.severity,
                    expense_id=finding.expense_id,
                    employee_id=finding.employee_id,
                    reason=finding.reason[:255],
                    evidence=finding.evidence,
                )
            )
        session.commit()

        log_event(
            logger,
            "control_finished",
            level=logging.ERROR if error else logging.INFO,
            run_id=run_id,
            control_id=control.control_id,
            severity=control.severity,
            status=status,
            exception_count=len(findings),
            duration_ms=duration_ms,
            **({"error": error} if error else {}),
        )

        by_severity[control.severity] += len(findings)
        outcomes.append(
            ControlOutcome(
                control_id=control.control_id,
                name=control.name,
                severity=control.severity,
                status=status,
                exception_count=len(findings),
                duration_ms=duration_ms,
                error_message=error,
            )
        )

    run = session.get(ControlRun, run_id)
    run.finished_at = clock()
    run.total_exceptions = sum(by_severity.values())
    run.status = "error" if any(o.status == "error" for o in outcomes) else "success"
    session.commit()

    log_event(
        logger,
        "run_finished",
        level=logging.ERROR if run.status == "error" else logging.INFO,
        run_id=run_id,
        status=run.status,
        total_exceptions=run.total_exceptions,
        exceptions_by_severity=by_severity,
        duration_seconds=round(time.perf_counter() - run_started, 3),
    )

    return RunSummary(
        run_id=run_id,
        status=run.status,
        outcomes=outcomes,
        exceptions_by_severity=by_severity,
    )