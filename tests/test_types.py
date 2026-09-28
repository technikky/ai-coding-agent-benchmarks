"""The data model, and the test-name normalisation every comparison depends on."""

from __future__ import annotations

import pytest

from agentbench.types import (
    RunGrade,
    SuiteResult,
    TaskGrade,
    normalize_test_name,
)
from agentbench.types import (
    TestCaseResult as CaseResult,
)


def case(name: str, status: str = "passed") -> CaseResult:
    return CaseResult(name=name, status=status)  # type: ignore[arg-type]


class TestNormalizeTestName:
    def test_leaves_a_bare_pytest_name_alone(self) -> None:
        assert normalize_test_name("test_doubles_every_element") == "test_doubles_every_element"

    def test_strips_a_vitest_describe_prefix(self) -> None:
        assert normalize_test_name("cart totals (visible) > returns zero") == "returns zero"

    def test_strips_only_the_outermost_ancestry(self) -> None:
        # Nested describes stack up; the test's own title is the final segment.
        assert normalize_test_name("outer > inner > does the thing") == "does the thing"

    def test_keeps_a_separator_that_is_part_of_the_title(self) -> None:
        # Partitioned from the right, so "a > b" as a title survives one describe.
        assert normalize_test_name("suite > renders a > b correctly") == "b correctly"

    def test_trims_surrounding_whitespace(self) -> None:
        assert normalize_test_name("  spaced out  ") == "spaced out"


class TestSuiteResult:
    def test_collected_counts_cases(self) -> None:
        suite = SuiteResult(
            label="base", returncode=0, duration_s=0.1, cases=[case("a"), case("b")]
        )
        assert suite.collected == 2

    def test_status_of_returns_none_for_an_uncollected_test(self) -> None:
        suite = SuiteResult(label="base", returncode=0, duration_s=0.0, cases=[case("a")])
        assert suite.status_of("missing") is None

    def test_missing_preserves_declaration_order(self) -> None:
        suite = SuiteResult(label="base", returncode=0, duration_s=0.0, cases=[case("b")])
        assert suite.missing(["a", "b", "c"]) == ["a", "c"]

    def test_duplicate_names_flags_ambiguous_selection(self) -> None:
        suite = SuiteResult(
            label="base", returncode=0, duration_s=0.0, cases=[case("a"), case("a"), case("b")]
        )
        assert suite.duplicate_names() == ["a"]

    def test_all_passed_is_false_when_a_test_was_never_collected(self) -> None:
        # A deleted test must not read as a pass; this is what stops an agent from
        # resolving a task by removing the assertions that failed.
        suite = SuiteResult(label="base", returncode=0, duration_s=0.0, cases=[case("a")])
        assert suite.all_passed(["a", "b"]) is False

    def test_passed_count_ignores_failures_and_absences(self) -> None:
        suite = SuiteResult(
            label="base",
            returncode=1,
            duration_s=0.0,
            cases=[case("a"), case("b", "failed"), case("c", "error")],
        )
        assert suite.passed_count(["a", "b", "c", "d"]) == 1

    def test_rejects_an_unknown_field(self) -> None:
        with pytest.raises(ValueError):
            SuiteResult(label="x", returncode=0, duration_s=0.0, oops=1)  # type: ignore[call-arg]


class TestRunGrade:
    def grade(self, task_id: str, resolved: bool) -> TaskGrade:
        return TaskGrade(
            task_id=task_id,
            language="python",
            resolved=resolved,
            f2p_passed=1 if resolved else 0,
            f2p_total=1,
            p2p_passed=1,
            p2p_total=1,
            duration_s=0.1,
        )

    def test_resolve_rate_over_a_mixed_run(self) -> None:
        run = RunGrade(
            solver="noop",
            created_at="2026-01-01T00:00:00+00:00",
            harness_version="0.1.0",
            tasks=[self.grade("a", True), self.grade("b", False)],
        )
        assert run.n_tasks == 2
        assert run.n_resolved == 1
        assert run.resolve_rate == 0.5

    def test_resolve_rate_is_none_with_no_tasks(self) -> None:
        # None rather than 0.0: "nothing ran" and "everything failed" are different,
        # and the CLI gate has to tell them apart.
        run = RunGrade(solver="noop", created_at="t", harness_version="0.1.0")
        assert run.resolve_rate is None
