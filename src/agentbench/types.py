"""Core data model.

Test identity across languages is the awkward part of a polyglot benchmark. pytest
node ids and vitest test titles have nothing in common, so this harness normalises on
the one field both emit into JUnit XML: the test's own name. That works only if test
names are unique within a task, so task validation enforces uniqueness instead of
leaving it to chance.
"""

from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: vitest joins a test's enclosing ``describe`` blocks onto its own title with this
#: separator in the JUnit ``name`` attribute (``"cart totals (visible) > returns zero
#: for an empty cart"``); pytest writes the bare test name. Both the declared names in
#: ``task.json`` and the names collected from a runner are passed through
#: :func:`normalize_test_name`, so a task may spell its tests either way and a spec
#: stays portable between languages.
TEST_NAME_SEPARATOR = " > "


def normalize_test_name(name: str) -> str:
    """Return a test's own title, without any ``describe`` ancestry.

    Partitioned from the right, because a title may itself contain the separator while
    the ancestry is always to its left. Two tests with the same title in different
    describe blocks collapse to one name; that is reported as a duplicate by
    ``SuiteResult.duplicate_names`` and rejected on the declared side, rather than
    being resolved silently in favour of whichever ran first.
    """
    _, separator, own = name.rpartition(TEST_NAME_SEPARATOR)
    return (own if separator else name).strip()


TestStatus = Literal["passed", "failed", "error", "skipped"]
Language = Literal["python", "typescript"]
TaskKind = Literal["bug_fix", "feature", "refactor"]
Difficulty = Literal["easy", "medium", "hard"]
#: Where a task's observed solve rate sits relative to the target band.
Verdict = Literal["too_easy", "in_band", "too_hard"]


class TestCaseResult(BaseModel):
    """One test case, as reported by a JUnit XML writer."""

    # The name starts with "Test", so pytest would otherwise try to collect it.
    __test__ = False

    model_config = ConfigDict(extra="forbid")

    name: str
    classname: str = ""
    status: TestStatus
    message: str = ""
    duration_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.status == "passed"


class SuiteResult(BaseModel):
    """The outcome of one test-runner invocation."""

    model_config = ConfigDict(extra="forbid")

    label: str
    returncode: int
    duration_s: float
    cases: list[TestCaseResult] = Field(default_factory=list)
    output_tail: str = ""
    runner_error: str | None = None

    @property
    def collected(self) -> int:
        return len(self.cases)

    def duplicate_names(self) -> list[str]:
        """Test names appearing more than once, which break name-based selection."""
        counts = Counter(case.name for case in self.cases)
        return sorted(name for name, n in counts.items() if n > 1)

    def status_of(self, name: str) -> TestStatus | None:
        """Status of the uniquely named test, or ``None`` when it was not collected."""
        for case in self.cases:
            if case.name == name:
                return case.status
        return None

    def names(self) -> set[str]:
        return {case.name for case in self.cases}

    def missing(self, expected: list[str]) -> list[str]:
        collected = self.names()
        return [name for name in expected if name not in collected]

    def all_passed(self, expected: list[str]) -> bool:
        return all(self.status_of(name) == "passed" for name in expected)

    def passed_count(self, expected: list[str]) -> int:
        return sum(1 for name in expected if self.status_of(name) == "passed")


class Check(BaseModel):
    """One validation check on a task."""

    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    detail: str = ""


class TaskValidation(BaseModel):
    """Whether a task is a usable benchmark item."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    language: Language
    digest: str
    checks: list[Check] = Field(default_factory=list)

    @property
    def valid(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failures(self) -> list[Check]:
        return [check for check in self.checks if not check.passed]


class TaskGrade(BaseModel):
    """The result of grading one attempt at one task."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    language: Language
    resolved: bool
    f2p_passed: int
    f2p_total: int
    p2p_passed: int
    p2p_total: int
    duration_s: float
    missing_tests: list[str] = Field(default_factory=list)
    note: str = ""


class RunGrade(BaseModel):
    """A solver's results across a task set."""

    model_config = ConfigDict(extra="forbid")

    solver: str
    created_at: str
    harness_version: str
    command: str | None = None
    tasks: list[TaskGrade] = Field(default_factory=list)

    @property
    def n_tasks(self) -> int:
        return len(self.tasks)

    @property
    def n_resolved(self) -> int:
        return sum(1 for task in self.tasks if task.resolved)

    @property
    def resolve_rate(self) -> float | None:
        return self.n_resolved / self.n_tasks if self.tasks else None


class CalibrationRow(BaseModel):
    """Observed solve rate for one task, and whether it sits in the target band."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    attempts: int
    solved: int
    solve_rate: float
    verdict: Verdict


class CalibrationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    band_low: float
    band_high: float
    n_runs: int
    rows: list[CalibrationRow] = Field(default_factory=list)

    @property
    def needs_rework(self) -> list[CalibrationRow]:
        return [row for row in self.rows if row.verdict != "in_band"]
