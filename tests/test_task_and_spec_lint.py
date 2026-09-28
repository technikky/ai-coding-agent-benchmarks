from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from agentbench.spec_lint import errors, lint_spec, lint_task, warnings
from agentbench.task import TaskSpec, discover_tasks, load_task
from tests.conftest import CLEAN_SPEC_TEMPLATE, TASKS_ROOT

# --- TaskSpec ---------------------------------------------------------------------


def minimal_spec(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "x-001",
        "language": "python",
        "title": "t",
        "kind": "bug_fix",
        "difficulty": "easy",
        "entrypoint_files": ["a.py"],
        "fail_to_pass": ["test_a"],
        "pass_to_pass": ["test_b"],
    }
    base.update(overrides)
    return base


def test_declared_names_are_normalised_on_load() -> None:
    spec = TaskSpec.model_validate(minimal_spec(fail_to_pass=["group > test_a"]))
    assert spec.fail_to_pass == ["test_a"]


def test_duplicate_declared_names_are_rejected() -> None:
    with pytest.raises(ValidationError, match="must not be declared twice"):
        TaskSpec.model_validate(minimal_spec(fail_to_pass=["test_a", "test_a"]))


def test_names_that_collide_after_normalisation_are_rejected() -> None:
    # Two describe blocks, one title: indistinguishable once collected.
    with pytest.raises(ValidationError, match="must not be declared twice"):
        TaskSpec.model_validate(minimal_spec(fail_to_pass=["one > test_a", "two > test_a"]))


def test_an_empty_declared_name_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        TaskSpec.model_validate(minimal_spec(fail_to_pass=["   "]))


def test_a_test_cannot_be_both_fail_to_pass_and_pass_to_pass() -> None:
    with pytest.raises(ValidationError, match="cannot be both"):
        TaskSpec.model_validate(minimal_spec(fail_to_pass=["test_a"], pass_to_pass=["test_a"]))


def test_at_least_one_fail_to_pass_test_is_required() -> None:
    with pytest.raises(ValidationError):
        TaskSpec.model_validate(minimal_spec(fail_to_pass=[]))


def test_an_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TaskSpec.model_validate(minimal_spec(entrypoint_file=["a.py"]))


def test_an_unknown_language_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TaskSpec.model_validate(minimal_spec(language="cobol"))


def test_a_non_positive_timeout_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TaskSpec.model_validate(minimal_spec(timeout_s=0))


# --- loading and discovery --------------------------------------------------------


def test_load_task_reads_a_shipped_task() -> None:
    task = load_task(TASKS_ROOT / "python" / "py-001-interval-merge")
    assert task.id == "py-001-interval-merge"
    assert task.language == "python"
    assert task.spec.entrypoint_files == ["intervals.py"]


def test_a_missing_task_json_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"no task\.json"):
        load_task(tmp_path)


