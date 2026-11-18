# Finance Controls Monitor

[![ci](https://github.com/samishaikk/finance-controls-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/samishaikk/finance-controls-monitor/actions/workflows/ci.yml)

ci-run.png

A small service that runs six automated controls over expense-reimbursement data in PostgreSQL, stores every run and every exception with evidence, and reports what it found. It also measures itself: known violations and look-alike legitimate cases are planted into the data, so each control's strengths and blind spots are shown with numbers instead of claims.

**All data is synthetic.** This is a learning and portfolio project. It is not a fraud detection product and nothing here is a claim about real-world accuracy.

## What it does

- Runs six controls as SQL against PostgreSQL (one `.sql` file per control, readable on its own).
- Reads thresholds from a validated YAML file, so a number can change without a code change.
- Saves each run, each control's result and each exception (with JSON evidence) to PostgreSQL.
- Classifies exceptions by severity (low, medium, high, critical) and exits non-zero when a run has exceptions at or above a chosen level, so a scheduler or CI job can alert on it.
- Writes a markdown exception report, Prometheus-format metrics, and structured JSON logs.
- Scores itself against planted violations and decoys (precision and recall per control).

## Quick start

You need Docker Desktop. One command builds the image, starts PostgreSQL, plants the cases, scores the controls, runs the monitor and writes the reports into `./reports`:

```bash
docker compose run --rm demo
```

Run the tests inside the container:

```bash
docker compose run --rm demo pytest -q
```

### Without Docker for the app (Python 3.12)

```bash
docker compose up -d db                      # PostgreSQL on localhost:5435
pip install -r requirements.txt
python -m controls_monitor.generator --reset --with-violations
python -m controls_monitor evaluate --output reports/evaluation.md
python -m controls_monitor run --report reports/latest.md --metrics reports/controls_monitor.prom
pytest -q
```

### Commands

| Command | What it does |
|---|---|
| `python -m controls_monitor run` | Run all enabled controls, save the run, print a summary. Options: `--config`, `--fail-on`, `--report`, `--metrics`, `--log-level`. |
| `python -m controls_monitor evaluate` | Run the monitor and score it against the planted cases. |
| `python -m controls_monitor report` | Rebuild a markdown report for any stored run. |
| `python -m controls_monitor metrics` | Print or write Prometheus metrics for a stored run. |
| `python -m controls_monitor history` | List recent runs. |
| `python -m controls_monitor.generator` | Seed a synthetic company (`--reset`, `--with-violations`, `--seed`). |

Exit codes of `run`: `0` nothing at or above the fail level, `1` exceptions at or above it, `2` a control crashed or the config is invalid. A crashed control is recorded as `error`, never as `passed`.

## The six controls

| ID | Control | Severity | Rule (defaults in `config/controls.yaml`) |
|---|---|---|---|
| C1 | Duplicate claims | high | A later claim with the same receipt number, or the same employee + vendor + amount within 7 days. Rejected claims are ignored. |
| C2 | Split claims under the approval limit | high | Claims each under 500 that, within 24 hours, number at least 2 and add up to 500 or more. |
| C3 | Approver is not the employee's manager | critical | An approved claim with no approver, a self-approval, or an approver who is neither the manager nor (if allowed) the skip-level manager. |
| C4 | Approval too fast to be a real review | medium | Approved less than 120 seconds after submission (a negative delay is also flagged). |
| C5 | Approval-rate outlier manager | medium | An approver (at least 30 decisions) whose approval rate is 20 or more points above the median of the other qualifying approvers. |
| C6 | Off-hours or weekend approval | low | Approved outside 09:00-18:00 UTC, or on a weekend (both configurable). |

Each control is a SQL file in `controls_monitor/sql/` plus a small Python class that binds the thresholds and turns rows into findings. Every finding carries evidence (the numbers that triggered it) so a reviewer does not have to re-derive it.

## How it fits together

```
config/controls.yaml --> validated settings
                              |
PostgreSQL (expenses,         v
employees, audit_log) --> runner --> C1..C6 (SQL) --> findings
                              |
                              v
        control_runs / control_results / control_exceptions  (history)
                              |
          +-------------------+-------------------+
          v                   v                   v
   markdown report     Prometheus metrics    JSON logs (stderr)
                              ^
 injected_violations (ground truth) --> evaluation: precision / recall per control
```

The report and the metrics are built only from stored rows, so the same run always produces the same report.

## Does it work? (evaluation)

The generator builds a clean company (46 employees, 447 expenses). The injector then plants 48 violations and 31 legitimate look-alikes ("decoys") with a recorded answer key. Each case is built to trigger only its own control.

| Control | Planted | Caught | Missed | Decoys | Decoys flagged | Precision | Recall |
|---|---|---|---|---|---|---|---|
| C1 duplicate claims | 11 | 8 | 3 | 6 | 2 | 80.0% | 72.7% |
| C2 split claims | 14 | 10 | 4 | 7 | 2 | 83.3% | 71.4% |
| C3 approver not manager | 8 | 8 | 0 | 7 | 2 | 80.0% | 100.0% |
| C4 too-fast approvals | 7 | 5 | 2 | 5 | 2 | 71.4% | 71.4% |
| C5 outlier manager | 2 | 1 | 1 | 2 | 1 | 50.0% | 50.0% |
| C6 off-hours approvals | 6 | 6 | 0 | 4 | 2 | 75.0% | 100.0% |
| **all** | 48 | 38 | 10 | 31 | 11 | 77.6% | 79.2% |

**How to read this honestly.** I designed this case set, including how many hard cases it contains, so the percentages describe the case set, not the real world. What the table is good for is showing *why* each control misses or over-flags:

- C3 and C6 are rule checks on recorded fields, so recall is 100% by construction. Their weakness is false positives.
- C1, C2, C4 and C5 depend on a threshold, window or gap, so each has misses with a named cause (see below).
- Unplanned flags are 0: nothing is flagged that was not planted, and the clean company produces no exceptions for several different seeds.

## Assumptions

- All times are UTC. Business hours are 09:00-18:00 UTC unless configured otherwise.
- The employee's manager is the single `manager_id` on the employee row; there is no delegation table or org history.
- Amounts are in one currency (USD); there is no conversion.
- The approval time is `approved_at` and the decision maker is `approver_id` as recorded. The monitor does not verify them against another system.
- Rejected claims are not counted as duplicates or as part of a split.
- The audit log is written by the generator alongside each claim; controls read the expense table, not the log.

## Limitations

- The data is synthetic, generated with a fixed seed. Results here say nothing about how the rules perform on a real company's data.
- The thresholds (7 days, 24 hours, 500, 120 seconds, 20 points, business hours) are arbitrary, configurable defaults, not tuned or validated values.
- C1 matches exactly. A resubmission with the amount off by one cent or a differently spelled vendor is missed.
- C2 uses a fixed window and a fixed limit. Splits spread over more than the window are missed.
- C4 uses one fixed cutoff for every claim size, so a rubber stamp at 130 seconds passes.
- C5 compares each approver to the median of the other qualifying approvers. It needs at least two peers, only flags the high side, and a small number of approvers makes the median unstable.
- No fuzzy matching, no per-office time zones, no delegation or leave calendar, no currency handling, no statistical testing.
- It reads a database directly. There is no live integration with a finance system and no scheduler is deployed. The metrics file is in Prometheus text format, but no Prometheus server or Grafana dashboard is part of this repo.
- Exceptions are leads for a human reviewer, not conclusions about anyone.

## Known false positives and misses

Legitimate cases the rules flag (from `reports/evaluation.md`):

- **C1:** two genuine identical trips look exactly like a duplicate.
- **C2:** two genuine conference hotel charges look like a split.
- **C3:** a delegate who legitimately approves while the manager is on leave.
- **C4:** tiny claims auto-approved by policy within seconds.
- **C5:** a small senior team that legitimately approves almost everything.
- **C6:** an overseas office approving at 09:30 local time (04:00 UTC), and a quarter-end close approved on a Saturday.

Real violations the rules miss:

- **C1:** a duplicate with the amount off by one cent, or with the vendor spelled differently.
- **C2:** split claims 30 hours apart (outside the 24-hour window).
- **C4:** rubber-stamp approvals at 130 and 170 seconds.
- **C5:** an approver at an 84% approval rate, high but under the 20-point gap.

Each of these is a documented trade-off, and each is covered by a planted case so a change to a threshold shows up in the scores.

## Configuration

```yaml
controls:
  C4:
    name: Approval too fast to be a real review
    enabled: true
    severity: medium
    min_review_seconds: 120
```

Unknown keys, wrong types, out-of-range values and inverted hours are rejected when the file loads. The config used by each run is stored with the run. The C5 gap of 20 points was chosen by measuring natural variation in clean data (up to about 19 points over 100 seeds with 30% rejections), so the control does not flag normal data.

## Operations

**Logs.** One JSON line per event on stderr, with `run_id` on every line (run start, each control finished, run finished, report written). Human output stays on stdout.

```json
{"level": "INFO", "logger": "controls_monitor.runner", "event": "control_finished", "run_id": 2, "control_id": "C1", "severity": "high", "status": "failed", "exception_count": 10, "duration_ms": 25}
```

**Metrics** (Prometheus text format, `reports/controls_monitor.prom`, designed for the node_exporter textfile collector):

| Metric | Meaning |
|---|---|
| `controls_monitor_exceptions{control_id,severity}` | exceptions found per control |
| `controls_monitor_exceptions_at_or_above_threshold` | what would fail the run |
| `controls_monitor_control_errored{control_id}` | 1 if a control crashed |
| `controls_monitor_control_duration_seconds{control_id}` | time per control |
| `controls_monitor_run_duration_seconds` | total run time |
| `controls_monitor_last_run_success` | 1 if every control executed |
| `controls_monitor_last_successful_run_timestamp_seconds` | for staleness alerts |

**Example alert rules** (not deployed; shown to document intent):

```yaml
- alert: ControlsMonitorStale
  expr: time() - controls_monitor_last_successful_run_timestamp_seconds > 90000   # no good run in ~25h
- alert: ControlCrashed
  expr: controls_monitor_control_errored == 1
- alert: HighSeverityExceptions
  expr: controls_monitor_exceptions_at_or_above_threshold > 0
```

## Testing and CI

- 192 tests: positive, negative and boundary tests for every control (for example an approval at exactly the limit, a claim at exactly 09:00:00, a duplicate on exactly day 7), plus tests for config validation, the runner (including a crashing control), report, metrics, logging, the CLI and the evaluation arithmetic.
- About 95% line coverage. GitHub Actions runs everything against a real PostgreSQL 16 service and fails below 80% coverage.
- Two end-to-end gates in CI: a clean company must produce zero exceptions, and the planted-violation scorecard must match exactly. If you change a control or threshold on purpose, the scores move and the gate line in `.github/workflows/ci.yml` is updated deliberately.
- Reports from the CI run are uploaded as a downloadable artifact.

## Project layout

```
controls_monitor/
  controls/        one class per control + registry
  sql/             one .sql file per control
  runner.py        runs controls, stores runs/results/exceptions, exit codes
  config.py        YAML loading and validation
  report.py        markdown exception report (from the database only)
  metrics.py       Prometheus textfile metrics
  logging_setup.py JSON logs on stderr
  generator.py     clean synthetic company
  injector.py      planted violations and decoys (ground truth)
  evaluation.py    precision / recall per control
  cli.py           run / evaluate / report / metrics / history
config/controls.yaml
docker/            init.sql, demo.sh
tests/
.github/workflows/ci.yml
```

## Stack

Python 3.12, PostgreSQL 16, SQLAlchemy 2, Pydantic 2, PyYAML, prometheus-client, pytest, pytest-cov, Docker Compose, GitHub Actions.
