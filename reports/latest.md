# Finance Controls Monitor - run 2

- Result: **FAIL (32 exception(s) at or above 'high')**
- Status: success
- Started: 2026-11-18 13:21:05 UTC
- Finished: 2026-11-18 13:21:06 UTC
- Fail threshold: high
- Total exceptions: 49

All data is synthetic. Findings are leads for review, not conclusions.

## Summary by control

| Control | Name | Severity | Status | Exceptions |
|---|---|---|---|---|
| C1 | Duplicate claims | high | failed | 10 |
| C2 | Split claims under the approval limit | high | failed | 12 |
| C3 | Approver is not the employee's manager | critical | failed | 10 |
| C4 | Approval too fast to be a real review | medium | failed | 7 |
| C5 | Approval-rate outlier manager | medium | failed | 2 |
| C6 | Off-hours or weekend approval | low | failed | 8 |

## Exceptions by severity

| Severity | Count |
|---|---|
| critical | 10 |
| high | 22 |
| medium | 9 |
| low | 8 |

## C3 - Approver is not the employee's manager (critical) - 10 exception(s)

Segregation of duties: only the employee's manager (or skip-level) may approve.

| Claim | Employee | Reason | Evidence |
|---|---|---|---|
| #508 | Arjun Joshi (#3) | employee 3 approved their own claim 508 | amount: 53.21; approved_at: 2026-02-19T09:21:00.761686+00:00; approver_id: 3; manager_id: 2; skip_level_id: 1; violation_type: self_approval |
| #509 | Sneha Singh (#25) | employee 25 approved their own claim 509 | amount: 259.81; approved_at: 2026-03-05T09:20:39.578835+00:00; approver_id: 25; manager_id: 20; skip_level_id: 1; violation_type: self_approval |
| #510 | Divya Menon (#13) | employee 13 approved their own claim 510 | amount: 77.12; approved_at: 2026-02-23T09:10:15.178184+00:00; approver_id: 13; manager_id: 11; skip_level_id: 1; violation_type: self_approval |
| #511 | Vikram Rao (#9) | claim 511 was approved by employee 29, who is not the employee's manager | amount: 179.11; approved_at: 2026-02-12T09:03:09.409128+00:00; approver_id: 29; manager_id: 2; skip_level_id: 1; violation_type: not_manager |
| #512 | Divya Menon (#13) | claim 512 was approved by employee 38, who is not the employee's manager | amount: 134.01; approved_at: 2026-01-07T14:05:32.741983+00:00; approver_id: 38; manager_id: 11; skip_level_id: 1; violation_type: not_manager |
| #513 | Aditya Menon (#24) | claim 513 was approved by employee 29, who is not the employee's manager | amount: 289.29; approved_at: 2026-02-04T09:50:39.620902+00:00; approver_id: 29; manager_id: 20; skip_level_id: 1; violation_type: not_manager |
| #514 | Vikram Joshi (#36) | claim 514 was approved but no approver is recorded | amount: 24.34; approved_at: 2026-01-12T09:26:41.590260+00:00; approver_id: None; manager_id: 29; skip_level_id: 1; violation_type: no_approver |
| #515 | Aditya Khan (#23) | claim 515 was approved but no approver is recorded | amount: 290.36; approved_at: 2026-03-12T10:23:22.549095+00:00; approver_id: None; manager_id: 20; skip_level_id: 1; violation_type: no_approver |
| #521 | Divya Reddy (#22) | claim 521 was approved by employee 29, who is not the employee's manager | amount: 216.34; approved_at: 2026-03-06T14:18:28.162295+00:00; approver_id: 29; manager_id: 20; skip_level_id: 1; violation_type: not_manager |
| #522 | Arjun Joshi (#3) | claim 522 was approved by employee 38, who is not the employee's manager | amount: 294.54; approved_at: 2026-01-22T09:34:39.272471+00:00; approver_id: 38; manager_id: 2; skip_level_id: 1; violation_type: not_manager |

## C1 - Duplicate claims (high) - 10 exception(s)

The same expense submitted twice (same receipt, or same employee, vendor and amount).

