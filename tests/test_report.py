from datetime import datetime, timedelta, timezone
import pytest
from controls_monitor.config import load_config
from controls_monitor.controls.base import Control
from controls_monitor.generator import seed_clean_org
from controls_monitor.report import ReportError, build_report, md
from controls_monitor.runner import run_all
from tests.helpers import make_claim, make_org

SATURDAY = datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc)

def test_clean_run_report_says_pass(db):
    seed_clean_org(db)
    summary = run_all(db, load_config())
    report = build_report(db, summary.run_id)

    assert f"# Finance Controls Monitor - run {summary.run_id}" in report
    assert "Result: **PASS**" in report
    assert "No exceptions found." in report
    for name in ("Duplicate claims", "Split claims under the approval limit", "Off-hours or weekend approval"):
        assert name in report
    assert "## C3" not in report  # no exception sections when nothing was found


def test_report_shows_exceptions_with_names_reason_and_evidence(db):
    org = make_org(db)
    claim = make_claim(db, org.alice, approver_id=org.bob.id)
    summary = run_all(db, load_config())
    report = build_report(db, summary.run_id)

    assert "Result: **FAIL (1 exception(s) at or above 'high')**" in report
    assert "## C3 - Approver is not the employee's manager (critical) - 1 exception(s)" in report
    assert f"| #{claim.id} | Alice Analyst (#{org.alice.id}) |" in report
    assert "not the employee's manager" in report
    assert "violation_type: not_manager" in report
    assert f"approver_id: {org.bob.id}" in report


def test_most_serious_controls_come_first(db):
    org = make_org(db)
    make_claim(db, org.alice, approver_id=org.bob.id)  # C3, critical
    make_claim(  # C6, low
        db, org.bob, amount="55.00",
        submitted_at=SATURDAY - timedelta(hours=3), approved_at=SATURDAY,
    )
    report = build_report(db, run_all(db, load_config()).run_id)
    assert report.index("## C3") < report.index("## C6")


def test_long_lists_are_cut_but_the_total_is_kept(db):
    org = make_org(db)
    for i in range(5):
        when = SATURDAY + timedelta(days=7 * i)
        make_claim(
            db, org.alice, amount=f"{20 + i}.00",
            submitted_at=when - timedelta(hours=3), approved_at=when,
        )
    report = build_report(db, run_all(db, load_config()).run_id, max_rows=2)

    assert "## C6 - Off-hours or weekend approval (low) - 5 exception(s)" in report
    assert "_Showing 2 of 5." in report
    assert report.count("approved on a Saturday") == 2


def test_threshold_comes_from_the_stored_config(db):
    org = make_org(db)
    make_claim(db, org.alice, submitted_at=SATURDAY - timedelta(hours=3), approved_at=SATURDAY)

    default_run = run_all(db, load_config())
    strict = load_config()
    strict.fail_on_severity = "low"
    strict_run = run_all(db, strict)

    assert "Result: **PASS**" in build_report(db, default_run.run_id)
    assert "Result: **FAIL" in build_report(db, strict_run.run_id)


class Crashing(Control):
    control_id = "C1"
    name = "Crashing control"

    def run(self, session):
        raise RuntimeError("boom")


def test_a_crashed_control_is_shown_as_an_error(db):
    config = load_config()
    summary = run_all(db, config, controls=[Crashing(config.controls.C1)])
    report = build_report(db, summary.run_id)

    assert "Result: **ERROR (1 control(s) crashed)**" in report
    assert "## Errors" in report
    assert "RuntimeError: boom" in report


def test_the_same_run_always_gives_the_same_report(db):
    org = make_org(db)
    make_claim(db, org.alice, approver_id=org.bob.id)
    run_id = run_all(db, load_config()).run_id
    assert build_report(db, run_id) == build_report(db, run_id)


def test_unknown_run_is_an_error(db):
    with pytest.raises(ReportError, match="run 999 not found"):
        build_report(db, 999)


def test_table_cells_are_escaped():
    assert md("a|b\nc") == "a\\|b c"
    assert md("x" * 400).endswith("...")
    assert len(md("x" * 400)) == 300