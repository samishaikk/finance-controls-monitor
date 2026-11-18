from datetime import timedelta
from controls_monitor.config import load_config
from controls_monitor.controls.c5_outlier_manager import OutlierManager
from tests.helpers import T0, make_claim, make_employee, make_org




SMALL = {"min_decisions": 10, "min_rate_gap_points": 10}

def run_c5(db, **overrides):
    settings = load_config().controls.C5.model_copy(update={**SMALL, **overrides})
    return OutlierManager(settings).run(db)


def make_decisions(db, submitter, approver, approved, rejected, pending=0):
    """Give `approver` a record of approved / rejected (and pending) decisions."""
    n = 0
    for status, count in (("approved", approved), ("rejected", rejected), ("pending", pending)):
        for _ in range(count):
            n += 1
            make_claim(
                db,
                submitter,
                amount=f"{10 + n}.00",
                status=status,
                approver_id=approver.id,
                submitted_at=T0 + timedelta(hours=n + 100 * approver.id),
            )


def make_approvers(db, rates):
    """One approver per entry in `rates`, each making 10 decisions (rate = approved of 10)."""
    org = make_org(db)
    people = [org.manager, org.other_manager]
    while len(people) < len(rates):
        people.append(make_employee(db, f"Extra Approver {len(people)}"))
    for person, approved in zip(people, rates):
        make_decisions(db, org.alice, person, approved=approved, rejected=10 - approved)
    return people


def test_approver_far_above_the_peer_median_is_flagged(db):
    m1, m2, m3 = make_approvers(db, [7, 7, 10])
    findings = run_c5(db)
    assert [f.employee_id for f in findings] == [m3.id]
    assert findings[0].evidence["approval_rate"] == "100.0"
    assert findings[0].evidence["peer_median"] == "70.0"
    assert findings[0].expense_id is None


def test_gap_exactly_at_the_threshold_is_flagged(db):
    m1, m2, m3 = make_approvers(db, [7, 7, 8])
    assert [f.employee_id for f in run_c5(db)] == [m3.id]


def test_gap_just_below_the_threshold_is_not_flagged(db):
    make_approvers(db, [7, 7, 8])
    assert run_c5(db, min_rate_gap_points=10.1) == []


def test_similar_approvers_are_not_flagged(db):
    make_approvers(db, [6, 7, 7])
    assert run_c5(db) == []


def test_a_low_approval_rate_is_not_flagged(db):
    make_approvers(db, [7, 7, 7, 7, 3])
    assert run_c5(db) == []


def test_approvers_with_too_few_decisions_are_ignored(db):
    org = make_org(db)
    make_decisions(db, org.alice, org.manager, approved=7, rejected=3)
    make_decisions(db, org.alice, org.other_manager, approved=7, rejected=3)
    newcomer = make_employee(db, "New Approver")
    make_decisions(db, org.alice, newcomer, approved=5, rejected=0)  # 100% but only 5 decisions
    assert run_c5(db) == []


def test_needs_at_least_two_peers(db):
    org = make_org(db)
    make_decisions(db, org.alice, org.manager, approved=10, rejected=0)
    make_decisions(db, org.alice, org.other_manager, approved=2, rejected=8)
    assert run_c5(db) == []


def test_pending_claims_do_not_count_as_decisions(db):
    org = make_org(db)
    third = make_employee(db, "Third Approver")
    make_decisions(db, org.alice, org.manager, approved=7, rejected=3)
    make_decisions(db, org.alice, org.other_manager, approved=7, rejected=3)
    make_decisions(db, org.alice, third, approved=7, rejected=3, pending=20)
    assert run_c5(db) == []


def test_minimum_decisions_comes_from_the_config(db):
    make_approvers(db, [7, 7, 10])
    assert len(run_c5(db)) == 1
    assert run_c5(db, min_decisions=11) == []


def test_finding_has_a_readable_reason(db):
    make_approvers(db, [7, 7, 10])
    assert "approved 100.0% of 10 decisions; peer median is 70.0%" in run_c5(db)[0].reason