| Claim | Employee | Reason | Evidence |
|---|---|---|---|
| #470 | Vikram Sharma (#39) | claim 470 has the same employee, vendor and amount as earlier claim 369 | amount: 394.70; match_type: same_employee_vendor_amount; original_expense_id: 369; original_submitted_at: 2026-01-19T13:41:20+00:00; submitted_at: 2026-01-23T11:55:59+00:00; vendor: CityRail |
| #471 | Arjun Joshi (#3) | claim 471 has the same employee, vendor and amount as earlier claim 12 | amount: 112.18; match_type: same_employee_vendor_amount; original_expense_id: 12; original_submitted_at: 2026-01-07T09:03:37+00:00; submitted_at: 2026-01-09T12:49:01+00:00; vendor: Harbor Inn |
| #472 | Divya Khan (#14) | claim 472 has the same employee, vendor and amount as earlier claim 121 | amount: 115.95; match_type: same_employee_vendor_amount; original_expense_id: 121; original_submitted_at: 2026-02-03T13:12:11+00:00; submitted_at: 2026-02-09T12:27:36+00:00; vendor: PaperTrail Supplies |
| #473 | Karan Menon (#35) | claim 473 has the same employee, vendor and amount as earlier claim 329 | amount: 23.98; match_type: same_employee_vendor_amount; original_expense_id: 329; original_submitted_at: 2026-01-22T09:50:44+00:00; submitted_at: 2026-01-27T12:38:04+00:00; vendor: DeskWorks |
| #474 | Arjun Nair (#4) | claim 474 has the same employee, vendor and amount as earlier claim 24 | amount: 39.25; match_type: same_employee_vendor_amount; original_expense_id: 24; original_submitted_at: 2026-01-13T12:01:42+00:00; submitted_at: 2026-01-19T11:04:47+00:00; vendor: Urban Kitchen |
| #475 | Aditya Sharma (#26) | claim 475 has the same employee, vendor and amount as earlier claim 234 | amount: 135.71; match_type: same_employee_vendor_amount; original_expense_id: 234; original_submitted_at: 2026-01-08T13:30:50+00:00; submitted_at: 2026-01-12T13:26:14+00:00; vendor: SkyJet Airways |
| #476 | Rohan Menon (#18) | claim 476 shares a receipt number with earlier claim 226 | amount: 34.53; match_type: same_receipt; original_expense_id: 226; original_submitted_at: 2026-01-29T10:19:10+00:00; submitted_at: 2026-03-17T13:50:11+00:00; vendor: SkyJet Airways |
| #477 | Divya Rao (#43) | claim 477 shares a receipt number with earlier claim 416 | amount: 198.41; match_type: same_receipt; original_expense_id: 416; original_submitted_at: 2026-01-05T12:33:58+00:00; submitted_at: 2026-01-28T15:08:21+00:00; vendor: SkillBridge Academy |
| #485 | Asha Patel (#10) | claim 485 has the same employee, vendor and amount as earlier claim 86 | amount: 450.67; match_type: same_employee_vendor_amount; original_expense_id: 86; original_submitted_at: 2026-02-05T13:00:36+00:00; submitted_at: 2026-02-09T10:58:18+00:00; vendor: SkillBridge Academy |
| #486 | Vikram Singh (#28) | claim 486 has the same employee, vendor and amount as earlier claim 255 | amount: 35.96; match_type: same_employee_vendor_amount; original_expense_id: 255; original_submitted_at: 2026-01-20T13:02:17+00:00; submitted_at: 2026-01-22T11:30:33+00:00; vendor: Spice Route |

## C2 - Split claims under the approval limit (high) - 12 exception(s)

Several small claims in a short window that together reach the approval limit.

