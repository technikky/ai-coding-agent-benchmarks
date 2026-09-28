"""Task validation: is this item a usable benchmark task at all?

The six checks below are the difference between authoring a benchmark and writing
tests. Each one corresponds to a way a task can look finished and measure nothing:

============================  ==========================================================
Check                         The authoring bug it catches
============================  ==========================================================
structure                     Files referenced but absent; colliding test filenames.
spec-lint                     A specification that defers a decision the tests grade.
tests-declared                A typo in ``task.json``, so a graded test never runs and
                              the task silently grades on fewer assertions.
base-fail-to-pass-fails       **The important one.** If a fail-to-pass test already
                              passes on the starting workspace, the task is already
                              solved and its solve rate is 100% for reasons that have
                              nothing to do with the agent.
base-pass-to-pass-passes      The starting workspace is broken beyond the intended
                              defect, so an agent must fix something the spec never
                              mentioned.
solution-resolves             The reference solution does not satisfy its own
                              specification, so the task is unsolvable as written.
============================  ==========================================================

What this cannot check is whether the specification is *unambiguous*. The only real
test for that is implementing it blind from the instructions alone and seeing whether
the hidden tests pass; ``spec_lint`` catches recurring smells, not meaning.
"""

from __future__ import annotations

from pathlib import Path

from agentbench.runners import TestRunner, build_runner
from agentbench.runners.base import RunnerError
from agentbench.spec_lint import errors as spec_errors
from agentbench.spec_lint import lint_task
from agentbench.spec_lint import warnings as spec_warnings
from agentbench.task import Task
from agentbench.types import Check, SuiteResult, TaskValidation
from agentbench.workspace import sandbox


def _structure_check(task: Task) -> Check:
    problems = task.structure_problems()
    return Check(
        name="structure",
        passed=not problems,
        detail="task layout is complete" if not problems else "; ".join(problems),
    )


def _spec_check(task: Task) -> Check:
    findings = lint_task(task)
    hard = spec_errors(findings)
    soft = spec_warnings(findings)
    if hard:
        return Check(name="spec-lint", passed=False, detail="; ".join(str(f) for f in hard))
    detail = "specification passes the linter"
    if soft:
        detail += f" ({len(soft)} warning(s): " + "; ".join(str(f) for f in soft) + ")"
    return Check(name="spec-lint", passed=True, detail=detail)


def _declared_tests_check(task: Task, base: SuiteResult) -> Check:
    missing = base.missing(task.spec.all_test_names)
    duplicates = [name for name in base.duplicate_names() if name in task.spec.all_test_names]

    problems: list[str] = []
    if missing:
        problems.append(f"declared but never collected: {', '.join(missing)}")
    if duplicates:
        problems.append(
            f"collected more than once, so name-based selection is ambiguous: "
            f"{', '.join(duplicates)}"
        )
    return Check(
        name="tests-declared",
        passed=not problems,
        detail=(
            f"all {len(task.spec.all_test_names)} declared tests collected exactly once"
            if not problems
            else "; ".join(problems)
        ),
    )


def _base_f2p_check(task: Task, base: SuiteResult) -> Check:
    already_passing = [name for name in task.spec.fail_to_pass if base.status_of(name) == "passed"]
    return Check(
        name="base-fail-to-pass-fails",
        passed=not already_passing,
        detail=(
            f"all {len(task.spec.fail_to_pass)} fail-to-pass tests fail before the fix"
            if not already_passing
            else (
                "these fail-to-pass tests already pass on the starting workspace, so the "
                f"task is pre-solved: {', '.join(already_passing)}"
            )
        ),
    )


def _base_p2p_check(task: Task, base: SuiteResult) -> Check:
    if not task.spec.pass_to_pass:
        return Check(name="base-pass-to-pass-passes", passed=True, detail="no pass-to-pass tests")
    broken = [name for name in task.spec.pass_to_pass if base.status_of(name) != "passed"]
    return Check(
        name="base-pass-to-pass-passes",
        passed=not broken,
        detail=(
            f"all {len(task.spec.pass_to_pass)} pass-to-pass tests pass before the fix"
            if not broken
            else f"already failing on the starting workspace: {', '.join(broken)}"
        ),
    )


