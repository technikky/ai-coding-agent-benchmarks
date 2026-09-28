"""pytest runner for Python tasks."""

from __future__ import annotations

import sys
from pathlib import Path

from agentbench.runners.base import failed_suite, run_subprocess, tail
from agentbench.runners.junit import parse_junit_file
from agentbench.types import SuiteResult

REPORT_NAME = ".agentbench-junit.xml"


class PytestRunner:
    """Runs ``python -m pytest tests`` inside the sandbox.

    Two details matter. ``PYTHONPATH`` is set to the sandbox root, because pytest's
    default import mode puts the *test file's* directory on ``sys.path``, not the
    project root, so ``import intervals`` from ``tests/public/`` would otherwise fail.
    And only ``tests/`` is collected, so a workspace file that happens to be named
    ``test_*.py`` cannot quietly join the graded set.
    """

    @property
    def name(self) -> str:
        return "pytest"

    def sandbox_parent(self) -> Path | None:
        return None

    def run(self, root: Path, *, label: str, timeout_s: int) -> SuiteResult:
        report = root / REPORT_NAME
        report.unlink(missing_ok=True)

        command = [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "-p",
            "no:cacheprovider",
            "-q",
            "--tb=line",
            f"--junit-xml={report}",
        ]
        returncode, output, duration = run_subprocess(
            command,
            cwd=root,
            timeout_s=timeout_s,
            env={"PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1"},
        )

        if not report.is_file():
            # No report at all means pytest never got as far as running tests, which is
            # a harness or task-structure problem rather than a test failure.
            return failed_suite(
                label,
                f"pytest produced no JUnit report (exit {returncode}):\n{tail(output, 1500)}",
                duration,
            )

        cases = parse_junit_file(report)
        report.unlink(missing_ok=True)
        return SuiteResult(
            label=label,
            returncode=returncode,
            duration_s=duration,
            cases=cases,
            output_tail=tail(output),
        )
