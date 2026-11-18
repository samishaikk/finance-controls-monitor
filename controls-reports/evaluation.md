# Detection evaluation - run 1

All data is synthetic. The case set was built with deliberate misses and look-alike decoys, so these numbers describe this test set, not real-world accuracy.

| Control | Name | Planted | Caught | Missed | Decoys | Decoys flagged | Unplanned flags | Precision | Recall |
|---|---|---|---|---|---|---|---|---|---|
| C1 | Duplicate claims | 11 | 8 | 3 | 6 | 2 | 0 | 80.0% | 72.7% |
| C2 | Split claims under the approval limit | 14 | 10 | 4 | 7 | 2 | 0 | 83.3% | 71.4% |
| C3 | Approver is not the employee's manager | 8 | 8 | 0 | 7 | 2 | 0 | 80.0% | 100.0% |
| C4 | Approval too fast to be a real review | 7 | 5 | 2 | 5 | 2 | 0 | 71.4% | 71.4% |
| C5 | Approval-rate outlier manager | 2 | 1 | 1 | 2 | 1 | 0 | 50.0% | 50.0% |
| C6 | Off-hours or weekend approval | 6 | 6 | 0 | 4 | 2 | 0 | 75.0% | 100.0% |
| **all** | | 48 | 38 | 10 | 31 | 11 | 0 | 77.6% | 79.2% |

- **Planted**: real violations put into the data. **Caught**: flagged by the control.
- **Decoys**: legitimate look-alikes. **Decoys flagged**: false positives the rule cannot avoid.
- **Unplanned flags**: flagged items that were not planted at all (should be 0).
- Precision = caught / (caught + decoys flagged + unplanned). Recall = caught / planted.

## Known misses (real violations the rules do not catch)

- C1: duplicate with the amount off by 1 cent (a miss)
- C1: duplicate with the vendor name spelled differently (a miss)
- C1: duplicate with the amount off by 1 cent (a miss)
- C2: split claims 30 hours apart - outside the window (a miss)
- C2: split claims 30 hours apart - outside the window (a miss)
- C2: split claims 30 hours apart - outside the window (a miss)
- C2: split claims 30 hours apart - outside the window (a miss)
- C4: rubber-stamp approval after 130 seconds - over the 120 s limit (a miss)
- C4: rubber-stamp approval after 170 seconds - over the 120 s limit (a miss)
- C5: high approval rate but under the gap threshold (a miss)

## Known false positives (legitimate cases the rules flag)

- C1: two genuine identical trips - looks exactly like a duplicate (flagged anyway)
- C1: two genuine identical trips - looks exactly like a duplicate (flagged anyway)
- C2: two genuine conference hotel charges (flagged anyway)
- C2: two genuine conference hotel charges (flagged anyway)
- C3: legitimate delegate approved while the manager was on leave (flagged anyway)
- C3: legitimate delegate approved while the manager was on leave (flagged anyway)
- C4: tiny claim auto-approved by policy within seconds (flagged anyway)
- C4: tiny claim auto-approved by policy within seconds (flagged anyway)
- C5: legitimately high approval rate (small senior team) - flagged anyway
- C6: approved at 09:30 India time (04:00 UTC) by an overseas office (flagged anyway)
- C6: quarter-end close approved on a Saturday (flagged anyway)
