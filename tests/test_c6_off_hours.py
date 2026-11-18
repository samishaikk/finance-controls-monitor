from datetime import datetime, timedelta, timezone
from controls_monitor.config import load_config
from controls_monitor.controls.c6_off_hours import OffHoursApprovals
from tests.helpers import make_claim, make_org

def run_c6(db, **overrides):
    settings = load_config().controls.C6.model_copy(update=overrides)
    return OffHoursApprovals(settings).run(db)


def approved_at(db, when, **kwargs):
    org = make_org(db)
    submitted = when - timedelta(hours=3)
    return make_claim(db, org.alice, submitted_at=submitted, approved_at=when, **kwargs)


def utc(day, hour, minute=0, second=0):
    """January 2026: day 5 is a Monday, 10 a Saturday, 11 a Sunday."""
    return datetime(2026, 1, day, hour, minute, second, tzinfo=timezone.utc)


def test_approval_during_business_hours_is_fine(db):
    approved_at(db, utc(5, 14))
    assert run_c6(db) == []


def test_just_before_opening_is_flagged(db):
    claim = approved_at(db, utc(5, 8, 59, 59))
    findings = run_c6(db)
    assert [f.expense_id for f in findings] == [claim.id]
    assert findings[0].evidence["reason_type"] == "off_hours"


def test_exactly_at_opening_is_fine(db):
    approved_at(db, utc(5, 9, 0, 0))
    assert run_c6(db) == []


def test_last_second_before_closing_is_fine(db):
    approved_at(db, utc(5, 17, 59, 59))
    assert run_c6(db) == []


def test_exactly_at_closing_is_flagged(db):
    approved_at(db, utc(5, 18, 0, 0))
    assert len(run_c6(db)) == 1


def test_late_night_is_flagged(db):
    approved_at(db, utc(6, 23, 30))
    assert len(run_c6(db)) == 1


def test_saturday_in_office_hours_is_flagged_as_weekend(db):
    approved_at(db, utc(10, 10))
    finding = run_c6(db)[0]
    assert finding.evidence["reason_type"] == "weekend"
    assert "approved on a Saturday" in finding.reason


def test_sunday_is_flagged(db):
    approved_at(db, utc(11, 11))
    assert len(run_c6(db)) == 1


def test_weekend_flag_can_be_switched_off(db):
    approved_at(db, utc(10, 10))
    assert run_c6(db, flag_weekends=False) == []


def test_weekend_late_evening_is_still_flagged_when_weekend_flag_is_off(db):
    approved_at(db, utc(10, 20))
    findings = run_c6(db, flag_weekends=False)
    assert len(findings) == 1
    assert findings[0].evidence["reason_type"] == "off_hours"


def test_business_hours_come_from_the_config(db):
    approved_at(db, utc(5, 8, 30))
    assert len(run_c6(db)) == 1
    assert run_c6(db, business_start_hour=8) == []


def test_hours_are_judged_in_utc_not_local_time(db):
    ist = timezone(timedelta(hours=5, minutes=30))
    # 09:00 in India is 03:30 UTC, which is outside the UTC business hours.
    approved_at(db, datetime(2026, 1, 5, 9, 0, tzinfo=ist))
    assert len(run_c6(db)) == 1


def test_rejections_and_pending_claims_are_ignored(db):
    org = make_org(db)
    when = utc(10, 22)
    make_claim(db, org.alice, status="rejected", submitted_at=when - timedelta(hours=2), approved_at=when)
    make_claim(db, org.alice, status="pending", submitted_at=when - timedelta(hours=2), amount="55.00")
    assert run_c6(db) == []


def test_finding_has_a_readable_reason(db):
    approved_at(db, utc(5, 22, 15))
    assert "approved at 22:xx UTC on a Monday, outside 09:00-18:00" in run_c6(db)[0].reason