| Claim | Employee | Reason | Evidence |
|---|---|---|---|
| #487 | Meera Khan (#6) | claim 487 is one of 2 claims totalling 760.21 inside 24 hours (limit 500) | amount: 322.73; claim_count: 2; claim_ids: [487, 488]; total: 760.21; window_start: 2026-02-26T09:31:26+00:00 |
| #488 | Meera Khan (#6) | claim 488 is one of 2 claims totalling 760.21 inside 24 hours (limit 500) | amount: 437.48; claim_count: 2; claim_ids: [487, 488]; total: 760.21; window_start: 2026-02-26T09:31:26+00:00 |
| #489 | Ravi Khan (#12) | claim 489 is one of 2 claims totalling 563.30 inside 24 hours (limit 500) | amount: 263.28; claim_count: 2; claim_ids: [489, 490]; total: 563.30; window_start: 2026-02-03T10:41:41+00:00 |
| #490 | Ravi Khan (#12) | claim 490 is one of 2 claims totalling 563.30 inside 24 hours (limit 500) | amount: 300.02; claim_count: 2; claim_ids: [489, 490]; total: 563.30; window_start: 2026-02-03T10:41:41+00:00 |
| #491 | Divya Das (#5) | claim 491 is one of 3 claims totalling 596.33 inside 24 hours (limit 500) | amount: 209.18; claim_count: 3; claim_ids: [491, 492, 493]; total: 596.33; window_start: 2026-02-06T09:23:14+00:00 |
| #492 | Divya Das (#5) | claim 492 is one of 3 claims totalling 596.33 inside 24 hours (limit 500) | amount: 215.92; claim_count: 3; claim_ids: [491, 492, 493]; total: 596.33; window_start: 2026-02-06T09:23:14+00:00 |
| #493 | Divya Das (#5) | claim 493 is one of 3 claims totalling 596.33 inside 24 hours (limit 500) | amount: 171.23; claim_count: 3; claim_ids: [491, 492, 493]; total: 596.33; window_start: 2026-02-06T09:23:14+00:00 |
| #494 | Divya Nair (#17) | claim 494 is one of 3 claims totalling 761.88 inside 24 hours (limit 500) | amount: 260.73; claim_count: 3; claim_ids: [494, 495, 496]; total: 761.88; window_start: 2026-03-26T10:11:04+00:00 |
| #495 | Divya Nair (#17) | claim 495 is one of 3 claims totalling 761.88 inside 24 hours (limit 500) | amount: 248.63; claim_count: 3; claim_ids: [494, 495, 496]; total: 761.88; window_start: 2026-03-26T10:11:04+00:00 |
| #496 | Divya Nair (#17) | claim 496 is one of 3 claims totalling 761.88 inside 24 hours (limit 500) | amount: 252.52; claim_count: 3; claim_ids: [494, 495, 496]; total: 761.88; window_start: 2026-03-26T10:11:04+00:00 |
| #506 | Vikram Das (#31) | claim 506 is one of 2 claims totalling 546.79 inside 24 hours (limit 500) | amount: 242.23; claim_count: 2; claim_ids: [506, 507]; total: 546.79; window_start: 2026-02-26T09:09:38+00:00 |
| #507 | Vikram Das (#31) | claim 507 is one of 2 claims totalling 546.79 inside 24 hours (limit 500) | amount: 304.56; claim_count: 2; claim_ids: [506, 507]; total: 546.79; window_start: 2026-02-26T09:09:38+00:00 |

## C4 - Approval too fast to be a real review (medium) - 7 exception(s)

Claims approved sooner after submission than a person could review them.

| Claim | Employee | Reason | Evidence |
|---|---|---|---|
| #523 | Karan Menon (#35) | claim 523 was approved 5 seconds after submission (minimum 120) | amount: 193.89; approved_at: 2026-03-03T15:16:55+00:00; approver_id: 29; latency_seconds: 5; submitted_at: 2026-03-03T15:16:50+00:00 |
| #524 | Vikram Das (#31) | claim 524 was approved 20 seconds after submission (minimum 120) | amount: 46.88; approved_at: 2026-03-17T10:25:42+00:00; approver_id: 29; latency_seconds: 20; submitted_at: 2026-03-17T10:25:22+00:00 |
| #525 | Meera Khan (#6) | claim 525 was approved 45 seconds after submission (minimum 120) | amount: 273.15; approved_at: 2026-01-09T14:16:39+00:00; approver_id: 2; latency_seconds: 45; submitted_at: 2026-01-09T14:15:54+00:00 |
| #526 | Nisha Das (#15) | claim 526 was approved 60 seconds after submission (minimum 120) | amount: 34.41; approved_at: 2026-02-16T15:34:28+00:00; approver_id: 11; latency_seconds: 60; submitted_at: 2026-02-16T15:33:28+00:00 |
| #527 | Aditya Sharma (#26) | claim 527 was approved 90 seconds after submission (minimum 120) | amount: 266.90; approved_at: 2026-03-10T11:50:41+00:00; approver_id: 20; latency_seconds: 90; submitted_at: 2026-03-10T11:49:11+00:00 |
| #533 | Divya Menon (#13) | claim 533 was approved 3 seconds after submission (minimum 120) | amount: 9.30; approved_at: 2026-02-27T12:01:17+00:00; approver_id: 11; latency_seconds: 3; submitted_at: 2026-02-27T12:01:14+00:00 |
| #534 | Karan Das (#45) | claim 534 was approved 8 seconds after submission (minimum 120) | amount: 18.20; approved_at: 2026-03-26T14:52:49+00:00; approver_id: 38; latency_seconds: 8; submitted_at: 2026-03-26T14:52:41+00:00 |

