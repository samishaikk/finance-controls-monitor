import copy
import json
import pytest
import yaml





from controls_monitor.config import (
    DEFAULT_CONFIG_PATH,
    ConfigError,
    build_config,
    load_config,
)


def default_data():
    return yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))


def changed(mutate):
    data = copy.deepcopy(default_data())
    mutate(data)
    return data


def test_default_config_loads_with_six_controls():
    config = load_config()
    assert list(config.controls.by_id()) == ["C1", "C2", "C3", "C4", "C5", "C6"]
    assert config.fail_on_severity == "high"


def test_thresholds_are_read_from_the_file():
    config = load_config()
    assert config.controls.C1.window_days == 7
    assert config.controls.C2.approval_limit == 500
    assert config.controls.C4.min_review_seconds == 120
    assert config.controls.C6.business_end_hour == 18


def test_a_threshold_can_be_changed_without_code():
    data = changed(lambda d: d["controls"]["C1"].update(window_days=30))
    assert build_config(data).controls.C1.window_days == 30


def test_snapshot_can_be_stored_as_json():
    snapshot = load_config().snapshot()
    assert json.loads(json.dumps(snapshot)) == snapshot


def test_typo_in_a_key_is_rejected():
    data = changed(lambda d: d["controls"]["C1"].update(window_day=7))
    with pytest.raises(ConfigError, match="window_day"):
        build_config(data)


def test_negative_window_is_rejected():
    data = changed(lambda d: d["controls"]["C1"].update(window_days=-1))
    with pytest.raises(ConfigError, match="controls.C1.window_days"):
        build_config(data)


def test_unknown_severity_is_rejected():
    data = changed(lambda d: d["controls"]["C3"].update(severity="urgent"))
    with pytest.raises(ConfigError, match="controls.C3.severity"):
        build_config(data)


def test_business_hours_must_start_before_they_end():
    def mutate(d):
        d["controls"]["C6"].update(business_start_hour=18, business_end_hour=9)

    with pytest.raises(ConfigError, match="before business_end_hour"):
        build_config(changed(mutate))


def test_split_claims_need_at_least_two_claims():
    data = changed(lambda d: d["controls"]["C2"].update(min_claims=1))
    with pytest.raises(ConfigError, match="min_claims"):
        build_config(data)


def test_missing_control_is_rejected():
    data = changed(lambda d: d["controls"].pop("C5"))
    with pytest.raises(ConfigError, match="controls.C5"):
        build_config(data)


def test_empty_file_is_rejected(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ConfigError, match="empty"):
        load_config(path)


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_path_can_come_from_an_environment_variable(tmp_path, monkeypatch):
    data = changed(lambda d: d["controls"]["C4"].update(min_review_seconds=45))
    path = tmp_path / "custom.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    monkeypatch.setenv("CONTROLS_CONFIG", str(path))
    assert load_config().controls.C4.min_review_seconds == 45