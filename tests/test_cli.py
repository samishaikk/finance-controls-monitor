from datetime import datetime, timezone
from controls_monitor.cli import main
from controls_monitor.generator import seed_clean_org
from tests.helpers import make_claim, make_org


def test_run_command_on_a_clean_company_exits_zero(db, engine, capsys):
    seed_clean_org(db)
    code = main(["run"], engine=engine)
    out = capsys.readouterr().out

    assert code == 0
    assert "Duplicate claims" in out
    assert "C6" in out
    assert "exit code: 0" in out


def test_run_command_exits_one_when_a_serious_exception_is_found(db, engine, capsys):
    org = make_org(db)
    make_claim(db, org.alice, approver_id=org.bob.id)
    code = main(["run"], engine=engine)
    out = capsys.readouterr().out

    assert code == 1
    assert "critical=1" in out
    assert "1 exception(s) at or above 'high'" in out


def test_fail_on_flag_overrides_the_config(db, engine, capsys):
    org = make_org(db)
    saturday = datetime(2026, 1, 10, 10, 0, tzinfo=timezone.utc)
    make_claim(db, org.alice, submitted_at=saturday.replace(hour=7), approved_at=saturday)

    assert main(["run"], engine=engine) == 0
    assert main(["run", "--fail-on", "low"], engine=engine) == 1


def test_bad_config_exits_with_the_error_code(db, engine, tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text("controls: {}\n")
    code = main(["run", "--config", str(bad)], engine=engine)
    assert code == 2
    assert "invalid config" in capsys.readouterr().err


def test_history_command_lists_runs(db, engine, capsys):
    seed_clean_org(db)
    main(["run"], engine=engine)
    main(["run"], engine=engine)
    capsys.readouterr()

    assert main(["history"], engine=engine) == 0
    out = capsys.readouterr().out
    assert "success" in out
    assert len([line for line in out.splitlines() if "success" in line]) == 2


def test_history_with_no_runs(db, engine, capsys):
    assert main(["history"], engine=engine) == 0
    assert "no runs yet" in capsys.readouterr().out