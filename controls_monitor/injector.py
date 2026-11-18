import random
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select, update

from controls_monitor.generator import (
    BASE_MONDAY,
    EXPENSE_TYPES,
    WEEKS,
    make_audit_log,
    make_expenses,
    to_business_time,
)
from controls_monitor.models import (
    AuditLog,
    Employee,
    Expense,
    InjectedViolation,
)

WINDOW_END = BASE_MONDAY + timedelta(weeks=WEEKS)
ALL_VENDORS = [v for vendors, _, _ in EXPENSE_TYPES.values() for v in vendors]


RATE_RUBBER_STAMP = 100  # caught
RATE_BELOW_GAP = 84  # high, but under the gap threshold -> missed
RATE_LEGIT_HIGH = 98  # legitimately high (small senior team) -> flagged anyway
RATES_NORMAL = (68, 70)
RATE_CEO = 72


class Injector:
    def __init__(self, session, rng):
        self.s = session
        self.rng = rng
        employees = list(session.scalars(select(Employee).order_by(Employee.id)))
        self.ceo = next(e for e in employees if e.manager_id is None)
        self.managers = [e for e in employees if e.manager_id == self.ceo.id]
        manager_ids = {m.id for m in self.managers}
        self.staff = [e for e in employees if e.manager_id in manager_ids]
        self.first_three_teams = [
            e for e in self.staff if e.manager_id in {m.id for m in self.managers[:3]}
        ]
        self.other_approvers = self.managers[3:5]  # "someone else" in the C3 cases
        self.times = defaultdict(list)
        self.amounts = set()
        for x in session.scalars(select(Expense)):
            self.times[x.employee_id].append(x.submitted_at)
            self.amounts.add(x.amount)
        self.counter = 0
        self.summary = defaultdict(lambda: {"violations": 0, "decoys": 0})

    # ---------- helpers ----------

    def new_amount(self, low, high):
        while True:
            amount = Decimal(str(round(self.rng.uniform(low, high), 2)))
            if amount not in self.amounts:
                self.amounts.add(amount)
                return amount

    def amounts_for_group(self, total_low, total_high, count):
        """`count` distinct unused amounts adding up to roughly a random total."""
        while True:
            total = self.rng.uniform(total_low, total_high)
            weights = [self.rng.uniform(0.8, 1.2) for _ in range(count)]
            parts = [Decimal(str(round(total * w / sum(weights), 2))) for w in weights]
            if len(set(parts)) == count and not any(p in self.amounts for p in parts):
                self.amounts.update(parts)
                return parts

    def random_time(self, lo, hi, weekdays=(0, 1, 2, 3, 4), hours=(9, 15)):
        span = int((hi - lo).total_seconds())
        for _ in range(5000):
            t = lo + timedelta(seconds=self.rng.randrange(span))
            t = t.replace(
                hour=self.rng.randint(*hours),
                minute=self.rng.randint(0, 59),
                second=self.rng.randint(0, 59),
            )
            if t.weekday() in weekdays and lo <= t <= hi:
                return t
        raise RuntimeError("no time slot found")

    def free_time(self, employee, gap_hours=26, lo=None, hi=None, **kwargs):
        """A business-hours time at least gap_hours away from all of the employee's claims."""
        lo = lo or BASE_MONDAY
        hi = hi or WINDOW_END - timedelta(days=2)
        gap = timedelta(hours=gap_hours)
        for _ in range(3000):
            t = self.random_time(lo, hi, **kwargs)
            if all(abs(t - u) >= gap for u in self.times[employee.id]):
                return t
        raise RuntimeError(f"no free slot for employee {employee.id}")

    def shuffled_staff(self, pool=None):
        pool = self.staff if pool is None else pool
        return iter(self.rng.sample(pool, len(pool)))

    def claims_of(self, employee, status, before_week=9):
        limit = BASE_MONDAY + timedelta(weeks=before_week)
        rows = self.s.scalars(
            select(Expense).where(Expense.employee_id == employee.id).order_by(Expense.id)
        )
        return [x for x in rows if x.status == status and x.submitted_at < limit]

    def add_claim(
        self,
        employee,
        amount,
        submitted,
        *,
        vendor=None,
        category=None,
        status="approved",
        approver="manager",
        approved_at=None,
        receipt=None,
    ):
        if category is None:
            category = self.rng.choice(list(EXPENSE_TYPES))
        if vendor is None:
            vendor = self.rng.choice(EXPENSE_TYPES[category][0])
        if approver == "manager":
            approver_id = employee.manager_id
        elif approver is None:
            approver_id = None
        else:
            approver_id = approver.id
        if status == "pending":
            approver_id, approved_at = None, None
        elif approved_at is None:
            approved_at = to_business_time(
                submitted + timedelta(hours=self.rng.uniform(2, 30)), self.rng
            )
        self.counter += 1
        claim = Expense(
            employee_id=employee.id,
            category=category,
            vendor=vendor,
            receipt_number=receipt or f"IV-{self.counter:06d}",
            amount=amount,
            currency="USD",
            description=f"{category} - {vendor}",
            status=status,
            submitted_at=submitted,
            approver_id=approver_id,
            approved_at=approved_at,
        )
        self.s.add(claim)
        self.s.flush()
        self.times[employee.id].append(submitted)
        self.s.add(
            AuditLog(expense_id=claim.id, actor_id=employee.id, action="submitted", created_at=submitted)
        )
        if approver_id is not None:
            self.s.add(
                AuditLog(expense_id=claim.id, actor_id=approver_id, action=status, created_at=approved_at)
            )
        return claim

    def record(self, control_id, note, *, claim=None, employee=None, decoy=False):
        self.s.add(
            InjectedViolation(
                control_id=control_id,
                expense_id=claim.id if claim else None,
                employee_id=employee.id if employee else None,
                note=note,
                is_decoy=decoy,
            )
        )
        self.summary[control_id]["decoys" if decoy else "violations"] += 1

    # ---------- C5: approver approval rates ----------

    def set_approval_rate(self, approver, target_pct):
        decided = list(
            self.s.scalars(
                select(Expense)
                .where(Expense.approver_id == approver.id, Expense.status.in_(["approved", "rejected"]))
                .order_by(Expense.id)
            )
        )
        wanted = round(len(decided) * target_pct / 100)
        approved = [x for x in decided if x.status == "approved"]
        rejected = [x for x in decided if x.status == "rejected"]
        if len(approved) < wanted:
            flips, new_status = rejected[: wanted - len(approved)], "approved"
        else:
            flips, new_status = approved[wanted:], "rejected"
        for x in flips:
            x.status = new_status
            self.s.execute(
                update(AuditLog)
                .where(AuditLog.expense_id == x.id, AuditLog.action.in_(["approved", "rejected"]))
                .values(action=new_status)
            )
        self.s.flush()

    def inject_c5(self):
        m1, m2, m3, m4, m5 = self.managers[:5]
        for manager, rate in (
            (m1, RATE_RUBBER_STAMP),
            (m2, RATE_BELOW_GAP),
            (m3, RATE_LEGIT_HIGH),
            (m4, RATES_NORMAL[0]),
            (m5, RATES_NORMAL[1]),
            (self.ceo, RATE_CEO),
        ):
            self.set_approval_rate(manager, rate)
        self.record("C5", "rubber-stamp approver: approves everything", employee=m1)
        self.record("C5", "high approval rate but under the gap threshold (a miss)", employee=m2)
        self.record(
            "C5",
            "legitimately high approval rate (small senior team) - flagged anyway",
            employee=m3,
            decoy=True,
        )

        # a brand-new approver with a perfect record, but too few decisions to judge
        interim = Employee(
            full_name="Ira Interim",
            email="ira.interim@example.com",
            department="Special Projects",
            job_title="Manager",
            manager_id=self.ceo.id,
        )
        self.s.add(interim)
        self.s.flush()
        team = []
        for first, last in (("Tara", "Temp"), ("Uma", "Unit")):
            emp = Employee(
                full_name=f"{first} {last}",
                email=f"{first}.{last}@example.com".lower(),
                department="Special Projects",
                job_title="Analyst",
                manager_id=interim.id,
            )
            self.s.add(emp)
            team.append(emp)
        self.s.flush()
        claims = make_expenses(self.s, self.rng, team, receipt_prefix="SP")
        for x in claims:
            x.status = "approved"
        self.s.flush()
        make_audit_log(self.s, claims)
        self.amounts.update(x.amount for x in claims)
        self.record(
            "C5",
            f"new approver with 100% approvals but only {len(claims)} decisions - too few to judge",
            employee=interim,
            decoy=True,
        )

    # ---------- C1: duplicate claims ----------

    def inject_c1(self):
        used = set()

        def place(min_hours, max_hours, status="approved"):
            """Find an employee with an original claim and a free time slot after it."""
            for emp in self.rng.sample(self.staff, len(self.staff)):
                if emp.id in used:
                    continue
                options = self.claims_of(emp, status)
                if not options:
                    continue
                original = self.rng.choice(options)
                try:
                    t = self.free_time(
                        emp,
                        lo=original.submitted_at + timedelta(hours=min_hours),
                        hi=original.submitted_at + timedelta(hours=max_hours),
                    )
                except RuntimeError:
                    continue
                used.add(emp.id)
                return emp, original, t
            raise RuntimeError("could not place a C1 case")

        def repeat(emp, original, t, **changes):
            return self.add_claim(
                emp,
                changes.pop("amount", original.amount),
                t,
                vendor=changes.pop("vendor", original.vendor),
                category=original.category,
            )

        for _ in range(6):  # exact duplicates: caught
            emp, original, t = place(27, 6 * 24)
            self.record("C1", "same employee, vendor and amount resubmitted", claim=repeat(emp, original, t))

        for _ in range(2):  # a receipt reused by a colleague: caught
            colleague, original, _t = place(24, 24 * 2)
            emp = self.rng.choice([e for e in self.staff if e.id != colleague.id])
            t = self.free_time(emp, lo=original.submitted_at + timedelta(days=1), hi=WINDOW_END - timedelta(days=2))
            dup = self.add_claim(emp, self.new_amount(20, 200), t, receipt=original.receipt_number)
            self.record("C1", f"receipt {original.receipt_number} reused by a different employee", claim=dup)

        for kind in ("amount", "vendor", "amount"):  # near-duplicates the exact rule cannot see: missed
            emp, original, t = place(27, 5 * 24)
            if kind == "amount":
                dup = repeat(emp, original, t, amount=original.amount + Decimal("0.01"))
                note = "duplicate with the amount off by 1 cent (a miss)"
            else:
                dup = repeat(emp, original, t, vendor=original.vendor + " Ltd")
                note = "duplicate with the vendor name spelled differently (a miss)"
            self.amounts.add(dup.amount)
            self.record("C1", note, claim=dup)

        for _ in range(2):  # same claim 8+ days later: not flagged
            emp, original, t = place(8 * 24 + 1, 10 * 24)
            self.record(
                "C1", "same claim 8+ days later - outside the 7-day window",
                claim=repeat(emp, original, t), decoy=True,
            )

        for _ in range(2):  # resubmitted after a rejection: not flagged
            emp, original, t = place(27, 5 * 24, status="rejected")
            self.record(
                "C1", "resubmitted after the first claim was rejected",
                claim=repeat(emp, original, t), decoy=True,
            )

        for _ in range(2):  # two genuine identical trips: flagged anyway
            emp, original, t = place(27, 4 * 24)
            self.record(
                "C1", "two genuine identical trips - looks exactly like a duplicate (flagged anyway)",
                claim=repeat(emp, original, t), decoy=True,
            )

    # ---------- C2: split claims ----------

    def inject_c2(self):
        people = self.shuffled_staff()

        def group(parts, offsets, note, decoy=False, weekdays=(0, 1, 2, 3, 4), vendors=None, category=None):
            emp = next(people)
            t0 = self.free_time(emp, gap_hours=26 + max(offsets), hours=(9, 10), weekdays=weekdays)
            vendors = vendors or self.rng.sample(ALL_VENDORS, len(parts))
            for amount, offset, vendor in zip(parts, offsets, vendors):
                claim = self.add_claim(
                    emp, amount, t0 + timedelta(hours=offset), vendor=vendor, category=category
                )
                self.record("C2", note, claim=claim, decoy=decoy)

        for count in (2, 2, 3, 3):  # splits inside 24 hours: caught
            group(
                self.amounts_for_group(540, 800, count), [0, 2, 4][:count],
                "one purchase split into small claims inside 24 hours",
            )
        for _ in range(2):  # splits 30 hours apart: missed
            group(
                self.amounts_for_group(540, 700, 2), [0, 30],
                "split claims 30 hours apart - outside the window (a miss)", weekdays=(0, 1, 2, 3),
            )
        for _ in range(2):  # two same-day claims under the limit: not flagged
            group(
                self.amounts_for_group(400, 480, 2), [0, 3],
                "two same-day claims totalling under the limit", decoy=True,
            )
        emp = next(people)
        single = self.add_claim(
            emp, Decimal("499.99"), self.free_time(emp), vendor="Harbor Inn", category="Lodging"
        )
        self.amounts.add(single.amount)
        self.record("C2", "a single claim just under the limit", claim=single, decoy=True)

        group(  # two genuine hotel charges: flagged anyway
            self.amounts_for_group(530, 560, 2), [0, 6],
            "two genuine conference hotel charges (flagged anyway)", decoy=True,
            vendors=["Harbor Inn", "Stay Plus"], category="Lodging",
        )

    # ---------- C3: wrong approver ----------

    def inject_c3(self):
        people = self.shuffled_staff()
        team_members = self.shuffled_staff(self.first_three_teams)

        def claim_for(emp, approver, status="approved"):
            return self.add_claim(
                emp, self.new_amount(20, 300), self.free_time(emp), approver=approver, status=status
            )

        for _ in range(3):
            emp = next(people)
            self.record("C3", "employee approved their own claim", claim=claim_for(emp, emp))
        for i in range(3):
            emp = next(team_members)
            self.record(
                "C3", "approved by an unrelated manager",
                claim=claim_for(emp, self.other_approvers[i % 2]),
            )
        for _ in range(2):
            emp = next(people)
            self.record("C3", "approved with no approver recorded", claim=claim_for(emp, None))

        for _ in range(3):
            emp = next(people)
            self.record(
                "C3", "approved by the manager's manager (allowed)",
                claim=claim_for(emp, self.ceo), decoy=True,
            )
        for _ in range(2):
            emp = next(people)
            self.record(
                "C3", "claim still pending, no approver yet",
                claim=claim_for(emp, None, "pending"), decoy=True,
            )
        for i in range(2):
            emp = next(team_members)
            self.record(
                "C3", "legitimate delegate approved while the manager was on leave (flagged anyway)",
                claim=claim_for(emp, self.other_approvers[i % 2]), decoy=True,
            )

    # ---------- C4: approvals too fast ----------

    def inject_c4(self):
        people = self.shuffled_staff()

        def fast(seconds, amount_range=(20, 300), category=None):
            emp = next(people)
            t = self.free_time(emp)
            return self.add_claim(
                emp, self.new_amount(*amount_range), t,
                approved_at=t + timedelta(seconds=seconds), category=category,
            )

        for seconds in (5, 20, 45, 60, 90):
            self.record("C4", f"approved {seconds} seconds after submission", claim=fast(seconds))
        for seconds in (130, 170):
            self.record(
                "C4", f"rubber-stamp approval after {seconds} seconds - over the 120 s limit (a miss)",
                claim=fast(seconds),
            )
        for seconds, note in (
            (120, "approved after exactly 120 seconds (the limit)"),
            (125, "approved after 125 seconds"),
            (600, "approved after 10 minutes"),
        ):
            self.record("C4", note, claim=fast(seconds), decoy=True)
        for seconds in (3, 8):
            self.record(
                "C4", "tiny claim auto-approved by policy within seconds (flagged anyway)",
                claim=fast(seconds, amount_range=(5, 19), category="Office"), decoy=True,
            )

    # ---------- C6: off-hours approvals ----------

    def inject_c6(self):
        people = self.shuffled_staff()

        def weekend_claim(days_after_friday, hour):
            emp = next(people)
            t = self.free_time(emp, hours=(13, 15), weekdays=(4,))  # a Friday afternoon
            approved = (t + timedelta(days=days_after_friday)).replace(
                hour=hour, minute=self.rng.randint(0, 59), second=0
            )
            return self.add_claim(emp, self.new_amount(20, 300), t, approved_at=approved)

        def same_day_claim(hour, minute, second):
            emp = next(people)
            t = self.free_time(emp, hours=(9, 10))
            approved = t.replace(hour=hour, minute=minute, second=second)
            return self.add_claim(emp, self.new_amount(20, 300), t, approved_at=approved)

        self.record("C6", "approved on a Saturday", claim=weekend_claim(1, 10))
        self.record("C6", "approved on a Sunday", claim=weekend_claim(2, 11))
        self.record("C6", "approved on a Saturday", claim=weekend_claim(1, 14))
        for hour, minute in ((22, 5), (23, 40), (20, 15)):
            self.record(
                "C6", f"approved late evening at {hour:02d}:{minute:02d} UTC",
                claim=same_day_claim(hour, minute, 0),
            )

        self.record(
            "C6", "approved at 17:59:59 - the last allowed second",
            claim=same_day_claim(17, 59, 59), decoy=True,
        )
        emp = next(people)
        t = self.free_time(emp, hours=(14, 15))
        approved = (t + timedelta(days=1)).replace(hour=9, minute=0, second=0)
        if approved.weekday() > 4:  
            approved += timedelta(days=7 - approved.weekday())
        self.record(
            "C6", "approved at exactly 09:00:00 - the first allowed second",
            claim=self.add_claim(emp, self.new_amount(20, 300), t, approved_at=approved), decoy=True,
        )

        emp = next(people)
        t = self.free_time(emp, hours=(14, 15), weekdays=(0, 1, 2, 3))
        approved = (t + timedelta(days=1)).replace(hour=4, minute=0, second=0)
        self.record(
            "C6", "approved at 09:30 India time (04:00 UTC) by an overseas office (flagged anyway)",
            claim=self.add_claim(emp, self.new_amount(20, 300), t, approved_at=approved), decoy=True,
        )
        self.record(
            "C6", "quarter-end close approved on a Saturday (flagged anyway)",
            claim=weekend_claim(1, 12), decoy=True,
        )


def inject_violations(session, seed=42):
    rng = random.Random(f"inject-{seed}")
    injector = Injector(session, rng)
    injector.inject_c5()  
    injector.inject_c1()
    injector.inject_c2()
    injector.inject_c3()
    injector.inject_c4()
    injector.inject_c6()
    session.commit()
    return {k: dict(v) for k, v in sorted(injector.summary.items())}