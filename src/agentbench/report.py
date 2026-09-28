"""Rendering validation, grading and calibration results."""

from __future__ import annotations

import json
from pathlib import Path

from agentbench.types import CalibrationReport, RunGrade, TaskValidation


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


# --- validation ------------------------------------------------------------------


def validations_to_markdown(validations: list[TaskValidation]) -> str:
    lines: list[str] = ["# Task validation", ""]
    n_valid = sum(1 for v in validations if v.valid)
    lines.append(f"{n_valid} of {len(validations)} tasks valid.")
    lines.append("")
    lines.append("| Task | Language | Valid | Failed checks |")
    lines.append("| --- | --- | --- | --- |")
    for v in validations:
        failed = ", ".join(c.name for c in v.failures) or "-"
        lines.append(f"| `{v.task_id}` | {v.language} | {'yes' if v.valid else 'NO'} | {failed} |")
    lines.append("")

    for v in validations:
        lines.append(f"## `{v.task_id}`")
        lines.append("")
        lines.append(f"Digest `{v.digest[:16]}`")
        lines.append("")
        for check in v.checks:
            mark = "PASS" if check.passed else "FAIL"
            lines.append(f"- **{mark}** `{check.name}` - {check.detail}")
        lines.append("")
    return "\n".join(lines)


def write_validations(validations: list[TaskValidation], out_dir: str | Path) -> dict[str, Path]:
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "validation.json"
    md_path = directory / "validation.md"
    json_path.write_text(
        json.dumps([v.model_dump(mode="json") for v in validations], indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    md_path.write_text(validations_to_markdown(validations), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


# --- grading ---------------------------------------------------------------------


def run_to_markdown(run: RunGrade) -> str:
    lines: list[str] = ["# Benchmark run", ""]
    lines.append(f"- Solver: **{run.solver}**")
    if run.command:
        lines.append(f"- Command: `{run.command}`")
    lines.append(f"- Harness: {run.harness_version}")
    lines.append(f"- Started: {run.created_at}")
    lines.append(f"- Resolved: **{run.n_resolved} / {run.n_tasks}** ({_pct(run.resolve_rate)})")
    lines.append("")
    lines.append("| Task | Language | Resolved | Fail-to-pass | Pass-to-pass | Seconds | Notes |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for task in run.tasks:
        lines.append(
            f"| `{task.task_id}` | {task.language} | {'yes' if task.resolved else 'no'} "
            f"| {task.f2p_passed}/{task.f2p_total} | {task.p2p_passed}/{task.p2p_total} "
            f"| {task.duration_s:.1f} | {task.note or '-'} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_run(run: RunGrade, out_dir: str | Path) -> dict[str, Path]:
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "run.json"
    md_path = directory / "run.md"
    json_path.write_text(
        json.dumps(run.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    md_path.write_text(run_to_markdown(run), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


# --- calibration -----------------------------------------------------------------


def calibration_to_markdown(report: CalibrationReport) -> str:
    lines: list[str] = ["# Difficulty calibration", ""]
    lines.append(
        f"Target solve-rate band **[{report.band_low:.2f}, {report.band_high:.2f}]** "
        f"over {report.n_runs} run(s)."
    )
    lines.append("")
    lines.append("| Task | Attempts | Solved | Solve rate | Verdict |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in report.rows:
        lines.append(
            f"| `{row.task_id}` | {row.attempts} | {row.solved} "
            f"| {_pct(row.solve_rate)} | {row.verdict.replace('_', ' ')} |"
        )
    lines.append("")
    if report.needs_rework:
        lines.append("## Needs rework")
        lines.append("")
        for row in report.needs_rework:
            why = (
                "solved too often to discriminate"
                if row.verdict == "too_easy"
                else "never or almost never solved"
            )
            lines.append(f"- `{row.task_id}`: {_pct(row.solve_rate)} - {why}")
        lines.append("")
    else:
        lines.append("Every task sits inside the target band.")
        lines.append("")
    return "\n".join(lines)
