import argparse
import sys
from sqlalchemy import select
from controls_monitor.config import SEVERITY_ORDER, ConfigError, load_config
from controls_monitor.db import make_engine, make_session_factory
from controls_monitor.models import ControlRun
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
    code = exit_code(summary, fail_on)
    print(format_summary(summary, fail_on, code))
    return code


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
    run.set_defaults(func=cmd_run)

    hist = sub.add_parser("history", help="show recent runs")
    hist.add_argument("--limit", type=int, default=10)
    hist.set_defaults(func=cmd_history)
    return parser


def main(argv=None, engine=None):
    args = build_parser().parse_args(argv)
    return args.func(args, engine or make_engine())