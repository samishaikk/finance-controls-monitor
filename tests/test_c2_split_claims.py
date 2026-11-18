from datetime import timedelta

from controls_monitor.config import load_config
from controls_monitor.controls.c2_split_claims import SplitClaims
from tests.helpers import T0, make_claim, make_org


def run_c2(db, **overrides):
    settings = load_config().controls.C2.model_copy(update=overrides)
    return SplitClaims(settings).run(db)


def test_two_claims_in_a_short_window_that_reach_the_limit_are_both_flagged(db):
    org = make_org(db)
    a = make_claim(db, org.alice, amount="300", vendor="V1")
    b = make_claim(db, org.alice, amount="300", vendor="V2", submitted_at=T0 + timedelta(hours=2))

    findings = run_c2(db)

    assert [f.expense_id for f in findings] == [a.id, b.id]
    assert findings[0].evidence["total"] == "600.00"
    assert findings[0].evidence["claim_ids"] == [a.id, b.id]


def test_total_exactly_equal_to_the_limit_is_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="250")
    make_claim(db, org.alice, amount="250", submitted_at=T0 + timedelta(hours=1))
    assert len(run_c2(db)) == 2


def test_total_one_cent_below_the_limit_is_not_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="249.99")
    make_claim(db, org.alice, amount="250", submitted_at=T0 + timedelta(hours=1))
    assert run_c2(db) == []


def test_claims_exactly_one_window_apart_are_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="300")
    make_claim(db, org.alice, amount="300", submitted_at=T0 + timedelta(hours=24))
    assert len(run_c2(db)) == 2


def test_claims_one_second_outside_the_window_are_not_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="300")
    make_claim(db, org.alice, amount="300", submitted_at=T0 + timedelta(hours=24, seconds=1))
    assert run_c2(db) == []


def test_three_small_claims_are_all_flagged_once(db):
    org = make_org(db)
    ids = [
        make_claim(db, org.alice, amount=amt, submitted_at=T0 + timedelta(hours=h)).id
        for amt, h in [("200", 0), ("200", 3), ("150", 6)]
    ]
    findings = run_c2(db)
    assert [f.expense_id for f in findings] == ids
    assert findings[0].evidence["claim_count"] == 3


def test_one_claim_just_under_the_limit_is_not_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="499.99")
    assert run_c2(db) == []


def test_a_single_large_claim_is_not_a_split(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="600")
    assert run_c2(db) == []


def test_a_claim_at_the_limit_is_not_part_of_a_split(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="500")
    make_claim(db, org.alice, amount="100", submitted_at=T0 + timedelta(hours=1))
    assert run_c2(db) == []


def test_claims_spread_over_several_days_are_not_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="300")
    make_claim(db, org.alice, amount="300", submitted_at=T0 + timedelta(days=3))
    assert run_c2(db) == []


def test_claims_by_different_people_are_not_added_together(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="300")
    make_claim(db, org.bob, amount="300", submitted_at=T0 + timedelta(hours=1))
    assert run_c2(db) == []


def test_rejected_claims_do_not_count(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="300")
    make_claim(db, org.alice, amount="300", status="rejected", submitted_at=T0 + timedelta(hours=1))
    assert run_c2(db) == []


def test_minimum_number_of_claims_comes_from_the_config(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="300")
    make_claim(db, org.alice, amount="300", submitted_at=T0 + timedelta(hours=1))
    assert len(run_c2(db)) == 2
    assert run_c2(db, min_claims=3) == []


def test_approval_limit_comes_from_the_config(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="300")
    make_claim(db, org.alice, amount="300", submitted_at=T0 + timedelta(hours=1))
    assert run_c2(db, approval_limit=1000) == []


def test_finding_has_a_readable_reason(db):
    org = make_org(db)
    make_claim(db, org.alice, amount="300")
    make_claim(db, org.alice, amount="300", submitted_at=T0 + timedelta(hours=1))
    reason = run_c2(db)[0].reason
    assert "one of 2 claims totalling 600.00 inside 24 hours (limit 500)" in reason