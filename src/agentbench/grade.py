"""Grading a solver's attempt.

Resolution is all-or-nothing, deliberately. A task is resolved when every fail-to-pass
test passes **and** every pass-to-pass test still passes. Partial credit on
fail-to-pass would reward an agent for satisfying the easy half of a specification, and
dropping the pass-to-pass requirement would reward one for deleting the assertions that
got in its way.

The fail-to-pass and pass-to-pass counts are still reported, because "7 of 8, and it
broke nothing" and "1 of 8" are very different failures when you are calibrating a task.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agentbench.runners import TestRunner, build_runner
from agentbench.runners.base import RunnerError
from agentbench.solvers import Solver
from agentbench.task import Task
from agentbench.types import RunGrade, TaskGrade
from agentbench.workspace import sandbox


def _version() -> str:
    from agentbench import __version__

    return __version__


def grade_task(
    task: Task,
    solver: Solver,
    *,
    cache_dir: str | Path | None = None,
    runner: TestRunner | None = None,
) -> TaskGrade:
    """Run a solver on one task and grade the result."""
    spec = task.spec
    empty = TaskGrade(
        task_id=task.id,
        language=task.language,
        resolved=False,
        f2p_passed=0,
        f2p_total=len(spec.fail_to_pass),
        p2p_passed=0,
        p2p_total=len(spec.pass_to_pass),
        duration_s=0.0,
    )

    try:
        active = runner or build_runner(task.language, cache_dir=cache_dir)
        parent = active.sandbox_parent()
    except RunnerError as exc:
        return empty.model_copy(update={"note": f"runner unavailable: {exc}"})

    # The solver works in a sandbox with the public tests only. The graded tests are
    # copied in afterwards, so nothing the solver can read includes them.
    with sandbox(task, parent=parent, include_hidden=False) as box:
        outcome = solver.solve(box, timeout_s=spec.timeout_s)
        changed = box.files_differing_from_workspace()

        box.add_hidden_tests()
        result = active.run(box.path, label="candidate", timeout_s=spec.timeout_s)

    if result.runner_error:
        return empty.model_copy(
            update={
                "duration_s": outcome.duration_s,
                "note": f"test run failed: {result.runner_error}",
            }
        )

    missing = result.missing(spec.all_test_names)
    f2p_passed = result.passed_count(spec.fail_to_pass)
    p2p_passed = result.passed_count(spec.pass_to_pass)
    resolved = (
        not missing
        and f2p_passed == len(spec.fail_to_pass)
        and p2p_passed == len(spec.pass_to_pass)
    )

    notes = [outcome.note] if outcome.note else []
    if missing:
        # Usually the solver deleted or renamed a test file. Treated as unresolved.
        notes.append(f"tests not collected: {', '.join(missing)}")
    if changed:
        notes.append(f"changed {len(changed)} file(s): {', '.join(changed[:5])}")
    else:
        notes.append("changed no files")

    return TaskGrade(
        task_id=task.id,
        language=task.language,
        resolved=resolved,
        f2p_passed=f2p_passed,
        f2p_total=len(spec.fail_to_pass),
        p2p_passed=p2p_passed,
        p2p_total=len(spec.pass_to_pass),
        duration_s=outcome.duration_s + result.duration_s,
        missing_tests=missing,
        note="; ".join(notes),
    )


def grade_tasks(
    tasks: list[Task],
    solver: Solver,
    *,
    cache_dir: str | Path | None = None,
    command: str | None = None,
) -> RunGrade:
    """Grade a solver across a task set, reusing one runner per language."""
    runners: dict[str, TestRunner] = {}
    grades: list[TaskGrade] = []

    for task in tasks:
        if task.language not in runners:
            runners[task.language] = build_runner(task.language, cache_dir=cache_dir)
        grades.append(grade_task(task, solver, cache_dir=cache_dir, runner=runners[task.language]))

    return RunGrade(
        solver=solver.name,
        created_at=datetime.now(timezone.utc).isoformat(),
        harness_version=_version(),
        command=command,
        tasks=grades,
    )
