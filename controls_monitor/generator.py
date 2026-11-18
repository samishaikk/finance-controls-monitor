import argparse
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import product

from sqlalchemy import func, select

from controls_monitor.db import make_engine, make_session_factory
from controls_monitor.init_db import create_tables, drop_tables
from controls_monitor.models import AuditLog, Employee, Expense

BASE_MONDAY = datetime(2026, 1, 5, tzinfo=timezone.utc)
WEEKS = 12
DEPARTMENTS = ["Sales", "Engineering", "Marketing", "Finance", "Support"]
EMPLOYEES_PER_MANAGER = 8
REJECT_RATE = 0.30

FIRST_NAMES = [
    "Asha", "Ravi", "Meera", "Karan", "Divya", "Arjun",
    "Sneha", "Rohan", "Priya", "Vikram", "Nisha", "Aditya",
]
LAST_NAMES = [
    "Rao", "Kumar", "Nair", "Singh", "Iyer", "Reddy",
    "Sharma", "Menon", "Patel", "Das", "Joshi", "Khan",
]

# category -> (vendors, min amount, max amount); all stay under the 500 approval limit
EXPENSE_TYPES = {
    "Travel": (["Metro Cabs", "SkyJet Airways", "CityRail"], 30, 450),
    "Meals": (["Green Bowl Cafe", "Urban Kitchen", "Spice Route"], 12, 95),
    "Software": (["CloudDesk", "CodeNest"], 15, 300),
    "Lodging": (["Harbor Inn", "Stay Plus"], 90, 480),
    "Office": (["PaperTrail Supplies", "DeskWorks"], 8, 150),
    "Training": (["SkillBridge Academy"], 50, 490),
}


def to_business_time(moment, rng):
    """Push a time forward to the next Mon-Fri, 09:00-17:59 UTC slot."""
    while True:
        if moment.weekday() >= 5:  # Saturday or Sunday -> Monday morning
            moment = moment + timedelta(days=7 - moment.weekday())
            moment = moment.replace(
                hour=9, minute=rng.randint(0, 59), second=rng.randint(0, 59)
            )
        elif moment.hour < 9:
            moment = moment.replace(
                hour=9, minute=rng.randint(0, 59), second=rng.randint(0, 59)
            )
        elif moment.hour >= 18:
            moment = (moment + timedelta(days=1)).replace(
                hour=9, minute=rng.randint(0, 59), second=rng.randint(0, 59)
            )
        else:
            return moment


def make_employees(session, rng):
    names = list(product(FIRST_NAMES, LAST_NAMES))
    rng.shuffle(names)

    def new_employee(department, job_title, manager_id):
        first, last = names.pop()
        emp = Employee(
            full_name=f"{first} {last}",
            email=f"{first}.{last}@example.com".lower(),
            department=department,
            job_title=job_title,
            manager_id=manager_id,
        )
        session.add(emp)
        session.flush()  # gives the row its id
        return emp

    ceo = new_employee("Executive", "CEO", None)
    employees = [ceo]
    for department in DEPARTMENTS:
        manager = new_employee(department, "Manager", ceo.id)
        employees.append(manager)
        for _ in range(EMPLOYEES_PER_MANAGER):
            employees.append(new_employee(department, "Analyst", manager.id))
    return employees


def make_expenses(session, rng, employees, receipt_prefix="RC"):
    expenses = []
    seen = set()  # (employee_id, vendor, amount) must never repeat
    receipt_counter = 0

    for emp in employees:
        if emp.manager_id is None:  # the CEO does not submit claims
            continue
        weeks = sorted(rng.sample(range(WEEKS), rng.randint(8, 12)))
        for week in weeks:
            # one claim per chosen week, on a weekday, in office hours
            submitted = BASE_MONDAY + timedelta(
                weeks=week,
                days=rng.randint(0, 4),
                hours=rng.randint(9, 16),
                minutes=rng.randint(0, 59),
                seconds=rng.randint(0, 59),
            )
            category = rng.choice(list(EXPENSE_TYPES))
            vendors, low, high = EXPENSE_TYPES[category]
            vendor = rng.choice(vendors)
            while True:
                amount = Decimal(str(round(rng.uniform(low, high), 2)))
                if (emp.id, vendor, amount) not in seen:
                    seen.add((emp.id, vendor, amount))
                    break

            receipt_counter += 1
            decided = to_business_time(
                submitted + timedelta(hours=rng.uniform(1, 72)), rng
            )
            expense = Expense(
                employee_id=emp.id,
                category=category,
                vendor=vendor,
                receipt_number=f"{receipt_prefix}-{receipt_counter:06d}",
                amount=amount,
                currency="USD",
                description=f"{category} - {vendor}",
                status="rejected" if rng.random() < REJECT_RATE else "approved",
                submitted_at=submitted,
                approver_id=emp.manager_id,  # clean data: the manager approves
                approved_at=decided,
            )
            session.add(expense)
            expenses.append(expense)

    session.flush()
    return expenses


def make_audit_log(session, expenses):
    for exp in expenses:
        session.add(
            AuditLog(
                expense_id=exp.id,
                actor_id=exp.employee_id,
                action="submitted",
                created_at=exp.submitted_at,
            )
        )
        session.add(
            AuditLog(
                expense_id=exp.id,
                actor_id=exp.approver_id,
                action=exp.status,  # "approved" or "rejected"
                created_at=exp.approved_at,
            )
        )
    session.flush()


def seed_clean_org(session, seed=42):
    rng = random.Random(seed)
    employees = make_employees(session, rng)
    expenses = make_expenses(session, rng, employees)
    make_audit_log(session, expenses)
    session.commit()
    return {
        "employees": len(employees),
        "expenses": len(expenses),
        "audit_rows": len(expenses) * 2,
    }


def main():
    parser = argparse.ArgumentParser(description="seed controls_db with a company")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reset", action="store_true", help="wipe all tables first")
    parser.add_argument(
        "--with-violations",
        action="store_true",
        help="also plant known violations and decoys (see injector.py)",
    )
    args = parser.parse_args()

    engine = make_engine()
    if args.reset:
        drop_tables(engine)
    create_tables(engine)

    with make_session_factory(engine)() as session:
        if session.scalar(select(func.count()).select_from(Employee)):
            raise SystemExit("database already has data - run again with --reset")
        summary = seed_clean_org(session, args.seed)
        planted = None
        if args.with_violations:
            from controls_monitor.injector import inject_violations

            planted = inject_violations(session, args.seed)
    print(
        f"seeded {summary['employees']} employees, "
        f"{summary['expenses']} expenses, {summary['audit_rows']} audit rows"
    )
    if planted:
        for control_id, counts in planted.items():
            print(
                f"  planted {control_id}: {counts['violations']} violations, "
                f"{counts['decoys']} decoys"
            )


if __name__ == "__main__":
    main()