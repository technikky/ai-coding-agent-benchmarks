"""Mechanical checks on a task specification.

Most rejected benchmark tasks are not rejected for having weak tests. They are
rejected because the specification admits more than one reasonable reading, so a
correct agent fails a graded test for a behaviour the spec never pinned down. The
cure is to state every convention explicitly and give exact expected outputs.

That discipline cannot be fully automated -- the real check is implementing the spec
blind from the instructions alone and seeing whether the hidden tests pass. What *can*
be automated is the set of recurring smells, and catching those before a human review
cycle is worth the eighty lines it costs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from agentbench.task import Task

Severity = Literal["error", "warning"]

REQUIRED_SECTIONS = ("## Context", "## Requirements", "## Definition of done")

#: Words that, in a benchmark specification, almost always stand in for a decision the
#: author has not made yet. "Handle errors appropriately" is not a requirement; it is a
#: disagreement waiting to happen at grading time.
WEASEL_TERMS = (
    "appropriately",
    "as appropriate",
    "as needed",
    "if necessary",
    "correctly",
    "properly",
    "reasonable",
    "sensible",
    "gracefully",
    "and so on",
    "should probably",
    "handle edge cases",
    "make it work",
    "as expected",
    "etc.",
)

PLACEHOLDER_PATTERN = re.compile(r"\b(TODO|FIXME|XXX|TBD)\b")
MIN_WORDS = 80


@dataclass(frozen=True)
class SpecFinding:
    rule: str
    severity: Severity
    message: str
    line: int | None = None

    def __str__(self) -> str:
        where = f"line {self.line}: " if self.line else ""
        return f"[{self.severity}] {self.rule}: {where}{self.message}"


def _find_term_lines(text: str, term: str) -> list[int]:
    """Line numbers where ``term`` appears, ignoring fenced code blocks.

    Code blocks are excluded because an exact expected output may legitimately contain
    any word at all, and flagging it would train authors to ignore the linter.
    """
    lines: list[int] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if term in line.lower():
            lines.append(number)
    return lines


def lint_spec(
    text: str,
    *,
    entrypoint_files: list[str],
    hidden_test_names: list[str],
    min_words: int = MIN_WORDS,
) -> list[SpecFinding]:
    """Lint a specification body. Errors block a task; warnings are advisory."""
    findings: list[SpecFinding] = []

    if not text.strip():
        return [SpecFinding("spec-empty", "error", "SPEC.md is empty")]

    if not any(line.startswith("# ") for line in text.splitlines()):
        findings.append(SpecFinding("spec-no-title", "error", "no level-1 heading"))

    for section in REQUIRED_SECTIONS:
        if section not in text:
            findings.append(SpecFinding("spec-missing-section", "error", f"no {section!r} section"))

    word_count = len(text.split())
    if word_count < min_words:
        findings.append(
            SpecFinding(
                "spec-too-short",
                "error",
                f"{word_count} words; a specification under {min_words} is very unlikely to "
                f"pin down the behaviour the hidden tests grade",
            )
        )

    if "```" not in text:
        findings.append(
            SpecFinding(
                "spec-no-example",
                "error",
                "no fenced code block; a task should show at least one exact input and its "
                "exact expected output",
            )
        )

    # The agent is told the specification and nothing else. Naming a graded test in it
    # turns "implement the behaviour" into "satisfy this named assertion".
    lowered = text.lower()
    for name in hidden_test_names:
        if name.lower() in lowered:
            findings.append(
                SpecFinding(
                    "spec-leaks-test-name",
                    "error",
                    f"names the graded test {name!r}; the specification must describe "
                    f"behaviour, not the tests that check it",
                )
            )

    for relative in entrypoint_files:
        basename = relative.rsplit("/", 1)[-1]
        if relative not in text and basename not in text:
            findings.append(
                SpecFinding(
                    "spec-entrypoint-unmentioned",
                    "error",
                    f"never mentions {relative}, which the task declares as a file to change",
                )
            )

    for term in WEASEL_TERMS:
        for line_number in _find_term_lines(text, term):
            findings.append(
                SpecFinding(
                    "spec-weasel-term",
                    "warning",
                    f"{term!r} defers a decision the specification should make",
                    line=line_number,
                )
            )

    for number, line in enumerate(text.splitlines(), start=1):
        match = PLACEHOLDER_PATTERN.search(line)
        if match:
            findings.append(
                SpecFinding(
                    "spec-placeholder",
                    "error",
                    f"unresolved {match.group(1)} marker",
                    line=number,
                )
            )

    return findings


def lint_task(task: Task, *, min_words: int = MIN_WORDS) -> list[SpecFinding]:
    """Lint a task's ``SPEC.md``."""
    if not task.spec_md.is_file():
        return [SpecFinding("spec-missing", "error", "SPEC.md does not exist")]
    return lint_spec(
        task.spec_md.read_text(encoding="utf-8"),
        entrypoint_files=task.spec.entrypoint_files,
        hidden_test_names=task.spec.fail_to_pass,
        min_words=min_words,
    )


def errors(findings: list[SpecFinding]) -> list[SpecFinding]:
    return [f for f in findings if f.severity == "error"]


def warnings(findings: list[SpecFinding]) -> list[SpecFinding]:
    return [f for f in findings if f.severity == "warning"]
