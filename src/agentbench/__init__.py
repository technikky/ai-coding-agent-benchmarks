"""A benchmark harness for evaluating AI coding agents on real repository tasks."""

from __future__ import annotations

from agentbench.calibrate import calibrate, load_run, load_runs
from agentbench.grade import grade_task, grade_tasks
from agentbench.solvers import (
    CommandSolver,
    NoopSolver,
    ReferenceSolver,
    SolveOutcome,
    Solver,
    build_solver,
)
from agentbench.spec_lint import SpecFinding, lint_spec, lint_task
from agentbench.task import Task, TaskSpec, discover_tasks, load_task
from agentbench.types import (
    CalibrationReport,
    CalibrationRow,
    Check,
    RunGrade,
    SuiteResult,
    TaskGrade,
    TaskValidation,
    TestCaseResult,
)
from agentbench.validate import validate_task, validate_tasks
from agentbench.workspace import Sandbox, sandbox

__version__ = "0.1.0"

__all__ = [
    "CalibrationReport",
    "CalibrationRow",
    "Check",
    "CommandSolver",
    "NoopSolver",
    "ReferenceSolver",
    "RunGrade",
    "Sandbox",
    "SolveOutcome",
    "Solver",
    "SpecFinding",
    "SuiteResult",
    "Task",
    "TaskGrade",
    "TaskSpec",
    "TaskValidation",
    "TestCaseResult",
    "__version__",
    "build_solver",
    "calibrate",
    "discover_tasks",
    "grade_task",
    "grade_tasks",
    "lint_spec",
    "lint_task",
    "load_run",
    "load_runs",
    "load_task",
    "sandbox",
    "validate_task",
    "validate_tasks",
]
