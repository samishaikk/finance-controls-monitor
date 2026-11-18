from controls_monitor.config import load_config
from controls_monitor.controls.c3_approver import ApproverNotManager
from tests.helpers import make_claim, make_org





def run_c3(db, **overrides):
    settings = load_config().controls.C3.model_copy(update=overrides)
    return ApproverNotManager(settings).run(db)


def test_manager_approval_is_fine(db):
    org = make_org(db)
    make_claim(db, org.alice)
    assert run_c3(db) == []


def test_peer_approving_is_flagged(db):
    org = make_org(db)
    claim = make_claim(db, org.alice, approver_id=org.bob.id)
    findings = run_c3(db)
    assert [f.expense_id for f in findings] == [claim.id]
    assert findings[0].evidence["violation_type"] == "not_manager"
    assert findings[0].evidence["approver_id"] == org.bob.id


def test_another_departments_manager_approving_is_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, approver_id=org.other_manager.id)
    assert len(run_c3(db)) == 1


def test_skip_level_approval_is_allowed_by_default(db):
    org = make_org(db)
    make_claim(db, org.alice, approver_id=org.ceo.id)
    assert run_c3(db) == []


def test_skip_level_approval_is_flagged_when_not_allowed(db):
    org = make_org(db)
    make_claim(db, org.alice, approver_id=org.ceo.id)
    assert len(run_c3(db, allow_skip_level=False)) == 1


def test_self_approval_is_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, approver_id=org.alice.id)
    findings = run_c3(db)
    assert findings[0].evidence["violation_type"] == "self_approval"
    assert "approved their own claim" in findings[0].reason


def test_self_approval_is_flagged_even_for_someone_with_no_manager(db):
    org = make_org(db)
    make_claim(db, org.ceo, approver_id=org.ceo.id)
    assert run_c3(db)[0].evidence["violation_type"] == "self_approval"


def test_approved_with_no_approver_recorded_is_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, approver_id=None)
    assert run_c3(db)[0].evidence["violation_type"] == "no_approver"


def test_pending_claim_without_approver_is_fine(db):
    org = make_org(db)
    make_claim(db, org.alice, status="pending", approver_id=None)
    assert run_c3(db) == []


def test_rejection_by_someone_else_is_not_flagged(db):
    org = make_org(db)
    make_claim(db, org.alice, status="rejected", approver_id=org.bob.id)
    assert run_c3(db) == []


def test_severity_is_critical(db):
    org = make_org(db)
    make_claim(db, org.alice, approver_id=org.bob.id)
    control = ApproverNotManager(load_config().controls.C3)
    assert control.severity == "critical"