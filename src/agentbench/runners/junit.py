"""JUnit XML parsing.

pytest and vitest agree on almost nothing about how a test is identified, but both
write JUnit XML. Parsing that one format is the whole of the polyglot support in this
harness -- adding a third language means adding a runner that can emit JUnit, not
teaching the grader a third result format.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from agentbench.types import TestCaseResult, TestStatus


def _status_of(case: ElementTree.Element) -> tuple[TestStatus, str]:
    """Derive a status from the child element JUnit uses to mark an outcome."""
    for tag, status in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
        child = case.find(tag)
        if child is not None:
            message = child.get("message") or (child.text or "").strip()
            return status, message.strip()[:500]  # type: ignore[return-value]
    return "passed", ""


def parse_junit_xml(text: str) -> list[TestCaseResult]:
    """Parse JUnit XML into test case results.

    Accepts either a ``<testsuites>`` or a bare ``<testsuite>`` root, since pytest and
    vitest differ on which they emit.
    """
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise ValueError(f"malformed JUnit XML: {exc}") from exc

    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))

    results: list[TestCaseResult] = []
    for suite in suites:
        for case in suite.findall("testcase"):
            status, message = _status_of(case)
            try:
                duration = float(case.get("time") or 0.0)
            except ValueError:
                duration = 0.0
            results.append(
                TestCaseResult(
                    name=(case.get("name") or "").strip(),
                    classname=(case.get("classname") or "").strip(),
                    status=status,
                    message=message,
                    duration_s=duration,
                )
            )
    return results


def parse_junit_file(path: str | Path) -> list[TestCaseResult]:
    report = Path(path)
    if not report.is_file():
        raise FileNotFoundError(f"no JUnit report at {report}")
    return parse_junit_xml(report.read_text(encoding="utf-8", errors="replace"))
