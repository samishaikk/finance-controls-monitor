from datetime import datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from controls_monitor.models import ControlResult, ControlRun, Employee, Expense

NOW = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)


def make_employee(db, name, manager_id=None):
    emp = Employee(
        full_name=name,
        email=f"{name.lower().replace(' ', '.')}@example.com",
        department="Sales",
        job_title="Analyst",
        manager_id=manager_id,
    )
    db.add(emp)
    db.commit()
    return emp


def make_expense(db, employee_id, amount="100.00", status="pending"):
    exp = Expense(
        employee_id=employee_id,
        category="Travel",
        vendor="Acme Cabs",
        amount=Decimal(amount),
        status=status,
        submitted_at=NOW,
    )
    db.add(exp)
    db.commit()
    return exp


def test_all_tables_exist(engine):
    expected = {
        "employees",
        "expenses",
        "audit_log",
        "injected_violations",
        "control_runs",
        "control_results",
        "control_exceptions",
    }
    assert expected <= set(inspect(engine).get_table_names())


def test_employee_can_have_a_manager(db):
    boss = make_employee(db, "Asha Rao")
    emp = make_employee(db, "Ravi Kumar", manager_id=boss.id)
    assert emp.manager_id == boss.id


def test_expense_amount_must_be_positive(db):
    emp = make_employee(db, "Ravi Kumar")
    with pytest.raises(IntegrityError):
        make_expense(db, emp.id, amount="0")
    db.rollback()


def test_expense_status_must_be_valid(db):
    emp = make_employee(db, "Ravi Kumar")
    with pytest.raises(IntegrityError):
        make_expense(db, emp.id, status="maybe")
    db.rollback()


def test_deleting_a_run_deletes_its_results(db):
    run = ControlRun(status="success")
    db.add(run)
    db.commit()
    db.add(
        ControlResult(
            run_id=run.id,
            control_id="C1",
            control_name="Duplicate claims",
            severity="high",
            status="passed",
        )
    )
    db.commit()

    db.delete(run)
    db.commit()

    remaining = db.scalar(select(func.count()).select_from(ControlResult))
    assert remaining == 0