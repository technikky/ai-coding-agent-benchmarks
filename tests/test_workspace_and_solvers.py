from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from agentbench.solvers import CommandSolver, NoopSolver, ReferenceSolver, build_solver
from agentbench.task import load_task
from agentbench.workspace import sandbox

# --- sandbox composition ----------------------------------------------------------


def test_the_sandbox_holds_the_workspace_the_spec_and_public_tests(
    write_python_task: Callable[..., Path],
) -> None:
    task = load_task(write_python_task())
    with sandbox(task) as box:
        assert (box.path / "doubling.py").is_file()
        assert (box.path / "SPEC.md").is_file()
        assert (box.path / "tests" / "public").is_dir()


def test_graded_tests_are_absent_until_added(write_python_task: Callable[..., Path]) -> None:
    task = load_task(write_python_task())
    with sandbox(task) as box:
        assert not box.has_hidden_tests
        assert not (box.path / "tests" / "hidden").exists()

        box.add_hidden_tests()
        assert box.has_hidden_tests
        assert (box.path / "tests" / "hidden" / "test_hidden_double.py").is_file()


def test_adding_graded_tests_twice_is_harmless(write_python_task: Callable[..., Path]) -> None:
    task = load_task(write_python_task())
    with sandbox(task) as box:
        box.add_hidden_tests()
        box.add_hidden_tests()
        assert box.has_hidden_tests


def test_include_hidden_materialises_them_up_front(
    write_python_task: Callable[..., Path],
) -> None:
    task = load_task(write_python_task())
    with sandbox(task, include_hidden=True) as box:
        assert (box.path / "tests" / "hidden").is_dir()


def test_applying_the_solution_overwrites_the_workspace(
    write_python_task: Callable[..., Path],
) -> None:
    task = load_task(write_python_task())
    with sandbox(task) as box:
        before = (box.path / "doubling.py").read_text(encoding="utf-8")
        box.apply_solution()
        after = (box.path / "doubling.py").read_text(encoding="utf-8")

    assert before != after
    assert "return value * 2" in after


def test_the_sandbox_is_removed_afterwards(write_python_task: Callable[..., Path]) -> None:
    task = load_task(write_python_task())
    with sandbox(task) as box:
        path = box.path
        assert path.is_dir()
    assert not path.exists()


def test_a_sandbox_can_be_placed_under_a_chosen_parent(
    write_python_task: Callable[..., Path], tmp_path: Path
) -> None:
    # The vitest runner relies on this to put sandboxes beside an installed
    # node_modules.
    task = load_task(write_python_task())
    parent = tmp_path / "runtime"
    with sandbox(task, parent=parent) as box:
        assert box.path.parent == parent.resolve() or box.path.parent == parent


# --- change detection -------------------------------------------------------------


def test_an_untouched_sandbox_reports_no_changes(
    write_python_task: Callable[..., Path],
) -> None:
    task = load_task(write_python_task())
    with sandbox(task) as box:
        assert box.files_differing_from_workspace() == []


def test_a_modified_file_is_reported(write_python_task: Callable[..., Path]) -> None:
    task = load_task(write_python_task())
    with sandbox(task) as box:
        (box.path / "doubling.py").write_text("# edited\n", encoding="utf-8")
        assert box.files_differing_from_workspace() == ["doubling.py"]


def test_a_new_file_is_reported(write_python_task: Callable[..., Path]) -> None:
    task = load_task(write_python_task())
    with sandbox(task) as box:
        (box.path / "helper.py").write_text("x = 1\n", encoding="utf-8")
        assert "helper.py" in box.files_differing_from_workspace()


def test_tests_and_the_spec_are_not_counted_as_changes(
    write_python_task: Callable[..., Path],
) -> None:
    task = load_task(write_python_task())
    with sandbox(task) as box:
        box.add_hidden_tests()
        (box.path / "SPEC.md").write_text("scribbled\n", encoding="utf-8")
        assert box.files_differing_from_workspace() == []


# --- solvers ----------------------------------------------------------------------


def test_the_noop_solver_changes_nothing(write_python_task: Callable[..., Path]) -> None:
    task = load_task(write_python_task())
    with sandbox(task) as box:
        outcome = NoopSolver().solve(box, timeout_s=10)
        assert outcome.ok
        assert box.files_differing_from_workspace() == []


def test_the_reference_solver_applies_the_solution(
    write_python_task: Callable[..., Path],
) -> None:
    task = load_task(write_python_task())
    with sandbox(task) as box:
        outcome = ReferenceSolver().solve(box, timeout_s=10)
        assert outcome.ok
        assert box.files_differing_from_workspace() == ["doubling.py"]


def test_the_command_solver_runs_in_the_sandbox(
    write_python_task: Callable[..., Path],
) -> None:
    task = load_task(write_python_task())
    script = (
        "import pathlib; "
        "pathlib.Path('doubling.py').write_text('def double(v):\\n    return v * 2\\n')"
    )
    solver = CommandSolver(f'"{sys.executable}" -c "{script}"')
    with sandbox(task) as box:
        outcome = solver.solve(box, timeout_s=60)
        assert outcome.ok, outcome.note
        assert box.files_differing_from_workspace() == ["doubling.py"]


def test_the_command_solver_records_a_non_zero_exit(
    write_python_task: Callable[..., Path],
) -> None:
    task = load_task(write_python_task())
    solver = CommandSolver(f'"{sys.executable}" -c "raise SystemExit(3)"')
    with sandbox(task) as box:
        outcome = solver.solve(box, timeout_s=60)
    assert not outcome.ok
    assert "exited 3" in outcome.note


def test_the_command_solver_substitutes_the_spec_path(
    write_python_task: Callable[..., Path],
) -> None:
    task = load_task(write_python_task())
    script = (
        "import pathlib, sys; pathlib.Path('seen.txt').write_text(pathlib.Path(sys.argv[1]).name)"
    )
    # Doubled braces keep {spec} literal, for CommandSolver itself to substitute.
    solver = CommandSolver(f'"{sys.executable}" -c "{script}" {{spec}}')
    with sandbox(task) as box:
        solver.solve(box, timeout_s=60)
        assert (box.path / "seen.txt").read_text(encoding="utf-8") == "SPEC.md"


def test_an_empty_command_is_rejected() -> None:
    with pytest.raises(ValueError, match="--command must not be empty"):
        CommandSolver("   ")


def test_build_solver_returns_the_named_solver() -> None:
    assert build_solver("noop").name == "noop"
    assert build_solver("reference").name == "reference"
    assert build_solver("command", command="echo hi").name == "command"


def test_build_solver_rejects_an_unknown_name() -> None:
    with pytest.raises(ValueError, match="unknown solver"):
        build_solver("magic")
