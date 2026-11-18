from datetime import timedelta
from controls_monitor.config import load_config
from controls_monitor.controls.c4_fast_approvals import FastApprovals
from tests.helpers import T0, make_claim, make_org


def run_c4(db, **overrides):
    settings = load_config().controls.C4.model_copy(update=overrides)
    return FastApprovals(settings).run(db)


def test_approval_after_30_seconds_is_flagged(db):
    org = make_org(db)
    claim = make_claim(db, org.alice, approved_at=T0 + timedelta(seconds=30))
    findings = run_c4(db)
    assert [f.expense_id for f in findings] == [claim.id]
    assert findings[0].evidence["latency_seconds"] == 30


def test_exactly_the_minimum_is_not_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, approved_at=T0 + timedelta(seconds=120))
    assert run_c4(db) == []


def test_one_second_under_the_minimum_is_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, approved_at=T0 + timedelta(seconds=119))
    assert len(run_c4(db)) == 1


def test_a_normal_review_time_is_not_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, approved_at=T0 + timedelta(hours=5))
    assert run_c4(db) == []


def test_approval_before_submission_is_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, approved_at=T0 - timedelta(hours=1))
    finding = run_c4(db)[0]
    assert finding.evidence["latency_seconds"] == -3600
    assert "before its submission time" in finding.reason


def test_a_fast_rejection_is_not_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, status="rejected", approved_at=T0 + timedelta(seconds=5))
    assert run_c4(db) == []


def test_pending_claims_are_not_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, status="pending")
    assert run_c4(db) == []


def test_minimum_comes_from_the_config(db):
    org = make_org(db)
    make_claim(db, org.alice, approved_at=T0 + timedelta(seconds=300))
    assert run_c4(db) == []
    assert len(run_c4(db, min_review_seconds=600)) == 1


def test_finding_has_a_readable_reason(db):
    org = make_org(db)
    make_claim(db, org.alice, approved_at=T0 + timedelta(seconds=30))
    assert "approved 30 seconds after submission (minimum 120)" in run_c4(db)[0].reason