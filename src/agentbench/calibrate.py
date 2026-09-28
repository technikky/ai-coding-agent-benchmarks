"""Difficulty calibration.

A benchmark item is informative when a capable agent sometimes solves it and sometimes
does not. A task solved on every attempt and a task solved on none carry the same
amount of information about the agent: none. Both still cost money to run.

Calibration here is deliberately blunt: run the same solver over the task set N times,
count solves per task, and compare the observed rate against a target band. Anything
outside the band is flagged for rework -- clarify the specification, tighten or relax
the graded tests, or remove the task.

The band is a policy choice, not a fact. 0.1-0.7 is the default because it keeps tasks
that a target model fails often enough to discriminate while dropping ones that are
impossible or free.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from agentbench.types import CalibrationReport, CalibrationRow, RunGrade, Verdict

DEFAULT_BAND = (0.1, 0.7)


def calibrate(
    runs: list[RunGrade],
    *,
    band: tuple[float, float] = DEFAULT_BAND,
) -> CalibrationReport:
    """Aggregate per-task solve rates across repeated runs."""
    low, high = band
    if not 0.0 <= low <= high <= 1.0:
        raise ValueError(f"band must satisfy 0 <= low <= high <= 1, got {band}")
    if not runs:
        raise ValueError("calibration needs at least one run report")

    attempts: dict[str, int] = defaultdict(int)
    solved: dict[str, int] = defaultdict(int)
    for run in runs:
        for task in run.tasks:
            attempts[task.task_id] += 1
            solved[task.task_id] += int(task.resolved)

    rows: list[CalibrationRow] = []
    for task_id in sorted(attempts):
        rate = solved[task_id] / attempts[task_id]
        verdict: Verdict
        if rate > high:
            verdict = "too_easy"
        elif rate < low:
            verdict = "too_hard"
        else:
            verdict = "in_band"
        rows.append(
            CalibrationRow(
                task_id=task_id,
                attempts=attempts[task_id],
                solved=solved[task_id],
                solve_rate=rate,
                verdict=verdict,
            )
        )

    return CalibrationReport(band_low=low, band_high=high, n_runs=len(runs), rows=rows)


def load_run(path: str | Path) -> RunGrade:
    """Load a ``run.json`` written by ``agentbench grade``."""
    file = Path(path)
    if not file.is_file():
        raise FileNotFoundError(f"run report not found: {file}")
    try:
        return RunGrade.model_validate_json(file.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"{file}: not a valid run report ({exc})") from exc


def load_runs(paths: list[str | Path]) -> list[RunGrade]:
    """Load run reports from files, or from every ``run.json`` under a directory."""
    runs: list[RunGrade] = []
    for entry in paths:
        path = Path(entry)
        if path.is_dir():
            found = sorted(path.rglob("run.json"))
            if not found:
                raise FileNotFoundError(f"no run.json found under {path}")
            runs.extend(load_run(p) for p in found)
        else:
            runs.append(load_run(path))
    return runs


def write_report(report: CalibrationReport, out_dir: str | Path) -> Path:
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "calibration.json"
    path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
