import pytest
from controls_monitor.config import load_config
from controls_monitor.controls import REGISTRY
from controls_monitor.generator import seed_clean_org




@pytest.mark.parametrize("control_id", sorted(REGISTRY))
def test_clean_company_produces_no_exceptions(db, control_id):
    seed_clean_org(db)
    settings = load_config().controls.by_id()[control_id]
    assert REGISTRY[control_id](settings).run(db) == []


def test_registry_contains_the_implemented_controls():
    assert {"C1", "C2", "C3"} <= set(REGISTRY)