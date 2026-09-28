from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from agentbench.cli import main
from tests.conftest import TASKS_ROOT

TASKS = str(TASKS_ROOT)


def test_list_prints_every_task(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["list", "--tasks-root", TASKS]) == 0
    out = capsys.readouterr().out
    assert "py-001-interval-merge" in out
    assert "ts-002-cart-total" in out
    assert "4 task(s)" in out


def test_list_honours_the_language_filter(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["list", "--tasks-root", TASKS, "--language", "python"]) == 0
    out = capsys.readouterr().out
    assert "py-001-interval-merge" in out
    assert "ts-001-debounce" not in out


def test_list_honours_repeated_task_filters(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(
        [
            "list",
            "--tasks-root",
            TASKS,
            "--task",
            "py-001-interval-merge",
            "--task",
            "ts-001-debounce",
        ]
    )
    assert exit_code == 0
    assert "2 task(s)" in capsys.readouterr().out


def test_lint_passes_on_the_shipped_specifications(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["lint", "--tasks-root", TASKS]) == 0
    assert "4 of 4 specifications clean" in capsys.readouterr().out


def test_lint_fails_on_a_weak_specification(
    write_python_task: Callable[..., Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "tasks"
    write_python_task(spec_text="# Thin\n\nDo the thing.\n", root=root)

    assert main(["lint", "--tasks-root", str(root)]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_an_unknown_task_id_exits_two(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["list", "--tasks-root", TASKS, "--task", "nope"]) == 2
    assert "unknown task id" in capsys.readouterr().err


def test_a_missing_tasks_root_exits_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["list", "--tasks-root", str(tmp_path / "gone")]) == 2
    assert "tasks root not found" in capsys.readouterr().err


def test_no_subcommand_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2


@pytest.mark.slow
def test_validate_writes_its_artifacts(
    write_python_task: Callable[..., Path], tmp_path: Path
) -> None:
    root = tmp_path / "tasks"
    write_python_task(root=root)
    out = tmp_path / "out"

    assert main(["validate", "--tasks-root", str(root), "--out", str(out)]) == 0
    assert (out / "validation.json").is_file()
    assert (out / "validation.md").is_file()


@pytest.mark.slow
def test_validate_exits_one_for_an_invalid_task(
    write_python_task: Callable[..., Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "tasks"
    # Pre-solved: the graded test already passes on the starting workspace.
    write_python_task(
        workspace_body="def double(value: int) -> int:\n    return value * 2\n", root=root
    )

    assert main(["validate", "--tasks-root", str(root)]) == 1
    assert "invalid task(s)" in capsys.readouterr().err


@pytest.mark.slow
def test_grade_writes_a_run_report(write_python_task: Callable[..., Path], tmp_path: Path) -> None:
    root = tmp_path / "tasks"
    write_python_task(root=root)
    out = tmp_path / "run"

    assert (
        main(["grade", "--tasks-root", str(root), "--solver", "reference", "--out", str(out)]) == 0
    )
    payload = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert payload["solver"] == "reference"
    assert payload["tasks"][0]["resolved"] is True


@pytest.mark.slow
def test_grade_enforces_the_expected_resolve_rate(
    write_python_task: Callable[..., Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "tasks"
    write_python_task(root=root)

    # noop must resolve nothing, so demanding 1.0 has to fail.
    exit_code = main(
        ["grade", "--tasks-root", str(root), "--solver", "noop", "--expect-resolve-rate", "1.0"]
    )
    assert exit_code == 1
    assert "resolve rate" in capsys.readouterr().err


@pytest.mark.slow
def test_the_two_controls_hold_on_the_shipped_python_tasks() -> None:
    common = ["grade", "--tasks-root", TASKS, "--language", "python"]
    assert main([*common, "--solver", "noop", "--expect-resolve-rate", "0.0"]) == 0
    assert main([*common, "--solver", "reference", "--expect-resolve-rate", "1.0"]) == 0


@pytest.mark.slow
def test_calibrate_reads_run_reports_and_can_fail_outside_the_band(
    write_python_task: Callable[..., Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "tasks"
    write_python_task(root=root)
    runs = tmp_path / "runs"

    for name in ("a", "b"):
        assert (
            main(
                [
                    "grade",
                    "--tasks-root",
                    str(root),
                    "--solver",
                    "reference",
                    "--out",
                    str(runs / name),
                ]
            )
            == 0
        )
    capsys.readouterr()

    # The reference solver always resolves, so every task reads as too easy.
    assert main(["calibrate", str(runs)]) == 0
    assert "too easy" in capsys.readouterr().out

    assert main(["calibrate", str(runs), "--fail-outside-band"]) == 1
    assert "outside the band" in capsys.readouterr().err
