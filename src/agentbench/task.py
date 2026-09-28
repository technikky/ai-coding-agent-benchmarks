"""Task discovery, loading and digesting.

A task is a directory, not a database row, so it can be reviewed in a pull request
like any other code. The layout is fixed:

    <task-id>/
        task.json          metadata, plus the fail-to-pass and pass-to-pass test names
        SPEC.md            the only thing the agent is told
        workspace/         the starting repository state, defect included
        tests/public/      visible to the agent
        tests/hidden/      withheld until grading
        solution/          reference files that overlay workspace/
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agentbench.types import Difficulty, Language, TaskKind, normalize_test_name

TASK_FILE = "task.json"
SPEC_FILE = "SPEC.md"


class TaskSpec(BaseModel):
    """The contents of ``task.json``."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    language: Language
    title: str = Field(min_length=1)
    kind: TaskKind
    difficulty: Difficulty
    fail_to_pass: list[str] = Field(min_length=1)
    pass_to_pass: list[str] = Field(default_factory=list)
    entrypoint_files: list[str] = Field(min_length=1)
    timeout_s: int = Field(default=300, gt=0)
    tags: list[str] = Field(default_factory=list)

    @field_validator("fail_to_pass", "pass_to_pass")
    @classmethod
    def _normalise_declarations(cls, names: list[str]) -> list[str]:
        """Strip describe-block ancestry, then reject duplicates.

        Normalising before the duplicate check is what makes the check meaningful for
        vitest: two tests with the same title under different describe blocks are
        indistinguishable once collected, so declaring both is an authoring error even
        though the raw strings differ.
        """
        normalised = [normalize_test_name(name) for name in names]
        if blank := [i for i, name in enumerate(normalised) if not name]:
            raise ValueError(f"test names must not be empty (entries {blank})")
        if len(set(normalised)) != len(normalised):
            raise ValueError("test names must not be declared twice")
        return normalised

    @model_validator(mode="after")
    def _f2p_and_p2p_are_disjoint(self) -> TaskSpec:
        overlap = sorted(set(self.fail_to_pass) & set(self.pass_to_pass))
        if overlap:
            raise ValueError(
                "a test cannot be both fail-to-pass and pass-to-pass: " + ", ".join(overlap)
            )
        return self

    @property
    def all_test_names(self) -> list[str]:
        return [*self.fail_to_pass, *self.pass_to_pass]


class Task:
    """A benchmark task on disk."""

    def __init__(self, spec: TaskSpec, root: Path) -> None:
        self.spec = spec
        self.root = root

    # --- paths -------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self.spec.id

    @property
    def language(self) -> Language:
        return self.spec.language

    @property
    def spec_md(self) -> Path:
        return self.root / SPEC_FILE

    @property
    def workspace_dir(self) -> Path:
        return self.root / "workspace"

    @property
    def public_tests_dir(self) -> Path:
        return self.root / "tests" / "public"

    @property
    def hidden_tests_dir(self) -> Path:
        return self.root / "tests" / "hidden"

    @property
    def solution_dir(self) -> Path:
        return self.root / "solution"

    # --- integrity ---------------------------------------------------------------

    def digest(self) -> str:
        """SHA-256 over every file in the task directory.

        Recorded in run reports so a published solve rate can be tied to the exact
        task content that produced it. Editing a hidden test changes the digest, which
        is the point: a benchmark whose items drift silently is not a benchmark.
        """
        digest = hashlib.sha256()
        for path in sorted(p for p in self.root.rglob("*") if p.is_file()):
            digest.update(path.relative_to(self.root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    def structure_problems(self) -> list[str]:
        """Missing files and directories, checked before anything is executed."""
        problems: list[str] = []
        for label, path in (
            (SPEC_FILE, self.spec_md),
            ("workspace/", self.workspace_dir),
            ("tests/hidden/", self.hidden_tests_dir),
            ("solution/", self.solution_dir),
        ):
            if not path.exists():
                problems.append(f"missing {label}")

        for directory, label in (
            (self.workspace_dir, "workspace/"),
            (self.hidden_tests_dir, "tests/hidden/"),
            (self.solution_dir, "solution/"),
        ):
            if directory.is_dir() and not any(p.is_file() for p in directory.rglob("*")):
                problems.append(f"{label} contains no files")

        for relative in self.spec.entrypoint_files:
            if not (self.workspace_dir / relative).is_file():
                problems.append(f"entrypoint_files lists {relative}, which is not in workspace/")

        # pytest's default import mode cannot load two test modules with the same
        # basename from directories that are not packages, so a hidden test file named
        # like a public one aborts collection for the whole task.
        basenames: dict[str, list[str]] = {}
        for directory, label in (
            (self.public_tests_dir, "public"),
            (self.hidden_tests_dir, "hidden"),
        ):
            if not directory.is_dir():
                continue
            for path in sorted(directory.rglob("*")):
                if path.is_file() and not path.name.startswith("."):
                    basenames.setdefault(path.name, []).append(label)
        for name, labels in sorted(basenames.items()):
            if len(labels) > 1:
                problems.append(
                    f"test file {name!r} appears in more than one tests/ directory "
                    f"({', '.join(labels)}); basenames must be unique within a task"
                )

        return problems

    def __repr__(self) -> str:
        return f"Task({self.id!r}, language={self.language!r})"


def load_task(root: str | Path) -> Task:
    """Load a single task directory."""
    path = Path(root)
    task_file = path / TASK_FILE
    if not task_file.is_file():
        raise FileNotFoundError(f"{path}: no {TASK_FILE}")
    try:
        raw = json.loads(task_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{task_file}: invalid JSON ({exc.msg} at line {exc.lineno})") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{task_file}: expected a JSON object at the top level")

    spec = TaskSpec.model_validate(raw)
    if spec.id != path.name:
        raise ValueError(f"{task_file}: id {spec.id!r} does not match directory name {path.name!r}")
    return Task(spec, path)


def discover_tasks(
    tasks_root: str | Path,
    *,
    language: Language | None = None,
    task_ids: list[str] | None = None,
) -> list[Task]:
    """Find every task under ``tasks_root``, sorted by id.

    A directory containing ``task.json`` is a task; anything else is ignored, so
    language folders and shared build files can live alongside tasks.
    """
    root = Path(tasks_root)
    if not root.is_dir():
        raise FileNotFoundError(f"tasks root not found: {root}")

    tasks = [load_task(p.parent) for p in sorted(root.rglob(TASK_FILE))]

    duplicates = sorted({t.id for t in tasks if [x.id for x in tasks].count(t.id) > 1})
    if duplicates:
        raise ValueError(f"duplicate task ids: {', '.join(duplicates)}")

    if language is not None:
        tasks = [t for t in tasks if t.language == language]
    if task_ids is not None:
        wanted = set(task_ids)
        known = {t.id for t in tasks}
        unknown = sorted(wanted - known)
        if unknown:
            raise ValueError(
                f"unknown task id(s): {', '.join(unknown)}. Available: {', '.join(sorted(known))}"
            )
        tasks = [t for t in tasks if t.id in wanted]

    return sorted(tasks, key=lambda t: t.id)
