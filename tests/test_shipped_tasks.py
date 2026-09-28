"""End-to-end checks on the benchmark that actually ships.

These are the assertions that make the published resolve rates meaningful: every task
validates, the negative control resolves nothing, and the positive control resolves
everything. CI runs them on every push.
"""

from __future__ import annotations

import pytest

from agentbench.grade import grade_tasks
from agentbench.solvers import NoopSolver, ReferenceSolver
from agentbench.task import discover_tasks
from agentbench.validate import validate_tasks
from tests.conftest import TASKS_ROOT, requires_node

pytestmark = pytest.mark.slow


def test_every_task_is_discoverable_and_declares_graded_tests() -> None:
    tasks = discover_tasks(TASKS_ROOT)
    assert len(tasks) >= 4
    for task in tasks:
        assert task.spec.fail_to_pass, f"{task.id} declares no fail-to-pass tests"
        assert not task.structure_problems(), task.structure_problems()


def test_both_languages_are_represented() -> None:
    languages = {task.language for task in discover_tasks(TASKS_ROOT)}
    assert languages == {"python", "typescript"}


def test_task_ids_match_their_directories_and_are_unique() -> None:
    tasks = discover_tasks(TASKS_ROOT)
    ids = [task.id for task in tasks]
    assert len(set(ids)) == len(ids)
    for task in tasks:
        assert task.root.name == task.id


# --- python track -----------------------------------------------------------------


def test_python_tasks_validate() -> None:
    validations = validate_tasks(discover_tasks(TASKS_ROOT, language="python"))
    assert validations
    for validation in validations:
        assert validation.valid, f"{validation.task_id}: " + "; ".join(
            f"{c.name}: {c.detail}" for c in validation.failures
        )


def test_noop_resolves_no_python_task() -> None:
    """A task the do-nothing solver resolves is a task that measures nothing."""
    run = grade_tasks(discover_tasks(TASKS_ROOT, language="python"), NoopSolver())
    assert run.n_resolved == 0, [t.task_id for t in run.tasks if t.resolved]
    # Pass-to-pass must already hold, or the starting workspace is broken.
    for task in run.tasks:
        assert task.p2p_passed == task.p2p_total, task.task_id
        assert task.f2p_passed == 0, task.task_id


def test_reference_resolves_every_python_task() -> None:
    run = grade_tasks(discover_tasks(TASKS_ROOT, language="python"), ReferenceSolver())
    assert run.resolve_rate == 1.0, [t.task_id for t in run.tasks if not t.resolved]


# --- typescript track -------------------------------------------------------------


@requires_node
def test_typescript_tasks_validate() -> None:
    validations = validate_tasks(discover_tasks(TASKS_ROOT, language="typescript"))
    assert validations
    for validation in validations:
        assert validation.valid, f"{validation.task_id}: " + "; ".join(
            f"{c.name}: {c.detail}" for c in validation.failures
        )


@requires_node
def test_noop_resolves_no_typescript_task() -> None:
    run = grade_tasks(discover_tasks(TASKS_ROOT, language="typescript"), NoopSolver())
    assert run.n_resolved == 0, [t.task_id for t in run.tasks if t.resolved]
    for task in run.tasks:
        assert task.p2p_passed == task.p2p_total, task.task_id


@requires_node
def test_reference_resolves_every_typescript_task() -> None:
    run = grade_tasks(discover_tasks(TASKS_ROOT, language="typescript"), ReferenceSolver())
    assert run.resolve_rate == 1.0, [t.task_id for t in run.tasks if not t.resolved]


# --- the hidden tests really are hidden -------------------------------------------


def test_a_solver_sandbox_contains_no_graded_tests() -> None:
    """The mechanism behind "hidden": the files are simply not copied in."""
    from agentbench.runners import build_runner
    from agentbench.workspace import sandbox

    task = next(t for t in discover_tasks(TASKS_ROOT, language="python"))
    runner = build_runner("python")

    with sandbox(task, parent=runner.sandbox_parent(), include_hidden=False) as box:
        assert not (box.path / "tests" / "hidden").exists()
        assert (box.path / "tests" / "public").is_dir()
        assert box.spec_path.is_file()

        graded_names = set(task.spec.fail_to_pass)
        present = "\n".join(
            p.read_text(encoding="utf-8", errors="replace")
            for p in box.path.rglob("*")
            if p.is_file() and p.suffix in {".py", ".md", ".ts", ".json"}
        )
        leaked = sorted(name for name in graded_names if name in present)
        assert not leaked, f"graded test names reachable in the sandbox: {leaked}"

        box.add_hidden_tests()
        assert (box.path / "tests" / "hidden").is_dir()
