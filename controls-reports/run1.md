# Finance Controls Monitor - run 1

- Result: **FAIL (1 exception(s) at or above 'high')**
- Status: success
- Started: 2026-11-18 12:24:38 UTC
- Finished: 2026-11-18 12:24:38 UTC
- Fail threshold: high
- Total exceptions: 2

All data is synthetic. Findings are leads for review, not conclusions.

## Summary by control

| Control | Name | Severity | Status | Exceptions |
|---|---|---|---|---|
| C1 | Duplicate claims | high | passed | 0 |
| C2 | Split claims under the approval limit | high | passed | 0 |
| C3 | Approver is not the employee's manager | critical | failed | 1 |
| C4 | Approval too fast to be a real review | medium | failed | 1 |
| C5 | Approval-rate outlier manager | medium | passed | 0 |
| C6 | Off-hours or weekend approval | low | passed | 0 |

## Exceptions by severity

| Severity | Count |
|---|---|
| critical | 1 |
| high | 0 |
| medium | 1 |
| low | 0 |

## C3 - Approver is not the employee's manager (critical) - 1 exception(s)

Segregation of duties: only the employee's manager (or skip-level) may approve.

| Claim | Employee | Reason | Evidence |
|---|---|---|---|
| #448 | Divya Das (#5) | employee 5 approved their own claim 448 | amount: 77.00; approved_at: 2026-11-17T12:24:51.222915+00:00; approver_id: 5; manager_id: 2; skip_level_id: 1; violation_type: self_approval |

## C4 - Approval too fast to be a real review (medium) - 1 exception(s)

Claims approved sooner after submission than a person could review them.

| Claim | Employee | Reason | Evidence |
|---|---|---|---|
| #448 | Divya Das (#5) | claim 448 was approved 20 seconds after submission (minimum 120) | amount: 77.00; approved_at: 2026-11-17T12:24:51.222915+00:00; approver_id: 5; latency_seconds: 20; submitted_at: 2026-11-17T12:24:31.222915+00:00 |
