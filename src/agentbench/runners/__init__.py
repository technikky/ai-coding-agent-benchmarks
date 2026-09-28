"""Test runners, one per task language."""

from __future__ import annotations

from pathlib import Path

from agentbench.runners.base import RunnerError, TestRunner
from agentbench.runners.junit import parse_junit_file, parse_junit_xml
from agentbench.runners.pytest_runner import PytestRunner
from agentbench.runners.vitest_runner import VitestRunner
from agentbench.types import Language

__all__ = [
    "PytestRunner",
    "RunnerError",
    "TestRunner",
    "VitestRunner",
    "build_runner",
    "parse_junit_file",
    "parse_junit_xml",
]


def build_runner(language: Language, *, cache_dir: str | Path | None = None) -> TestRunner:
    """Return the runner for a task language."""
    if language == "python":
        return PytestRunner()
    if language == "typescript":
        return VitestRunner(cache_dir)
    raise RunnerError(f"no runner for language {language!r}")
