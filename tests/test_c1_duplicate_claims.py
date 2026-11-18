from datetime import timedelta

from controls_monitor.config import load_config
from controls_monitor.controls.c1_duplicate_claims import DuplicateClaims
from tests.helpers import T0, make_claim, make_org


def run_c1(db, **overrides):
    settings = load_config().controls.C1.model_copy(update=overrides)
    return DuplicateClaims(settings).run(db)


def test_same_employee_vendor_amount_is_flagged_on_the_later_claim(db):
    org = make_org(db)
    first = make_claim(db, org.alice, amount="45.50")
    second = make_claim(db, org.alice, amount="45.50", submitted_at=T0 + timedelta(days=2))

    findings = run_c1(db)

    assert [f.expense_id for f in findings] == [second.id]
    assert findings[0].evidence["original_expense_id"] == first.id
    assert findings[0].evidence["match_type"] == "same_employee_vendor_amount"


def test_exactly_at_the_window_is_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="45.50")
    make_claim(db, org.alice, amount="45.50", submitted_at=T0 + timedelta(days=7))
    assert len(run_c1(db)) == 1


def test_one_second_past_the_window_is_not_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="45.50")
    make_claim(
        db, org.alice, amount="45.50", submitted_at=T0 + timedelta(days=7, seconds=1)
    )
    assert run_c1(db) == []


def test_window_comes_from_the_config(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="45.50")
    make_claim(db, org.alice, amount="45.50", submitted_at=T0 + timedelta(days=20))
    assert run_c1(db) == []
    assert len(run_c1(db, window_days=30)) == 1


def test_a_one_cent_difference_is_not_a_duplicate(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="45.50")
    make_claim(db, org.alice, amount="45.51", submitted_at=T0 + timedelta(days=1))
    assert run_c1(db) == []


def test_different_vendor_is_not_a_duplicate(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="45.50", vendor="Metro Cabs")
    make_claim(
        db, org.alice, amount="45.50", vendor="City Rail", submitted_at=T0 + timedelta(days=1)
    )
    assert run_c1(db) == []


def test_same_amount_and_vendor_by_different_people_is_not_a_duplicate(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="45.50")
    make_claim(db, org.bob, amount="45.50", submitted_at=T0 + timedelta(days=1))
    assert run_c1(db) == []


def test_same_receipt_number_is_flagged_even_for_different_people_and_dates(db):
    org = make_org(db)
    first = make_claim(db, org.alice, amount="45.50", receipt="RC-1")
    second = make_claim(
        db,
        org.bob,
        amount="99.00",
        vendor="Other Vendor",
        receipt="RC-1",
        submitted_at=T0 + timedelta(days=90),
    )
    findings = run_c1(db)
    assert [f.expense_id for f in findings] == [second.id]
    assert findings[0].evidence["original_expense_id"] == first.id
    assert findings[0].evidence["match_type"] == "same_receipt"


def test_missing_receipt_numbers_do_not_match_each_other(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="10.00", vendor="A", receipt=None)
    make_claim(db, org.bob, amount="20.00", vendor="B", receipt=None, submitted_at=T0 + timedelta(days=1))
    assert run_c1(db) == []


def test_resubmitting_after_a_rejection_is_not_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="45.50", status="rejected")
    make_claim(db, org.alice, amount="45.50", submitted_at=T0 + timedelta(days=1))
    assert run_c1(db) == []


def test_a_duplicate_that_was_rejected_is_not_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="45.50")
    make_claim(
        db, org.alice, amount="45.50", status="rejected", submitted_at=T0 + timedelta(days=1)
    )
    assert run_c1(db) == []


def test_three_identical_claims_flag_two_and_point_to_the_first(db):
    org = make_org(db)
    first = make_claim(db, org.alice, amount="45.50")
    second = make_claim(db, org.alice, amount="45.50", submitted_at=T0 + timedelta(days=1))
    third = make_claim(db, org.alice, amount="45.50", submitted_at=T0 + timedelta(days=2))

    findings = run_c1(db)

    assert [f.expense_id for f in findings] == [second.id, third.id]
    assert {f.evidence["original_expense_id"] for f in findings} == {first.id}


def test_finding_has_a_readable_reason_and_json_safe_evidence(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="45.50")
    make_claim(db, org.alice, amount="45.50", submitted_at=T0 + timedelta(days=1))
    finding = run_c1(db)[0]
    assert "has the same employee, vendor and amount as earlier claim" in finding.reason
    assert finding.evidence["amount"] == "45.50"