def _solution_check(task: Task, solved: SuiteResult) -> Check:
    failing_f2p = [name for name in task.spec.fail_to_pass if solved.status_of(name) != "passed"]
    failing_p2p = [name for name in task.spec.pass_to_pass if solved.status_of(name) != "passed"]

    problems: list[str] = []
    if failing_f2p:
        problems.append(
            f"fail-to-pass still failing after the reference fix: {', '.join(failing_f2p)}"
        )
    if failing_p2p:
        problems.append(f"reference fix regresses pass-to-pass: {', '.join(failing_p2p)}")
    return Check(
        name="solution-resolves",
        passed=not problems,
        detail=(
            "the reference solution passes every declared test"
            if not problems
            else "; ".join(problems)
        ),
    )


def _solution_changes_check(task: Task) -> Check:
    """The reference must actually modify the workspace."""
    changed: list[str] = []
    for path in sorted(task.solution_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(task.solution_dir)
        original = task.workspace_dir / relative
        if not original.is_file() or original.read_bytes() != path.read_bytes():
            changed.append(relative.as_posix())
    return Check(
        name="solution-differs",
        passed=bool(changed),
        detail=(
            f"reference changes {', '.join(changed)}"
            if changed
            else "solution/ is byte-identical to workspace/, so it fixes nothing"
        ),
    )


def validate_task(
    task: Task,
    *,
    cache_dir: str | Path | None = None,
    runner: TestRunner | None = None,
) -> TaskValidation:
    """Run every validation check on one task."""
    validation = TaskValidation(task_id=task.id, language=task.language, digest=task.digest())

    structure = _structure_check(task)
    validation.checks.append(structure)
    validation.checks.append(_spec_check(task))

    if not structure.passed:
        # Executing tests against an incomplete task produces confusing errors rather
        # than useful ones, so stop here and report the structural problem.
        validation.checks.append(
            Check(name="tests-executed", passed=False, detail="skipped: task layout is incomplete")
        )
        return validation

    validation.checks.append(_solution_changes_check(task))

    try:
        active = runner or build_runner(task.language, cache_dir=cache_dir)
        parent = active.sandbox_parent()

        with sandbox(task, parent=parent, include_hidden=True) as box:
            base = active.run(box.path, label="base", timeout_s=task.spec.timeout_s)

        with sandbox(task, parent=parent, include_hidden=True, apply_solution=True) as box:
            solved = active.run(box.path, label="solution", timeout_s=task.spec.timeout_s)
    except RunnerError as exc:
        validation.checks.append(
            Check(name="tests-executed", passed=False, detail=f"runner unavailable: {exc}")
        )
        return validation

    for label, result in (("base", base), ("solution", solved)):
        if result.runner_error:
            validation.checks.append(
                Check(
                    name=f"{label}-run",
                    passed=False,
                    detail=f"the {label} test run failed: {result.runner_error}",
                )
            )
            return validation

    validation.checks.append(_declared_tests_check(task, base))
    validation.checks.append(_base_f2p_check(task, base))
    validation.checks.append(_base_p2p_check(task, base))
    validation.checks.append(_solution_check(task, solved))
    return validation


def validate_tasks(
    tasks: list[Task], *, cache_dir: str | Path | None = None
) -> list[TaskValidation]:
    """Validate several tasks, reusing one runner per language."""
    runners: dict[str, TestRunner] = {}
    results: list[TaskValidation] = []
    for task in tasks:
        if task.language not in runners:
            runners[task.language] = build_runner(task.language, cache_dir=cache_dir)
        results.append(validate_task(task, cache_dir=cache_dir, runner=runners[task.language]))
    return results
