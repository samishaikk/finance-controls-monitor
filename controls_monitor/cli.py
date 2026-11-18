import argparse
import sys

from sqlalchemy import select
from controls_monitor.config import SEVERITY_ORDER, ConfigError, load_config
from controls_monitor.db import make_engine, make_session_factory
from controls_monitor.models import ControlRun
from controls_monitor.report import ReportError, build_report, latest_run_id, write_report
from controls_monitor.runner import (
    EXIT_ERROR,
    EXIT_EXCEPTIONS,
    exit_code,
    run_all,
)
def format_summary(summary, fail_on, code):
    lines = [
        f"run {summary.run_id} finished: {summary.status}, "
        f"{summary.total_exceptions} exception(s)",
        f"fail threshold: {fail_on}",
        "",
        f"{'control':<8}{'severity':<10}{'status':<8}{'exceptions':<12}{'ms':<7}name",
    ]
    for o in summary.outcomes:
        lines.append(
            f"{o.control_id:<8}{o.severity:<10}{o.status:<8}"
            f"{o.exception_count:<12}{o.duration_ms:<7}{o.name}"
        )
        if o.error_message:
            lines.append(f"        ERROR: {o.error_message}")
    by_sev = "  ".join(
        f"{sev}={summary.exceptions_by_severity.get(sev, 0)}"
        for sev in sorted(SEVERITY_ORDER, key=SEVERITY_ORDER.get, reverse=True)
    )
    lines += ["", f"exceptions by severity: {by_sev}"]
    if code == EXIT_ERROR:
        reason = f"{len(summary.errored)} control(s) crashed"
    elif code == EXIT_EXCEPTIONS:
        reason = (
            f"{summary.count_at_or_above(fail_on)} exception(s) "
            f"at or above '{fail_on}'"
        )
    else:
        reason = f"nothing at or above '{fail_on}'"
    lines.append(f"exit code: {code} ({reason})")
    return "\n".join(lines)


def cmd_run(args, engine):
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return EXIT_ERROR
    fail_on = args.fail_on or config.fail_on_severity
    with make_session_factory(engine)() as session:
        summary = run_all(session, config)
        report_path = None
        if args.report:
            report_path = write_report(build_report(session, summary.run_id), args.report)
    code = exit_code(summary, fail_on)
    print(format_summary(summary, fail_on, code))
    if report_path:
        print(f"report written to {report_path}")
    return code


def cmd_report(args, engine):
    with make_session_factory(engine)() as session:
        run_id = args.run_id or latest_run_id(session)
        if run_id is None:
            print("no runs yet - run the monitor first", file=sys.stderr)
            return EXIT_ERROR
        try:
            text = build_report(session, run_id, max_rows=args.max_rows)
        except ReportError as exc:
            print(exc, file=sys.stderr)
            return EXIT_ERROR
    if args.output:
        path = write_report(text, args.output)
        print(f"report written to {path}")
    else:
        print(text)
    return 0


def cmd_history(args, engine):
    with make_session_factory(engine)() as session:
        runs = session.scalars(
            select(ControlRun).order_by(ControlRun.id.desc()).limit(args.limit)
        ).all()
    if not runs:
        print("no runs yet")
        return 0
    print(f"{'run':<6}{'started (UTC)':<22}{'status':<9}exceptions")
    for r in runs:
        started = r.started_at.strftime("%Y-%m-%d %H:%M:%S")
        print(f"{r.id:<6}{started:<22}{r.status:<9}{r.total_exceptions}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="controls_monitor")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run all enabled controls")
    run.add_argument("--config", help="path to a controls YAML file")
    run.add_argument("--fail-on", choices=sorted(SEVERITY_ORDER, key=SEVERITY_ORDER.get),
                     help="override fail_on_severity from the config")
    run.add_argument("--report", help="also write a markdown report to this path")
    run.set_defaults(func=cmd_run)

    rep = sub.add_parser("report", help="build a markdown report for a stored run")
    rep.add_argument("--run-id", type=int, help="default: the latest run")
    rep.add_argument("--output", help="write to this file instead of printing")
    rep.add_argument("--max-rows", type=int, default=20,
                     help="exception rows shown per control")
    rep.set_defaults(func=cmd_report)

    hist = sub.add_parser("history", help="show recent runs")
    hist.add_argument("--limit", type=int, default=10)
    hist.set_defaults(func=cmd_history)
    return parser


def main(argv=None, engine=None):
    args = build_parser().parse_args(argv)
    return args.func(args, engine or make_engine())