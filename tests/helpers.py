from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace   
from controls_monitor.models import Employee, Expense

T0 = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)  # a Monday, 10:00 UTC
UNSET = object()


def make_employee(db, name, manager=None, title="Analyst"):
    emp = Employee(
        full_name=name,
        email=f"{name.lower().replace(' ', '.')}@example.com",
        department="Sales",
        job_title=title,
        manager_id=manager.id if manager else None,
    )
    db.add(emp)
    db.commit()
    return emp


def make_org(db):
    """ceo -> (manager, other_manager); manager -> (alice, bob)."""
    ceo = make_employee(db, "Cora Ceo", title="CEO")
    manager = make_employee(db, "Mia Manager", manager=ceo, title="Manager")
    other_manager = make_employee(db, "Omar Other", manager=ceo, title="Manager")
    alice = make_employee(db, "Alice Analyst", manager=manager)
    bob = make_employee(db, "Bob Analyst", manager=manager)
    return SimpleNamespace(
        ceo=ceo, manager=manager, other_manager=other_manager, alice=alice, bob=bob
    )


def make_claim(
    db,
    employee,
    amount="100.00",
    vendor="Metro Cabs",
    receipt=None,
    submitted_at=T0,
    status="approved",
    approver_id=UNSET,
    approved_at=UNSET,
):
    """Create one claim. By default the employee's manager approves it a day later."""
    if approver_id is UNSET:
        approver_id = employee.manager_id
    if approved_at is UNSET:
        approved_at = None if status == "pending" else submitted_at + timedelta(days=1)
    claim = Expense(
        employee_id=employee.id,
        category="Travel",
        vendor=vendor,
        receipt_number=receipt,
        amount=Decimal(str(amount)),
        status=status,
        submitted_at=submitted_at,
        approver_id=approver_id,
        approved_at=approved_at,
    )
    db.add(claim)
    db.commit()
    return claim