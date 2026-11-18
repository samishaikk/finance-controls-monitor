from datetime import datetime, timezone
from decimal import Decimal
import pytest

from controls_monitor.config import load_config
from controls_monitor.controls.base import Control, Finding
from controls_monitor.controls.registry import (
    UnknownControlError,
    build_controls,
    register,
)




class DemoControl(Control):
    """A tiny control that only exists for these tests."""

    control_id = "C1"
    name = "Demo"
    sql_file = "demo.sql"

    def row_to_finding(self, row):
        return Finding(
            reason=f"window is {row['window_days']} days",
            expense_id=row["expense_id"],
            evidence=row,
        )


def make_demo(tmp_path, sql):
    (tmp_path / "demo.sql").write_text(sql, encoding="utf-8")
    DemoControl.sql_dir = tmp_path
    return DemoControl(load_config().controls.C1)


def test_control_runs_its_sql_and_returns_findings(db, tmp_path):
    control = make_demo(tmp_path, "SELECT 7 AS expense_id, :window_days AS window_days")
    findings = control.run(db)
    assert len(findings) == 1
    assert findings[0].expense_id == 7
    assert findings[0].reason == "window is 7 days"


def test_control_with_no_matches_returns_empty_list(db, tmp_path):
    control = make_demo(tmp_path, "SELECT 1 AS expense_id, 7 AS window_days WHERE false")
    assert control.run(db) == []


def test_threshold_from_config_reaches_the_sql(db, tmp_path):
    (tmp_path / "demo.sql").write_text("SELECT 1 AS expense_id, :window_days AS window_days")
    DemoControl.sql_dir = tmp_path
    settings = load_config().controls.C1.model_copy(update={"window_days": 30})
    assert DemoControl(settings).run(db)[0].reason == "window is 30 days"





def test_severity_comes_from_the_config(tmp_path):
    assert make_demo(tmp_path, "SELECT 1").severity == "high"


def test_evidence_is_made_json_safe():
    finding = Finding(
        reason="x",
        evidence={
            "amount": Decimal("12.50"),
            "when": datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            "ids": [1, 2],
        },
    )
    assert finding.evidence == {
        "amount": "12.50",
        "when": "2026-01-05T09:00:00+00:00",
        "ids": [1, 2],
    }


def test_base_control_requires_row_mapping():
    with pytest.raises(NotImplementedError):
        Control(load_config().controls.C1).row_to_finding({})


def test_build_controls_skips_disabled_controls():
    config = load_config()
    config.controls.C2.enabled = False
    registry = {
        cid: type(cid, (Control,), {"control_id": cid})
        for cid in config.controls.by_id()
    }
    built = build_controls(config, registry)
    assert [c.control_id for c in built] == ["C1", "C3", "C4", "C5", "C6"]


def test_enabled_control_without_a_class_is_an_error():
    with pytest.raises(UnknownControlError, match="C1"):
        build_controls(load_config(), registry={})


def test_register_rejects_a_control_without_an_id():
    class NoId(Control):
        pass

    with pytest.raises(ValueError, match="no control_id"):
        register(NoId)