def test_invalid_task_json_reports_the_line(tmp_path: Path) -> None:
    (tmp_path / "task.json").write_text("{\n  nope\n}", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        load_task(tmp_path)


def test_an_id_that_does_not_match_the_directory_is_rejected(tmp_path: Path) -> None:
    directory = tmp_path / "actual-name"
    directory.mkdir()
    (directory / "task.json").write_text(json.dumps(minimal_spec()), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match directory name"):
        load_task(directory)


def test_discovery_finds_every_shipped_task() -> None:
    tasks = discover_tasks(TASKS_ROOT)
    assert {t.id for t in tasks} >= {
        "py-001-interval-merge",
        "py-002-retry-backoff",
        "ts-001-debounce",
        "ts-002-cart-total",
    }


def test_discovery_filters_by_language() -> None:
    tasks = discover_tasks(TASKS_ROOT, language="typescript")
    assert tasks
    assert all(t.language == "typescript" for t in tasks)


def test_discovery_filters_by_task_id() -> None:
    tasks = discover_tasks(TASKS_ROOT, task_ids=["ts-002-cart-total"])
    assert [t.id for t in tasks] == ["ts-002-cart-total"]


def test_an_unknown_task_id_lists_what_is_available() -> None:
    with pytest.raises(ValueError, match="unknown task id"):
        discover_tasks(TASKS_ROOT, task_ids=["does-not-exist"])


def test_a_missing_tasks_root_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="tasks root not found"):
        discover_tasks(tmp_path / "nope")


def test_digest_is_stable_across_calls(write_python_task: Callable[..., Path]) -> None:
    task = load_task(write_python_task())
    assert task.digest() == task.digest()
    assert len(task.digest()) == 64


# --- spec lint --------------------------------------------------------------------


def lint(text: str, **kwargs: object) -> list[str]:
    findings = lint_spec(
        text,
        entrypoint_files=kwargs.pop("entrypoint_files", ["mod.py"]),  # type: ignore[arg-type]
        hidden_test_names=kwargs.pop("hidden_test_names", ["test_graded"]),  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )
    return [f.rule for f in errors(findings)]


def test_every_shipped_specification_is_clean() -> None:
    for task in discover_tasks(TASKS_ROOT):
        assert errors(lint_task(task)) == [], f"{task.id} specification has lint errors"


def test_the_synthetic_template_is_clean() -> None:
    # The negative tests depend on this, so it is asserted rather than assumed.
    findings = lint_spec(
        CLEAN_SPEC_TEMPLATE.format(entrypoint="doubling.py"),
        entrypoint_files=["doubling.py"],
        hidden_test_names=["test_doubles_a_negative_number"],
    )
    assert errors(findings) == []


def test_an_empty_specification_is_an_error() -> None:
    assert lint("   ") == ["spec-empty"]


def test_a_missing_title_is_an_error() -> None:
    assert "spec-no-title" in lint("## Context\nsome text\n")


def test_missing_required_sections_are_errors() -> None:
    rules = lint("# Title\n\nsome text\n")
    assert rules.count("spec-missing-section") == 3


def test_a_short_specification_is_an_error() -> None:
    assert "spec-too-short" in lint("# T\n## Context\n## Requirements\n## Definition of done\n")


def test_a_specification_with_no_example_is_an_error() -> None:
    body = "# Title\n## Context\n## Requirements\n## Definition of done\nmod.py " + "word " * 100
    assert "spec-no-example" in lint(body)


def test_leaking_a_graded_test_name_is_an_error() -> None:
    body = (
        "# Title\n## Context\n## Requirements\n## Definition of done\n"
        "mod.py must satisfy test_graded.\n```\nx\n```\n" + "word " * 100
    )
    assert "spec-leaks-test-name" in lint(body)


def test_never_mentioning_the_entrypoint_is_an_error() -> None:
    body = (
        "# Title\n## Context\n## Requirements\n## Definition of done\n```\nx\n```\n" + "word " * 100
    )
    assert "spec-entrypoint-unmentioned" in lint(body)


def test_mentioning_only_the_basename_of_the_entrypoint_is_accepted() -> None:
    body = (
        "# Title\n## Context\n## Requirements\n## Definition of done\n"
        "Change debounce.ts only.\n```\nx\n```\n" + "word " * 100
    )
    assert "spec-entrypoint-unmentioned" not in lint(body, entrypoint_files=["src/debounce.ts"])


def test_an_unresolved_placeholder_is_an_error() -> None:
    body = (
        "# Title\n## Context\n## Requirements\n## Definition of done\n"
        "mod.py TODO decide this\n```\nx\n```\n" + "word " * 100
    )
    assert "spec-placeholder" in lint(body)


def test_a_weasel_term_is_a_warning_not_an_error() -> None:
    body = (
        "# Title\n## Context\n## Requirements\n## Definition of done\n"
        "mod.py must handle errors appropriately.\n```\nx\n```\n" + "word " * 100
    )
    findings = lint_spec(body, entrypoint_files=["mod.py"], hidden_test_names=[])

    assert errors(findings) == []
    assert any(f.rule == "spec-weasel-term" for f in warnings(findings))


def test_a_weasel_term_inside_a_code_fence_is_ignored() -> None:
    # An exact expected output may contain any word; flagging it teaches authors to
    # ignore the linter.
    body = (
        "# Title\n## Context\n## Requirements\n## Definition of done\n"
        "mod.py does the thing.\n```\nraise ValueError('handled appropriately')\n```\n"
        + "word "
        * 100
    )
    findings = lint_spec(body, entrypoint_files=["mod.py"], hidden_test_names=[])
    assert not any(f.rule == "spec-weasel-term" for f in findings)


def test_a_warning_reports_its_line_number() -> None:
    body = (
        "# Title\n## Context\n## Requirements\n## Definition of done\n"
        "mod.py\nthis is reasonable\n```\nx\n```\n" + "word " * 100
    )
    findings = lint_spec(body, entrypoint_files=["mod.py"], hidden_test_names=[])
    weasels = [f for f in warnings(findings) if f.rule == "spec-weasel-term"]
    assert weasels and weasels[0].line == 6
