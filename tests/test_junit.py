"""JUnit parsing, against the two shapes pytest and vitest actually emit."""

from __future__ import annotations

import pytest

from agentbench.runners.junit import parse_junit_file, parse_junit_xml

PYTEST_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="1" skipped="1" tests="4" time="0.07">
    <testcase classname="tests.hidden.test_graded" name="test_passes" time="0.001"/>
    <testcase classname="tests.hidden.test_graded" name="test_fails" time="0.002">
      <failure message="assert 1 == 2">E assert 1 == 2</failure>
    </testcase>
    <testcase classname="tests.hidden.test_graded" name="test_errors" time="0.0">
      <error message="fixture blew up">ZeroDivisionError</error>
    </testcase>
    <testcase classname="tests.hidden.test_graded" name="test_skipped" time="0.0">
      <skipped message="needs network"/>
    </testcase>
  </testsuite>
</testsuites>
"""

# vitest writes a bare <testsuite> root and folds describe blocks into name.
VITEST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="tests/hidden/cart.graded.test.ts" tests="2" failures="1" time="0.4">
  <testcase classname="tests/hidden/cart.graded.test.ts"
            name="cart totals (graded) &gt; rounds once" time="0.01"/>
  <testcase classname="tests/hidden/cart.graded.test.ts"
            name="cart totals (graded) &gt; includes the final line" time="0.02">
    <failure message="expected 10 to be 12">AssertionError</failure>
  </testcase>
</testsuite>
"""


class TestParsePytestShape:
    def test_reads_every_case(self) -> None:
        assert len(parse_junit_xml(PYTEST_XML)) == 4

    @pytest.mark.parametrize(
        ("name", "status"),
        [
            ("test_passes", "passed"),
            ("test_fails", "failed"),
            ("test_errors", "error"),
            ("test_skipped", "skipped"),
        ],
    )
    def test_maps_each_outcome_element_to_a_status(self, name: str, status: str) -> None:
        by_name = {c.name: c for c in parse_junit_xml(PYTEST_XML)}
        assert by_name[name].status == status

    def test_a_skipped_test_is_not_a_pass(self) -> None:
        by_name = {c.name: c for c in parse_junit_xml(PYTEST_XML)}
        assert by_name["test_skipped"].ok is False

    def test_captures_the_failure_message(self) -> None:
        by_name = {c.name: c for c in parse_junit_xml(PYTEST_XML)}
        assert "assert 1 == 2" in by_name["test_fails"].message

    def test_reads_durations(self) -> None:
        by_name = {c.name: c for c in parse_junit_xml(PYTEST_XML)}
        assert by_name["test_fails"].duration_s == pytest.approx(0.002)


class TestParseVitestShape:
    def test_accepts_a_bare_testsuite_root(self) -> None:
        assert len(parse_junit_xml(VITEST_XML)) == 2

    def test_keeps_the_raw_describe_prefix(self) -> None:
        # The parser stays a parser; normalisation belongs to the runner, so that the
        # raw name is still available for diagnostics.
        names = {c.name for c in parse_junit_xml(VITEST_XML)}
        assert "cart totals (graded) > rounds once" in names


class TestParserRobustness:
    def test_malformed_xml_raises_valueerror(self) -> None:
        with pytest.raises(ValueError, match="malformed JUnit XML"):
            parse_junit_xml("<testsuite><testcase</testsuite>")

    def test_a_non_numeric_time_degrades_to_zero(self) -> None:
        xml = '<testsuite><testcase name="a" time="NaNish"/></testsuite>'
        assert parse_junit_xml(xml)[0].duration_s == 0.0

    def test_an_empty_suite_parses_to_nothing(self) -> None:
        assert parse_junit_xml('<testsuite name="empty"/>') == []

    def test_missing_report_file_raises(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError):
            parse_junit_file(tmp_path / "absent.xml")

    def test_reads_a_report_from_disk(self, tmp_path) -> None:
        report = tmp_path / "junit.xml"
        report.write_text(PYTEST_XML, encoding="utf-8")
        assert len(parse_junit_file(report)) == 4
