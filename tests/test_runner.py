from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select, text
from controls_monitor.config import load_config
from controls_monitor.controls.base import Control
from controls_monitor.controls.c1_duplicate_claims import DuplicateClaims
from controls_monitor.generator import seed_clean_org
from controls_monitor.models import ControlException, ControlResult, ControlRun
from controls_monitor.runner import (
    EXIT_ERROR,
    EXIT_EXCEPTIONS,
    EXIT_OK,
    ControlOutcome,
    RunSummary,
    exit_code,
    run_all,
)
from tests.helpers import make_claim, make_org


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


# ---------- the happy path ----------


def test_clean_company_run_passes_every_control(db):
    seed_clean_org(db)
    summary = run_all(db, load_config())

    assert summary.status == "success"
    assert [o.control_id for o in summary.outcomes] == ["C1", "C2", "C3", "C4", "C5", "C6"]
    assert {o.status for o in summary.outcomes} == {"passed"}
    assert summary.total_exceptions == 0
    assert exit_code(summary, "high") == EXIT_OK


def test_run_and_results_are_saved_to_the_database(db):
    seed_clean_org(db)
    fixed = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    summary = run_all(db, load_config(), clock=lambda: fixed)

    run = db.get(ControlRun, summary.run_id)
    assert run.status == "success"
    assert run.finished_at == fixed
    assert run.total_exceptions == 0
    assert run.config_snapshot["controls"]["C2"]["approval_limit"] == 500

    results = db.scalars(
        select(ControlResult).where(ControlResult.run_id == run.id).order_by(ControlResult.id)
    ).all()
    assert [r.control_id for r in results] == ["C1", "C2", "C3", "C4", "C5", "C6"]
    assert all(r.duration_ms >= 0 for r in results)
    assert results[0].severity == "high"


def test_each_run_adds_to_the_history(db):
    seed_clean_org(db)
    first = run_all(db, load_config())
    second = run_all(db, load_config())

    assert second.run_id > first.run_id
    assert count(db, ControlRun) == 2
    assert count(db, ControlResult) == 12


def test_disabled_controls_are_not_run(db):
    seed_clean_org(db)
    config = load_config()
    config.controls.C2.enabled = False
    summary = run_all(db, config)
    assert [o.control_id for o in summary.outcomes] == ["C1", "C3", "C4", "C5", "C6"]


# ---------- exceptions are stored with their evidence ----------


def test_findings_are_stored_as_exceptions_with_evidence(db):
    org = make_org(db)
    claim = make_claim(db, org.alice, approver_id=org.bob.id)  # a peer approved it

    summary = run_all(db, load_config())

    assert summary.exceptions_by_severity["critical"] == 1
    row = db.scalars(select(ControlException)).one()
    assert row.control_id == "C3"
    assert row.severity == "critical"
    assert row.expense_id == claim.id
    assert row.employee_id == org.alice.id
    assert row.evidence["violation_type"] == "not_manager"
    assert "not the employee's manager" in row.reason

    result = db.scalars(select(ControlResult).where(ControlResult.control_id == "C3")).one()
    assert result.status == "failed"
    assert result.exception_count == 1

    run = db.get(ControlRun, summary.run_id)
    assert run.total_exceptions == 1


# ---------- exit codes ----------


def test_critical_exception_fails_the_default_gate(db):
    org = make_org(db)
    make_claim(db, org.alice, approver_id=org.bob.id)
    summary = run_all(db, load_config())
    assert exit_code(summary, "high") == EXIT_EXCEPTIONS


def test_low_severity_exception_does_not_fail_the_default_gate(db):
    org = make_org(db)
    saturday = datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc)
    make_claim(db, org.alice, submitted_at=saturday - timedelta(hours=3), approved_at=saturday)

    summary = run_all(db, load_config())

    assert summary.exceptions_by_severity["low"] == 1
    assert summary.total_exceptions == 1
    assert exit_code(summary, "high") == EXIT_OK
    assert exit_code(summary, "low") == EXIT_EXCEPTIONS


def test_exit_code_helper_cases():
    def summary(by_sev, status="passed"):
        base = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        base.update(by_sev)
        outcome = ControlOutcome("C1", "x", "high", status, 0, 1)
        return RunSummary(run_id=1, status="success", outcomes=[outcome], exceptions_by_severity=base)

    assert exit_code(summary({}), "high") == EXIT_OK
    assert exit_code(summary({"medium": 5}), "high") == EXIT_OK
    assert exit_code(summary({"medium": 5}), "medium") == EXIT_EXCEPTIONS
    assert exit_code(summary({"high": 1}), "high") == EXIT_EXCEPTIONS
    assert exit_code(summary({"critical": 1}), "high") == EXIT_EXCEPTIONS
    assert exit_code(summary({}, status="error"), "high") == EXIT_ERROR


# ---------- a broken control must not look green ----------


class BrokenControl(Control):
    control_id = "C2"
    name = "Broken on purpose"
    sql_file = "broken.sql"

    def row_to_finding(self, row):  # pragma: no cover
        raise AssertionError


def test_a_crashing_control_is_recorded_as_error_and_the_others_still_run(db, tmp_path):
    seed_clean_org(db)
    (tmp_path / "broken.sql").write_text("SELECT * FROM table_that_does_not_exist")
    BrokenControl.sql_dir = tmp_path
    config = load_config()
    controls = [BrokenControl(config.controls.C2), DuplicateClaims(config.controls.C1)]

    summary = run_all(db, config, controls=controls)

    broken, good = summary.outcomes
    assert broken.status == "error"
    assert "table_that_does_not_exist" in broken.error_message
    assert good.status == "passed"
    assert summary.status == "error"
    assert exit_code(summary, "high") == EXIT_ERROR

    run = db.get(ControlRun, summary.run_id)
    assert run.status == "error"
    stored = db.scalars(select(ControlResult).order_by(ControlResult.id)).all()
    assert [r.status for r in stored] == ["error", "passed"]
    assert stored[0].error_message is not None


# ---------- crash safety ----------


class SpyControl(Control):
    control_id = "C1"
    name = "Spy"
    seen_status = None

    def run(self, session):
        SpyControl.seen_status = session.execute(
            text("SELECT status FROM control_runs ORDER BY id DESC LIMIT 1")
        ).scalar()
        return []


def test_run_is_visible_as_running_while_controls_execute(db):
    config = load_config()
    run_all(db, config, controls=[SpyControl(config.controls.C1)])
    assert SpyControl.seen_status == "running"


def test_a_long_reason_is_truncated_instead_of_crashing(db):
    class Chatty(Control):
        control_id = "C1"
        name = "Chatty"

        def run(self, session):
            from controls_monitor.controls.base import Finding

            return [Finding(reason="x" * 500)]

    config = load_config()
    summary = run_all(db, config, controls=[Chatty(config.controls.C1)])
    assert summary.total_exceptions == 1
    assert len(db.scalars(select(ControlException)).one().reason) == 255