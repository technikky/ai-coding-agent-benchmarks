"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agentbench.calibrate import DEFAULT_BAND, calibrate, load_runs, write_report
from agentbench.grade import grade_tasks
from agentbench.report import (
    calibration_to_markdown,
    run_to_markdown,
    validations_to_markdown,
    write_run,
    write_validations,
)
from agentbench.runners.base import RunnerError
from agentbench.solvers import build_solver
from agentbench.spec_lint import errors as spec_errors
from agentbench.spec_lint import lint_task
from agentbench.task import discover_tasks
from agentbench.validate import validate_tasks

DEFAULT_TASKS_ROOT = "tasks"
LANGUAGES = ("python", "typescript")
SOLVERS = ("noop", "reference", "command")


def _add_selection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tasks-root", default=DEFAULT_TASKS_ROOT, help="directory holding tasks")
    parser.add_argument(
        "--language", choices=LANGUAGES, default=None, help="restrict to one language"
    )
    parser.add_argument(
        "--task", action="append", dest="task_ids", default=None, help="task id (repeatable)"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentbench",
        description="Author, validate and run benchmark tasks for AI coding agents.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("list", help="list discovered tasks")
    _add_selection_args(listing)

    lint = sub.add_parser("lint", help="lint task specifications without running any tests")
    _add_selection_args(lint)

    validate = sub.add_parser(
        "validate", help="check that each task is a usable benchmark item (runs tests)"
    )
    _add_selection_args(validate)
    validate.add_argument("--out", default=None, help="directory for validation.json and .md")
    validate.add_argument("--cache-dir", default=None, help="where to keep the TypeScript runtime")

    grade = sub.add_parser("grade", help="run a solver over the task set and grade it")
    _add_selection_args(grade)
    grade.add_argument("--solver", choices=SOLVERS, default="reference")
    grade.add_argument(
        "--command",
        dest="solver_command",
        default=None,
        help="shell command for --solver command; {spec} and {workspace}",
    )
    grade.add_argument("--out", default=None, help="directory for run.json and run.md")
    grade.add_argument("--cache-dir", default=None, help="where to keep the TypeScript runtime")
    grade.add_argument(
        "--expect-resolve-rate",
        type=float,
        default=None,
        help="exit non-zero unless the resolve rate equals this exactly; used by CI to "
        "assert noop=0.0 and reference=1.0",
    )

    calibrate_cmd = sub.add_parser(
        "calibrate", help="aggregate solve rates across runs and flag tasks outside the band"
    )
    calibrate_cmd.add_argument(
        "runs", nargs="+", help="run.json files, or directories containing them"
    )
    calibrate_cmd.add_argument("--band", nargs=2, type=float, default=list(DEFAULT_BAND))
    calibrate_cmd.add_argument("--out", default=None, help="directory for calibration.json")
    calibrate_cmd.add_argument(
        "--fail-outside-band",
        action="store_true",
        help="exit non-zero if any task falls outside the target band",
    )

    return parser


def _cmd_list(args: argparse.Namespace) -> int:
    tasks = discover_tasks(args.tasks_root, language=args.language, task_ids=args.task_ids)
    if not tasks:
        print("no tasks found", file=sys.stderr)
        return 1
    width = max(len(t.id) for t in tasks)
    print(f"{'task'.ljust(width)}  lang        kind       diff     F2P  P2P  title")
    for task in tasks:
        spec = task.spec
        print(
            f"{task.id.ljust(width)}  {spec.language[:10].ljust(10)}  {spec.kind[:9].ljust(9)}  "
            f"{spec.difficulty[:6].ljust(6)}  {len(spec.fail_to_pass):>4} "
            f"{len(spec.pass_to_pass):>4}  {spec.title}"
        )
    print(f"\n{len(tasks)} task(s)")
    return 0


def _cmd_lint(args: argparse.Namespace) -> int:
    tasks = discover_tasks(args.tasks_root, language=args.language, task_ids=args.task_ids)
    failed = 0
    for task in tasks:
        findings = lint_task(task)
        hard = spec_errors(findings)
        status = "FAIL" if hard else "ok"
        print(f"{status:4}  {task.id}")
        for finding in findings:
            print(f"        {finding}")
        if hard:
            failed += 1
    print(f"\n{len(tasks) - failed} of {len(tasks)} specifications clean")
    return 1 if failed else 0


def _cmd_validate(args: argparse.Namespace) -> int:
    tasks = discover_tasks(args.tasks_root, language=args.language, task_ids=args.task_ids)
    validations = validate_tasks(tasks, cache_dir=args.cache_dir)

    if args.out:
        paths = write_validations(validations, args.out)
        print(f"wrote {paths['json']}")
        print(f"wrote {paths['markdown']}")
    else:
        print(validations_to_markdown(validations))

    invalid = [v for v in validations if not v.valid]
    if invalid:
        print(
            f"\n{len(invalid)} invalid task(s): {', '.join(v.task_id for v in invalid)}",
            file=sys.stderr,
        )
        return 1
    return 0


def _cmd_grade(args: argparse.Namespace) -> int:
    tasks = discover_tasks(args.tasks_root, language=args.language, task_ids=args.task_ids)
    solver = build_solver(args.solver, command=args.solver_command)
    run = grade_tasks(tasks, solver, cache_dir=args.cache_dir, command=args.solver_command)

    if args.out:
        paths = write_run(run, args.out)
        print(f"wrote {paths['json']}")
        print(f"wrote {paths['markdown']}")
    else:
        print(run_to_markdown(run))

    if args.expect_resolve_rate is not None:
        actual = run.resolve_rate
        if actual is None:
            print("FAIL: no tasks were graded", file=sys.stderr)
            return 1
        if abs(actual - args.expect_resolve_rate) > 1e-9:
            print(
                f"FAIL: resolve rate {actual:.3f} != expected {args.expect_resolve_rate:.3f}. "
                f"For the noop solver this means a task is pre-solved; for the reference "
                f"solver it means a reference solution does not satisfy its own spec.",
                file=sys.stderr,
            )
            return 1
    return 0


def _cmd_calibrate(args: argparse.Namespace) -> int:
    runs = load_runs([Path(p) for p in args.runs])
    low, high = args.band
    report = calibrate(runs, band=(low, high))

    print(calibration_to_markdown(report))
    if args.out:
        print(f"wrote {write_report(report, args.out)}")

    if args.fail_outside_band and report.needs_rework:
        print(
            f"FAIL: {len(report.needs_rework)} task(s) outside the band: "
            f"{', '.join(r.task_id for r in report.needs_rework)}",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "list": _cmd_list,
        "lint": _cmd_lint,
        "validate": _cmd_validate,
        "grade": _cmd_grade,
        "calibrate": _cmd_calibrate,
    }
    try:
        return handlers[args.command](args)
    except (FileNotFoundError, ValueError, KeyError, RunnerError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
