import pytest
from prometheus_client.parser import text_string_to_metric_families
from controls_monitor.cli import main
from controls_monitor.config import load_config
from controls_monitor.controls.base import Control
from controls_monitor.generator import seed_clean_org
from controls_monitor.metrics import MetricsError, render, write_metrics
from controls_monitor.models import ControlRun
from controls_monitor.runner import run_all
from tests.helpers import make_claim, make_org


def samples(text):
    """Parse metrics text into {(name, labels...): value}. Also proves the format is valid."""
    found = {}
    for family in text_string_to_metric_families(text):
        for s in family.samples:
            found[(s.name, tuple(sorted(s.labels.items())))] = s.value
    return found


def value(found, name, **labels):
    return found[("controls_monitor_" + name, tuple(sorted(labels.items())))]


def test_clean_run_metrics(db):
    seed_clean_org(db)
    run_id = run_all(db, load_config()).run_id
    found = samples(render(db, run_id))

    assert value(found, "last_run_success") == 1
    assert value(found, "run_duration_seconds") >= 0
    assert value(found, "exceptions_at_or_above_threshold") == 0
    assert value(found, "exceptions", control_id="C1", severity="high") == 0
    assert value(found, "control_errored", control_id="C6") == 0
    assert value(found, "control_duration_seconds", control_id="C2") >= 0
    assert value(found, "runs", status="success") == 1
    assert value(found, "runs", status="error") == 0
    assert ("controls_monitor_last_successful_run_timestamp_seconds", ()) in found


def test_every_control_has_a_series_even_with_zero_exceptions(db):
    seed_clean_org(db)
    found = samples(render(db, run_all(db, load_config()).run_id))
    exception_series = [k for k in found if k[0] == "controls_monitor_exceptions"]
    assert len(exception_series) == 6


def test_exceptions_are_counted_per_control_and_severity(db):
    org = make_org(db)
    make_claim(db, org.alice, approver_id=org.bob.id)  # one critical (C3)
    found = samples(render(db, run_all(db, load_config()).run_id))

    assert value(found, "exceptions", control_id="C3", severity="critical") == 1
    assert value(found, "exceptions", control_id="C1", severity="high") == 0
    assert value(found, "exceptions_at_or_above_threshold") == 1


class Crashing(Control):
    control_id = "C1"
    name = "Crashing control"

    def run(self, session):
        raise RuntimeError("boom")


def test_a_crashed_control_shows_up_as_errored_and_the_run_as_unsuccessful(db):
    config = load_config()
    run_id = run_all(db, config, controls=[Crashing(config.controls.C1)]).run_id
    found = samples(render(db, run_id))

    assert value(found, "control_errored", control_id="C1") == 1
    assert value(found, "last_run_success") == 0
    assert value(found, "runs", status="error") == 1


def test_last_successful_run_survives_a_later_failed_run(db):
    seed_clean_org(db)
    config = load_config()
    good = run_all(db, config)
    bad = run_all(db, config, controls=[Crashing(config.controls.C1)])

    found = samples(render(db, bad.run_id))
    good_finished = db.get(ControlRun, good.run_id).finished_at.timestamp()
    key = ("controls_monitor_last_successful_run_timestamp_seconds", ())
    assert found[key] == pytest.approx(good_finished)
    assert value(found, "last_run_success") == 0


def test_no_successful_run_means_no_last_success_series(db):
    config = load_config()
    run_id = run_all(db, config, controls=[Crashing(config.controls.C1)]).run_id
    found = samples(render(db, run_id))
    assert ("controls_monitor_last_successful_run_timestamp_seconds", ()) not in found


def test_unknown_run_is_an_error(db):
    with pytest.raises(MetricsError, match="run 999 not found"):
        render(db, 999)


def test_metrics_file_is_written_and_parseable(db, tmp_path):
    seed_clean_org(db)
    run_id = run_all(db, load_config()).run_id
    target = write_metrics(db, run_id, tmp_path / "deep" / "controls_monitor.prom")

    found = samples(target.read_text(encoding="utf-8"))
    assert value(found, "last_run_success") == 1


def test_metrics_command_prints_the_latest_run(db, engine, capsys):
    seed_clean_org(db)
    main(["run"], engine=engine)
    capsys.readouterr()

    assert main(["metrics"], engine=engine) == 0
    assert "controls_monitor_last_run_success 1.0" in capsys.readouterr().out


def test_run_can_write_metrics_in_one_go(db, engine, tmp_path, capsys):
    seed_clean_org(db)
    target = tmp_path / "m.prom"
    assert main(["run", "--metrics", str(target)], engine=engine) == 0
    assert "controls_monitor_run_duration_seconds" in target.read_text(encoding="utf-8")
    assert "metrics written to" in capsys.readouterr().out


def test_metrics_with_no_runs_is_an_error(db, engine, capsys):
    assert main(["metrics"], engine=engine) == 2
    assert "no runs yet" in capsys.readouterr().err