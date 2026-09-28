"""Solvers: the things being benchmarked, plus the harness's own controls.

``noop`` and ``reference`` are not toys. They are the benchmark's negative and
positive controls, and CI asserts both on every push:

* ``noop`` changes nothing and must resolve **0** tasks. If it resolves any, that
  task's hidden tests already passed on the starting workspace, which means the task
  measures nothing.
* ``reference`` applies the author's own solution and must resolve **all** tasks. If
  it fails any, the reference does not satisfy the specification it shipped with.

A benchmark that cannot state those two numbers has not been validated, and the number
it reports for a real agent is not interpretable.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Protocol

from agentbench.workspace import Sandbox


@dataclass(frozen=True)
class SolveOutcome:
    """What a solver did. ``ok`` is about the solver running, not about passing."""

    ok: bool
    duration_s: float
    note: str = ""


class Solver(Protocol):
    @property
    def name(self) -> str: ...

    def solve(self, sandbox: Sandbox, *, timeout_s: int) -> SolveOutcome: ...


class NoopSolver:
    """Changes nothing. The benchmark's negative control."""

    @property
    def name(self) -> str:
        return "noop"

    def solve(self, sandbox: Sandbox, *, timeout_s: int) -> SolveOutcome:
        return SolveOutcome(ok=True, duration_s=0.0, note="no changes made")


class ReferenceSolver:
    """Applies the task's reference solution. The benchmark's positive control."""

    @property
    def name(self) -> str:
        return "reference"

    def solve(self, sandbox: Sandbox, *, timeout_s: int) -> SolveOutcome:
        started = time.perf_counter()
        sandbox.apply_solution()
        return SolveOutcome(
            ok=True, duration_s=time.perf_counter() - started, note="reference solution applied"
        )


class CommandSolver:
    """Runs an external coding agent inside the sandbox.

    The command is a template supplied by whoever starts the run, with two
    placeholders:

    * ``{spec}``      - path to ``SPEC.md`` inside the sandbox
    * ``{workspace}`` - path to the sandbox root

    It runs through the shell so that ordinary agent CLI invocations work unchanged.
    The string comes from the operator's own command line, never from task data.

    Example::

        agentbench grade --solver command \\
            --command 'claude -p "$(cat {spec})" --permission-mode acceptEdits'
    """

    def __init__(self, command: str) -> None:
        if not command.strip():
            raise ValueError("--command must not be empty when --solver command is used")
        self.command = command

    @property
    def name(self) -> str:
        return "command"

    def solve(self, sandbox: Sandbox, *, timeout_s: int) -> SolveOutcome:
        rendered = self.command.format(
            spec=sandbox.spec_path.as_posix(), workspace=sandbox.path.as_posix()
        )
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                rendered,
                shell=True,
                cwd=str(sandbox.path),
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return SolveOutcome(
                ok=False,
                duration_s=time.perf_counter() - started,
                note=f"agent timed out after {timeout_s}s",
            )

        duration = time.perf_counter() - started
        if completed.returncode != 0:
            # A non-zero exit is recorded but does not skip grading: an agent may fail
            # its own exit contract and still have left a correct edit behind.
            return SolveOutcome(
                ok=False, duration_s=duration, note=f"agent exited {completed.returncode}"
            )
        return SolveOutcome(ok=True, duration_s=duration)


def build_solver(name: str, *, command: str | None = None) -> Solver:
    key = name.strip().lower()
    if key == "noop":
        return NoopSolver()
    if key == "reference":
        return ReferenceSolver()
    if key == "command":
        return CommandSolver(command or "")
    raise ValueError(f"unknown solver {name!r}; expected noop, reference or command")
