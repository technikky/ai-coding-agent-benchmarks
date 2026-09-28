"""The validator's own tests.

Each test here breaks exactly one thing about an otherwise-valid synthetic task and
asserts that the corresponding check fails. Without these, `agentbench validate`
printing all-PASS would only prove that it prints.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from agentbench.task import load_task
from agentbench.types import TaskValidation
from agentbench.validate import validate_task

pytestmark = pytest.mark.slow


def failed_check_names(validation: TaskValidation) -> set[str]:
    return {check.name for check in validation.failures}


def test_the_factory_default_is_a_valid_task(write_python_task: Callable[..., Path]) -> None:
    # Everything below depends on this baseline being clean.
    validation = validate_task(load_task(write_python_task()))
    assert validation.valid, failed_check_names(validation)


def test_a_pre_solved_task_is_rejected(write_python_task: Callable[..., Path]) -> None:
    """The check that matters most: a fail-to-pass test that already passes."""
    task_dir = write_python_task(
        workspace_body="def double(value: int) -> int:\n    return value * 2\n",
    )
    validation = validate_task(load_task(task_dir))

    assert not validation.valid
    assert "base-fail-to-pass-fails" in failed_check_names(validation)
    detail = next(c.detail for c in validation.checks if c.name == "base-fail-to-pass-fails")
    assert "pre-solved" in detail


def test_a_reference_that_does_not_fix_the_defect_is_rejected(
    write_python_task: Callable[..., Path],
) -> None:
    task_dir = write_python_task(
        solution_body="def double(value: int) -> int:\n    return value\n",
    )
    validation = validate_task(load_task(task_dir))

    assert not validation.valid
    assert "solution-resolves" in failed_check_names(validation)


def test_a_reference_that_regresses_a_pass_to_pass_test_is_rejected(
    write_python_task: Callable[..., Path],
) -> None:
    # Fixes negatives, breaks positives.
    task_dir = write_python_task(
        solution_body=(
            "def double(value: int) -> int:\n"
            "    if value < 0:\n"
            "        return value * 2\n"
            "    return 0\n"
        ),
    )
    validation = validate_task(load_task(task_dir))

    assert not validation.valid
    detail = next(c.detail for c in validation.checks if c.name == "solution-resolves")
    assert "regresses pass-to-pass" in detail


def test_a_typo_in_a_declared_test_name_is_rejected(
    write_python_task: Callable[..., Path],
) -> None:
    """A misdeclared test silently shrinks the graded set, so it must be an error."""
    task_dir = write_python_task(fail_to_pass=["test_doubles_a_negatve_number"])
    validation = validate_task(load_task(task_dir))

    assert not validation.valid
    assert "tests-declared" in failed_check_names(validation)


def test_a_workspace_already_failing_a_pass_to_pass_test_is_rejected(
    write_python_task: Callable[..., Path],
) -> None:
    task_dir = write_python_task(
        workspace_body="def double(value: int) -> int:\n    raise RuntimeError('broken')\n",
    )
    validation = validate_task(load_task(task_dir))

    assert not validation.valid
    assert "base-pass-to-pass-passes" in failed_check_names(validation)


def test_a_reference_identical_to_the_workspace_is_rejected(
    write_python_task: Callable[..., Path],
) -> None:
    body = (
        "def double(value: int) -> int:\n"
        "    if value < 0:\n"
        "        return 0\n"
        "    return value * 2\n"
    )
    task_dir = write_python_task(workspace_body=body, solution_body=body)
    validation = validate_task(load_task(task_dir))

    assert not validation.valid
    assert "solution-differs" in failed_check_names(validation)


def test_a_task_with_a_weak_specification_is_rejected(
    write_python_task: Callable[..., Path],
) -> None:
    task_dir = write_python_task(spec_text="# Double\n\nMake it work.\n")
    validation = validate_task(load_task(task_dir))

    assert not validation.valid
    assert "spec-lint" in failed_check_names(validation)


def test_a_missing_entrypoint_file_stops_before_running_tests(
    write_python_task: Callable[..., Path],
) -> None:
    task_dir = write_python_task()
    (task_dir / "workspace" / "doubling.py").unlink()

    validation = validate_task(load_task(task_dir))

    assert not validation.valid
    assert "structure" in failed_check_names(validation)
    # Executing tests against an incomplete task yields noise, not information.
    assert "tests-executed" in failed_check_names(validation)


def test_duplicate_test_filenames_are_rejected(write_python_task: Callable[..., Path]) -> None:
    # pytest cannot import two same-named test modules from non-package directories.
    task_dir = write_python_task()
    (task_dir / "tests" / "hidden" / "test_hidden_double.py").rename(
        task_dir / "tests" / "hidden" / "test_public_double.py"
    )
    validation = validate_task(load_task(task_dir))

    assert not validation.valid
    assert "structure" in failed_check_names(validation)


def test_the_digest_changes_when_a_hidden_test_changes(
    write_python_task: Callable[..., Path],
) -> None:
    task_dir = write_python_task()
    before = load_task(task_dir).digest()

    hidden = task_dir / "tests" / "hidden" / "test_hidden_double.py"
    hidden.write_text(
        hidden.read_text(encoding="utf-8") + "\n# an added comment\n", encoding="utf-8"
    )

    assert load_task(task_dir).digest() != before
