from datetime import timezone
from pathlib import Path
from sqlalchemy import select

from controls_monitor.config import SEVERITY_ORDER
from controls_monitor.controls import REGISTRY
from controls_monitor.models import (
    ControlException,
    ControlResult,
    ControlRun,
    Employee,
)


class ReportError(Exception):
    pass


def md(value, limit=300):
    """Make text safe for a markdown table cell."""
    text = str(value).replace("\n", " ").replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 3] + "..."


SHOWN_ELSEWHERE = {"expense_id", "employee_id"}  # already in their own columns


def format_evidence(evidence):
    parts = []
    for key, value in sorted((evidence or {}).items()):
        if key not in SHOWN_ELSEWHERE:
            parts.append(f"{key}: {value}")
    return "; ".join(parts) if parts else "-"


def _stamp(moment):
    if moment is None:
        return "-"
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def latest_run_id(session):
    return session.scalar(select(ControlRun.id).order_by(ControlRun.id.desc()).limit(1))


def build_report(session, run_id, max_rows=20):
    run = session.get(ControlRun, run_id)
    if run is None:
        raise ReportError(f"run {run_id} not found")

    results = session.scalars(
        select(ControlResult).where(ControlResult.run_id == run_id).order_by(ControlResult.id)
    ).all()
    exceptions = session.scalars(
        select(ControlException)
        .where(ControlException.run_id == run_id)
        .order_by(ControlException.control_id, ControlException.id)
    ).all()
    names = {e.id: e.full_name for e in session.scalars(select(Employee))}

    def person(employee_id):
        if employee_id is None:
            return "-"
        return f"{names.get(employee_id, 'unknown')} (#{employee_id})"

    fail_on = (run.config_snapshot or {}).get("fail_on_severity", "high")
    by_severity = {sev: 0 for sev in SEVERITY_ORDER}
    for exc in exceptions:
        by_severity[exc.severity] += 1
    gating = sum(n for sev, n in by_severity.items() if SEVERITY_ORDER[sev] >= SEVERITY_ORDER[fail_on])
    crashed = [r for r in results if r.status == "error"]

    if crashed:
        verdict = f"ERROR ({len(crashed)} control(s) crashed)"
    elif gating:
        verdict = f"FAIL ({gating} exception(s) at or above '{fail_on}')"
    else:
        verdict = "PASS"

    lines = [
        f"# Finance Controls Monitor - run {run.id}",
        "",
        f"- Result: **{verdict}**",
        f"- Status: {run.status}",
        f"- Started: {_stamp(run.started_at)}",
        f"- Finished: {_stamp(run.finished_at)}",
        f"- Fail threshold: {fail_on}",
        f"- Total exceptions: {len(exceptions)}",
        "",
        "All data is synthetic. Findings are leads for review, not conclusions.",
        "",
        "## Summary by control",
        "",
        "| Control | Name | Severity | Status | Exceptions |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.control_id} | {md(r.control_name)} | {r.severity} | {r.status} | {r.exception_count} |"
        )

    lines += ["", "## Exceptions by severity", "", "| Severity | Count |", "|---|---|"]
    for sev in sorted(SEVERITY_ORDER, key=SEVERITY_ORDER.get, reverse=True):
        lines.append(f"| {sev} | {by_severity[sev]} |")

    if crashed:
        lines += ["", "## Errors", ""]
        for r in crashed:
            lines.append(f"- **{r.control_id}** {md(r.control_name)}: {md(r.error_message, 500)}")

    if not exceptions:
        lines += ["", "No exceptions found."]

    # most serious controls first, then by control id
    ordered = sorted(
        (r for r in results if r.exception_count > 0),
        key=lambda r: (-SEVERITY_ORDER[r.severity], r.control_id),
    )
    for r in ordered:
        rows = [e for e in exceptions if e.control_id == r.control_id]
        description = getattr(REGISTRY.get(r.control_id), "description", "")
        lines += [
            "",
            f"## {r.control_id} - {md(r.control_name)} ({r.severity}) - {len(rows)} exception(s)",
        ]
        if description:
            lines += ["", description]
        lines += [
            "",
            "| Claim | Employee | Reason | Evidence |",
            "|---|---|---|---|",
        ]
        for e in rows[:max_rows]:
            claim = f"#{e.expense_id}" if e.expense_id is not None else "-"
            lines.append(
                f"| {claim} | {md(person(e.employee_id))} | {md(e.reason)} | {md(format_evidence(e.evidence))} |"
            )
        if len(rows) > max_rows:
            lines += [
                "",
                f"_Showing {max_rows} of {len(rows)}. The full list is in the "
                f"control_exceptions table (run_id = {run.id})._",
            ]

    return "\n".join(lines) + "\n"


def write_report(text, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path