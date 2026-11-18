import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

from controls_monitor.cli import main
from controls_monitor.config import load_config
from controls_monitor.controls.base import Control
from controls_monitor.generator import seed_clean_org
from controls_monitor.logging_setup import JsonFormatter, configure_logging, log_event
from controls_monitor.runner import run_all
from tests.helpers import make_claim, make_org

def make_record(event="something_happened", level=logging.INFO, **fields):
    record = logging.LogRecord("controls_monitor.test", level, __file__, 1, event, None, None)
    record.fields = fields
    return record


def test_formatter_writes_one_json_object_with_the_basics():
    line = JsonFormatter().format(make_record(run_id=7, status="ok"))
    data = json.loads(line)

    assert "\n" not in line
    assert data["event"] == "something_happened"
    assert data["level"] == "INFO"
    assert data["logger"] == "controls_monitor.test"
    assert data["run_id"] == 7
    assert data["status"] == "ok"
    assert data["timestamp"].endswith("+00:00")


def test_formatter_copes_with_values_json_cannot_store():
    when = datetime(2026, 1, 5, tzinfo=timezone.utc)
    data = json.loads(JsonFormatter().format(make_record(amount=Decimal("12.50"), when=when)))
    assert data["amount"] == "12.50"
    assert data["when"].startswith("2026-01-05")


def test_a_field_cannot_overwrite_a_reserved_key():
    record = make_record()
    record.fields = {"level": "custom", "event": "other"}
    data = json.loads(JsonFormatter().format(record))
    assert data["level"] == "INFO"
    assert data["event"] == "something_happened"
    assert data["field_level"] == "custom"
    assert data["field_event"] == "other"


def test_exception_text_is_included():
    try:
        raise ValueError("bad value")
    except ValueError:
        import sys

        record = make_record(level=logging.ERROR)
        record.exc_info = sys.exc_info()
    assert "ValueError: bad value" in json.loads(JsonFormatter().format(record))["exception"]


def test_configuring_twice_does_not_duplicate_log_lines(capsys):
    configure_logging("INFO")
    configure_logging("INFO")
    log_event(logging.getLogger("controls_monitor.test"), "hello", run_id=1)

    lines = [line for line in capsys.readouterr().err.splitlines() if line]
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "hello"


def events(caplog):
    return [(r.getMessage(), r.fields) for r in caplog.records if r.name.startswith("controls_monitor")]


def test_a_run_logs_start_each_control_and_finish(db, caplog):
    seed_clean_org(db)
    caplog.set_level(logging.INFO, logger="controls_monitor")
    summary = run_all(db, load_config())

    logged = events(caplog)
    names = [name for name, _ in logged]
    assert names == ["run_started"] + ["control_finished"] * 6 + ["run_finished"]
    assert {fields["run_id"] for _, fields in logged} == {summary.run_id}

    first_control = logged[1][1]
    assert first_control["control_id"] == "C1"
    assert first_control["status"] == "passed"
    assert first_control["duration_ms"] >= 0

    finished = logged[-1][1]
    assert finished["status"] == "success"
    assert finished["total_exceptions"] == 0
    assert finished["duration_seconds"] >= 0


def test_findings_show_up_in_the_logs(db, caplog):
    org = make_org(db)
    make_claim(db, org.alice, approver_id=org.bob.id)
    caplog.set_level(logging.INFO, logger="controls_monitor")
    run_all(db, load_config())

    c3 = next(f for n, f in events(caplog) if n == "control_finished" and f["control_id"] == "C3")
    assert c3["status"] == "failed"
    assert c3["exception_count"] == 1
    assert c3["severity"] == "critical"
    finished = events(caplog)[-1][1]
    assert finished["exceptions_by_severity"]["critical"] == 1


class Crashing(Control):
    control_id = "C1"
    name = "Crashing control"

    def run(self, session):
        raise RuntimeError("boom")


def test_a_crashing_control_is_logged_at_error_level(db, caplog):
    caplog.set_level(logging.INFO, logger="controls_monitor")
    config = load_config()
    run_all(db, config, controls=[Crashing(config.controls.C1)])

    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert [r.getMessage() for r in errors] == ["control_finished", "run_finished"]
    assert "RuntimeError: boom" in errors[0].fields["error"]
    assert errors[1].fields["status"] == "error"


def test_cli_run_writes_json_lines_to_stderr_and_the_table_to_stdout(db, engine, capsys):
    seed_clean_org(db)
    main(["run"], engine=engine)
    captured = capsys.readouterr()

    log_lines = [json.loads(line) for line in captured.err.splitlines() if line.startswith("{")]
    assert [e["event"] for e in log_lines][0] == "run_started"
    assert [e["event"] for e in log_lines][-1] == "run_finished"
    assert "exit code: 0" in captured.out
    assert "run_started" not in captured.out


def test_log_level_can_silence_the_info_lines(db, engine, capsys):
    seed_clean_org(db)
    main(["run", "--log-level", "WARNING"], engine=engine)
    assert capsys.readouterr().err == ""