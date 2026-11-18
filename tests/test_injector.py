from sqlalchemy import func, select
from controls_monitor.generator import seed_clean_org
from controls_monitor.init_db import truncate_all
from controls_monitor.injector import inject_violations
from controls_monitor.models import Employee, Expense, InjectedViolation

EXPECTED = {
    # control: (real violations, decoys)
    "C1": (11, 6),
    "C2": (14, 7),
    "C3": (8, 7),
    "C4": (7, 5),
    "C5": (2, 2),
    "C6": (6, 4),
}


def plant(db, seed=42):
    seed_clean_org(db, seed)
    return inject_violations(db, seed)


def test_the_planted_cases_match_the_catalogue(db):
    summary = plant(db)
    assert {c: (v["violations"], v["decoys"]) for c, v in summary.items()} == EXPECTED

    for control_id, (violations, decoys) in EXPECTED.items():
        stored = db.execute(
            select(InjectedViolation.is_decoy, func.count())
            .where(InjectedViolation.control_id == control_id)
            .group_by(InjectedViolation.is_decoy)
        ).all()
        counts = dict(stored)
        assert counts.get(False, 0) == violations
        assert counts.get(True, 0) == decoys


def test_every_case_points_at_a_real_claim_or_employee(db):
    plant(db)
    for case in db.scalars(select(InjectedViolation)):
        if case.control_id == "C5":
            assert case.expense_id is None
            assert db.get(Employee, case.employee_id) is not None
        else:
            assert case.employee_id is None
            assert db.get(Expense, case.expense_id) is not None
        assert case.note


def test_every_case_has_a_note_and_is_unique(db):
    plant(db)
    keys = [
        (c.control_id, c.expense_id, c.employee_id)
        for c in db.scalars(select(InjectedViolation))
    ]
    assert len(keys) == len(set(keys))


def test_the_same_seed_plants_the_same_cases(db, engine):
    def snapshot():
        rows = db.execute(
            select(
                InjectedViolation.control_id,
                InjectedViolation.expense_id,
                InjectedViolation.employee_id,
                InjectedViolation.is_decoy,
                InjectedViolation.note,
            ).order_by(InjectedViolation.id)
        ).all()
        return [tuple(r) for r in rows]

    plant(db, seed=7)
    first = snapshot()
    db.close()
    truncate_all(engine)

    plant(db, seed=7)
    assert snapshot() == first


def test_injection_adds_a_small_new_team_for_the_c5_decoy(db):
    plant(db)
    names = set(db.scalars(select(Employee.full_name)))
    assert {"Ira Interim", "Tara Temp", "Uma Unit"} <= names