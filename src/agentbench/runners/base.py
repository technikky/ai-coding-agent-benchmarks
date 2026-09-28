"""The test-runner interface and shared subprocess handling."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Protocol

from agentbench.types import SuiteResult

OUTPUT_TAIL_CHARS = 4000


class RunnerError(RuntimeError):
    """The runner could not be executed at all (missing toolchain, failed install)."""


class TestRunner(Protocol):
    """Runs a task's tests inside a prepared sandbox and reports JUnit results."""

    @property
    def name(self) -> str: ...

    def sandbox_parent(self) -> Path | None:
        """Directory sandboxes must be created under, or ``None`` for the system temp.

        The vitest runner uses this so that a sandbox sits beneath a directory holding
        an already-installed ``node_modules``; Node's upward module resolution then
        finds it without an install per sandbox.
        """
        ...

    def run(self, root: Path, *, label: str, timeout_s: int) -> SuiteResult:
        """Run every test present in ``root`` and return the parsed outcome."""
        ...


def _as_text(stream: str | bytes | None) -> str:
    if stream is None:
        return ""
    if isinstance(stream, bytes):  # pragma: no cover - platform dependent
        return stream.decode("utf-8", errors="replace")
    return stream


def run_subprocess(
    command: list[str],
    *,
    cwd: Path,
    timeout_s: int,
    env: dict[str, str] | None = None,
) -> tuple[int, str, float]:
    """Run a command, capturing merged output. Returns (returncode, output, seconds).

    A timeout yields returncode ``-1`` rather than raising: a task that hangs is a
    result about that task, and it should not abort a hundred-task run.
    """
    merged_env = {**os.environ, **(env or {})}
    started = time.perf_counter()
    try:
        # The command is always constructed by the harness, never by task data.
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=merged_env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        # TimeoutExpired carries bytes or str depending on how the child was opened,
        # so each stream is normalised on its own before being joined.
        captured = "".join(_as_text(stream) for stream in (exc.stdout, exc.stderr))
        return -1, f"{captured}\n[timed out after {timeout_s}s]", time.perf_counter() - started
    except FileNotFoundError as exc:
        raise RunnerError(f"executable not found: {command[0]} ({exc})") from exc

    duration = time.perf_counter() - started
    return completed.returncode, completed.stdout + completed.stderr, duration


def tail(text: str, limit: int = OUTPUT_TAIL_CHARS) -> str:
    return text if len(text) <= limit else "...\n" + text[-limit:]


def failed_suite(label: str, message: str, duration_s: float = 0.0) -> SuiteResult:
    """A suite that could not be run, as opposed to one whose tests failed."""
    return SuiteResult(
        label=label, returncode=-1, duration_s=duration_s, cases=[], runner_error=message
    )
