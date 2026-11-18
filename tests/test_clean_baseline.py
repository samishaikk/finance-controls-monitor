import pytest
from controls_monitor.config import load_config
from controls_monitor.controls import REGISTRY, build_controls
from controls_monitor.generator import seed_clean_org

@pytest.mark.parametrize("control_id", sorted(REGISTRY))
def test_clean_company_produces_no_exceptions(db, control_id):
    seed_clean_org(db)
    settings = load_config().controls.by_id()[control_id]
    assert REGISTRY[control_id](settings).run(db) == []


def test_all_six_controls_are_registered():
    assert sorted(REGISTRY) == ["C1", "C2", "C3", "C4", "C5", "C6"]


def test_every_control_in_the_config_has_an_implementation():
    controls = build_controls(load_config())
    assert [c.control_id for c in controls] == ["C1", "C2", "C3", "C4", "C5", "C6"]


@pytest.mark.parametrize("seed", [7, 123, 2024])
def test_clean_company_stays_clean_for_other_seeds(db, seed):
    seed_clean_org(db, seed)
    config = load_config()
    for control_id, control_class in REGISTRY.items():
        findings = control_class(config.controls.by_id()[control_id]).run(db)
        assert findings == [], f"{control_id} flagged clean data for seed {seed}"