## C5 - Approval-rate outlier manager (medium) - 2 exception(s)

An approver whose approval rate is far above the median of their peers.

| Claim | Employee | Reason | Evidence |
|---|---|---|---|
| - | Asha Sharma (#2) | approver 2 approved 100.0% of 94 decisions; peer median is 73.6% | approval_rate: 100.0; approved: 94; decisions: 94; gap_points: 26.4; peer_count: 5; peer_median: 73.6 |
| - | Rohan Reddy (#20) | approver 20 approved 97.9% of 94 decisions; peer median is 73.6% | approval_rate: 97.9; approved: 92; decisions: 94; gap_points: 24.3; peer_count: 5; peer_median: 73.6 |

## C6 - Off-hours or weekend approval (low) - 8 exception(s)

Approvals made outside business hours or at weekends (UTC).

| Claim | Employee | Reason | Evidence |
|---|---|---|---|
| #535 | Arjun Das (#21) | claim 535 was approved on a Saturday | amount: 122.89; approved_at: 2026-03-28T10:34:00+00:00; approver_id: 20; hour_utc: 10; iso_weekday: 6; reason_type: weekend |
| #536 | Aditya Joshi (#16) | claim 536 was approved on a Sunday | amount: 252.51; approved_at: 2026-02-15T11:53:00+00:00; approver_id: 11; hour_utc: 11; iso_weekday: 7; reason_type: weekend |
| #537 | Divya Reddy (#22) | claim 537 was approved on a Saturday | amount: 213.88; approved_at: 2026-03-14T14:35:00+00:00; approver_id: 20; hour_utc: 14; iso_weekday: 6; reason_type: weekend |
| #538 | Ravi Rao (#44) | claim 538 was approved at 22:xx UTC on a Thursday, outside 09:00-18:00 | amount: 167.72; approved_at: 2026-01-08T22:05:00+00:00; approver_id: 38; hour_utc: 22; iso_weekday: 4; reason_type: off_hours |
| #539 | Vikram Sharma (#39) | claim 539 was approved at 23:xx UTC on a Friday, outside 09:00-18:00 | amount: 222.24; approved_at: 2026-01-09T23:40:00+00:00; approver_id: 38; hour_utc: 23; iso_weekday: 5; reason_type: off_hours |
| #540 | Priya Menon (#27) | claim 540 was approved at 20:xx UTC on a Tuesday, outside 09:00-18:00 | amount: 252.21; approved_at: 2026-03-03T20:15:00+00:00; approver_id: 20; hour_utc: 20; iso_weekday: 2; reason_type: off_hours |
| #543 | Aditya Khan (#23) | claim 543 was approved at 04:xx UTC on a Tuesday, outside 09:00-18:00 | amount: 98.39; approved_at: 2026-01-06T04:00:00+00:00; approver_id: 20; hour_utc: 4; iso_weekday: 2; reason_type: off_hours |
| #544 | Sneha Khan (#19) | claim 544 was approved on a Saturday | amount: 281.07; approved_at: 2026-01-17T12:24:00+00:00; approver_id: 11; hour_utc: 12; iso_weekday: 6; reason_type: weekend |
