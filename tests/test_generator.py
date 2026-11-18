import hashlib
from collections import defaultdict
from sqlalchemy import select

from controls_monitor.generator import seed_clean_org
from controls_monitor.init_db import truncate_all
from controls_monitor.models import AuditLog, Employee, Expense


def fingerprint(db):
    
    """One hash that changes if any employee or expense value changes."""
    
    h = hashlib.sha256()
    for e in db.scalars(select(Employee).order_by(Employee.id)):
        h.update(f"{e.id}|{e.email}|{e.manager_id}".encode())
    for x in db.scalars(select(Expense).order_by(Expense.id)):
        h.update(
            f"{x.id}|{x.employee_id}|{x.vendor}|{x.amount}|{x.status}|"
            f"{x.submitted_at.isoformat()}|{x.approved_at.isoformat()}".encode()
        )
    return h.hexdigest()


def test_organisation_shape(db):
    summary = seed_clean_org(db)
    employees = db.scalars(select(Employee)).all()
    assert summary["employees"] == len(employees) == 46
    assert len([e for e in employees if e.manager_id is None]) == 1
    assert summary["expenses"] > 300


def test_same_seed_gives_identical_data(db, engine):
    seed_clean_org(db, seed=7)
    first = fingerprint(db)
    db.close()
    truncate_all(engine)

    seed_clean_org(db, seed=7)
    assert fingerprint(db) == first


def test_different_seed_gives_different_data(db, engine):
    seed_clean_org(db, seed=1)
    first = fingerprint(db)
    db.close()
    truncate_all(engine)

    seed_clean_org(db, seed=2)
    assert fingerprint(db) != first


def test_every_claim_is_approved_by_the_submitters_manager(db):
    seed_clean_org(db)
    managers = {e.id: e.manager_id for e in db.scalars(select(Employee))}
    for x in db.scalars(select(Expense)):
        assert x.approver_id == managers[x.employee_id]
        assert x.approver_id != x.employee_id
        assert x.status in ("approved", "rejected")


def test_no_duplicate_receipts_or_repeat_claims(db):
    seed_clean_org(db)
    receipts = set()
    combos = set()
    for x in db.scalars(select(Expense)):
        assert x.receipt_number not in receipts
        receipts.add(x.receipt_number)
        key = (x.employee_id, x.vendor, x.amount)
        assert key not in combos
        combos.add(key)


def test_claims_stay_under_the_approval_limit(db):
    seed_clean_org(db)
    assert max(x.amount for x in db.scalars(select(Expense))) < 500


def test_claims_from_one_person_are_at_least_two_days_apart(db):
    seed_clean_org(db)
    by_employee = defaultdict(list)
    for x in db.scalars(select(Expense).order_by(Expense.submitted_at)):
        by_employee[x.employee_id].append(x.submitted_at)
    for times in by_employee.values():
        for earlier, later in zip(times, times[1:]):
            assert (later - earlier).days >= 2


def test_decisions_are_in_office_hours_and_not_instant(db):
    seed_clean_org(db)
    for x in db.scalars(select(Expense)):
        assert x.submitted_at.weekday() < 5
        assert 9 <= x.submitted_at.hour < 18
        assert x.approved_at.weekday() < 5
        assert 9 <= x.approved_at.hour < 18
        assert (x.approved_at - x.submitted_at).total_seconds() >= 3600


def test_audit_log_has_a_submit_and_a_decision_for_each_claim(db):
    summary = seed_clean_org(db)
    rows = db.scalars(select(AuditLog)).all()
    assert len(rows) == summary["audit_rows"]
    actions = defaultdict(list)
    for r in rows:
        actions[r.expense_id].append(r.action)
    for acts in actions.values():
        assert sorted(acts) in (["approved", "submitted"], ["rejected", "submitted"])