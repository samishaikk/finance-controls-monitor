import argparse
import logging
import sys
from sqlalchemy import select
from controls_monitor.config import SEVERITY_ORDER, ConfigError, load_config
from controls_monitor.db import make_engine, make_session_factory
from controls_monitor.evaluation import (
    EvaluationError,
    evaluate_run,
    format_markdown,
    format_table,
)
from controls_monitor.logging_setup import configure_logging, log_event
from controls_monitor.metrics import MetricsError, render, write_metrics
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


logger = logging.getLogger("controls_monitor.cli")


def cmd_run(args, engine):
    configure_logging(args.log_level)
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return EXIT_ERROR
    fail_on = args.fail_on or config.fail_on_severity
    with make_session_factory(engine)() as session:
        summary = run_all(session, config)
        report_path = metrics_path = None
        if args.report:
            report_path = write_report(build_report(session, summary.run_id), args.report)
        if args.metrics:
            metrics_path = write_metrics(session, summary.run_id, args.metrics)
    code = exit_code(summary, fail_on)
    print(format_summary(summary, fail_on, code))
    for label, path in (("report", report_path), ("metrics", metrics_path)):
        if path:
            print(f"{label} written to {path}")
            log_event(logger, f"{label}_written", run_id=summary.run_id, path=str(path))
    return code


def cmd_evaluate(args, engine):
    configure_logging(args.log_level)
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return EXIT_ERROR
    with make_session_factory(engine)() as session:
        summary = run_all(session, config)
        try:
            scores = evaluate_run(session, summary.run_id)
        except EvaluationError as exc:
            print(exc, file=sys.stderr)
            return EXIT_ERROR
        markdown = format_markdown(scores, summary.run_id)
    print(f"evaluation of run {summary.run_id} against the planted cases")
    print()
    print(format_table(scores))
    if args.output:
        path = write_report(markdown, args.output)
        print()
        print(f"evaluation written to {path}")
    return 0


def cmd_metrics(args, engine):
    with make_session_factory(engine)() as session:
        run_id = args.run_id or latest_run_id(session)
        if run_id is None:
            print("no runs yet - run the monitor first", file=sys.stderr)
            return EXIT_ERROR
        try:
            if args.output:
                path = write_metrics(session, run_id, args.output)
                print(f"metrics written to {path}")
            else:
                print(render(session, run_id), end="")
        except MetricsError as exc:
            print(exc, file=sys.stderr)
            return EXIT_ERROR
    return 0


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
    run.add_argument("--metrics", help="also write Prometheus metrics (.prom) to this path")
    run.add_argument("--log-level", default="INFO",
                     choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                     help="JSON log level on stderr (default INFO)")
    run.set_defaults(func=cmd_run)

    ev = sub.add_parser("evaluate", help="run the monitor and score it against the planted cases")
    ev.add_argument("--config", help="path to a controls YAML file")
    ev.add_argument("--output", help="also write the evaluation as markdown to this path")
    ev.add_argument("--log-level", default="WARNING",
                    choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                    help="JSON log level on stderr (default WARNING)")
    ev.set_defaults(func=cmd_evaluate)

    met = sub.add_parser("metrics", help="print or write Prometheus metrics for a stored run")
    met.add_argument("--run-id", type=int, help="default: the latest run")
    met.add_argument("--output", help="write to this file instead of printing")
    met.set_defaults(func=cmd_metrics)

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