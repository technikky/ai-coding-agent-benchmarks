from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentbench.calibrate import calibrate, load_run, load_runs, write_report
from agentbench.report import (
    calibration_to_markdown,
    run_to_markdown,
    validations_to_markdown,
    write_run,
    write_validations,
)
from agentbench.types import Check, RunGrade, TaskGrade, TaskValidation


def grade(task_id: str, resolved: bool) -> TaskGrade:
    return TaskGrade(
        task_id=task_id,
        language="python",
        resolved=resolved,
        f2p_passed=3 if resolved else 0,
        f2p_total=3,
        p2p_passed=2,
        p2p_total=2,
        duration_s=1.5,
    )


def run(*results: tuple[str, bool], solver: str = "command") -> RunGrade:
    return RunGrade(
        solver=solver,
        created_at="2026-09-28T00:00:00+00:00",
        harness_version="0.1.0",
        command="agent --go",
        tasks=[grade(task_id, resolved) for task_id, resolved in results],
    )


# --- RunGrade arithmetic ----------------------------------------------------------


def test_resolve_rate_counts_resolved_tasks() -> None:
    assert run(("a", True), ("b", False), ("c", True), ("d", False)).resolve_rate == 0.5


def test_an_empty_run_has_no_resolve_rate() -> None:
    assert RunGrade(solver="noop", created_at="t", harness_version="0.1.0").resolve_rate is None


# --- calibration ------------------------------------------------------------------


def test_a_task_solved_every_time_is_too_easy() -> None:
    report = calibrate([run(("a", True)), run(("a", True))], band=(0.1, 0.7))
    assert report.rows[0].verdict == "too_easy"
    assert report.rows[0].solve_rate == 1.0


def test_a_task_never_solved_is_too_hard() -> None:
    report = calibrate([run(("a", False)), run(("a", False))], band=(0.1, 0.7))
    assert report.rows[0].verdict == "too_hard"


def test_a_task_solved_sometimes_is_in_band() -> None:
    runs = [run(("a", True)), run(("a", False)), run(("a", False)), run(("a", True))]
    report = calibrate(runs, band=(0.1, 0.7))
    assert report.rows[0].solve_rate == 0.5
    assert report.rows[0].verdict == "in_band"


def test_the_band_edges_are_inclusive() -> None:
    runs = [run(("a", True)), run(("a", False))]  # 0.5
    assert calibrate(runs, band=(0.5, 0.5)).rows[0].verdict == "in_band"


def test_attempts_are_counted_per_task() -> None:
    report = calibrate([run(("a", True), ("b", False)), run(("a", False))])
    rows = {row.task_id: row for row in report.rows}
    assert rows["a"].attempts == 2
    assert rows["b"].attempts == 1


def test_needs_rework_lists_only_out_of_band_tasks() -> None:
    runs = [run(("easy", True), ("mixed", True)), run(("easy", True), ("mixed", False))]
    report = calibrate(runs, band=(0.1, 0.7))
    assert [row.task_id for row in report.needs_rework] == ["easy"]


def test_an_invalid_band_is_rejected() -> None:
    with pytest.raises(ValueError, match="band must satisfy"):
        calibrate([run(("a", True))], band=(0.8, 0.2))


def test_calibration_needs_at_least_one_run() -> None:
    with pytest.raises(ValueError, match="at least one run report"):
        calibrate([])


# --- loading run reports ----------------------------------------------------------


def test_a_run_report_round_trips_through_disk(tmp_path: Path) -> None:
    original = run(("a", True), ("b", False))
    paths = write_run(original, tmp_path / "r1")
    restored = load_run(paths["json"])

    assert restored.solver == original.solver
    assert restored.resolve_rate == original.resolve_rate
    assert [t.task_id for t in restored.tasks] == ["a", "b"]


def test_load_runs_accepts_a_directory_of_runs(tmp_path: Path) -> None:
    write_run(run(("a", True)), tmp_path / "r1")
    write_run(run(("a", False)), tmp_path / "r2")

    runs = load_runs([tmp_path])
    assert len(runs) == 2


def test_load_runs_accepts_individual_files(tmp_path: Path) -> None:
    first = write_run(run(("a", True)), tmp_path / "r1")["json"]
    assert len(load_runs([first])) == 1


def test_a_directory_with_no_runs_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"no run\.json found"):
        load_runs([tmp_path])


def test_a_missing_run_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="run report not found"):
        load_run(tmp_path / "nope.json")


def test_a_file_that_is_not_a_run_report_raises(tmp_path: Path) -> None:
    bad = tmp_path / "run.json"
    bad.write_text(json.dumps({"nope": True}), encoding="utf-8")
    with pytest.raises(ValueError, match="not a valid run report"):
        load_run(bad)


def test_write_report_emits_calibration_json(tmp_path: Path) -> None:
    report = calibrate([run(("a", True))])
    path = write_report(report, tmp_path)
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8"))["rows"][0]["task_id"] == "a"


# --- markdown ---------------------------------------------------------------------


def test_run_markdown_reports_the_resolve_rate_and_every_task() -> None:
    markdown = run_to_markdown(run(("a", True), ("b", False)))
    assert "Resolved: **1 / 2** (50.0%)" in markdown
    assert "`a`" in markdown
    assert "`b`" in markdown
    assert "agent --go" in markdown


def test_calibration_markdown_names_tasks_needing_rework() -> None:
    markdown = calibration_to_markdown(calibrate([run(("easy", True))], band=(0.1, 0.7)))
    assert "Needs rework" in markdown
    assert "solved too often to discriminate" in markdown


def test_calibration_markdown_says_so_when_everything_is_in_band() -> None:
    runs = [run(("a", True)), run(("a", False))]
    markdown = calibration_to_markdown(calibrate(runs, band=(0.1, 0.7)))
    assert "Every task sits inside the target band." in markdown


def test_validation_markdown_lists_failed_checks() -> None:
    validation = TaskValidation(
        task_id="x",
        language="python",
        digest="0" * 64,
        checks=[
            Check(name="structure", passed=True, detail="fine"),
            Check(name="base-fail-to-pass-fails", passed=False, detail="pre-solved"),
        ],
    )
    markdown = validations_to_markdown([validation])

    assert "0 of 1 tasks valid." in markdown
    assert "base-fail-to-pass-fails" in markdown
    assert "**FAIL**" in markdown


def test_write_validations_emits_both_artifacts(tmp_path: Path) -> None:
    validation = TaskValidation(
        task_id="x", language="python", digest="a" * 64, checks=[Check(name="c", passed=True)]
    )
    paths = write_validations([validation], tmp_path / "v")
    assert paths["json"].is_file()
    assert paths["markdown"].is_file()
    assert json.loads(paths["json"].read_text(encoding="utf-8"))[0]["task_id"] == "x"
