"""Sandbox construction.

What ends up in the sandbox is the whole of the "hidden tests" mechanism. There is no
clever isolation here: the hidden tests are simply not copied in while a solver is
working, and are copied in afterwards to grade. Anything the solver can read, it was
meant to read.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from agentbench.task import Task

SANDBOX_PREFIX = "agentbench-"


def _merge_tree(src: Path, dst: Path) -> None:
    """Copy ``src`` over ``dst``, overwriting files and keeping the rest."""
    if not src.is_dir():
        return
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True)


class Sandbox:
    """A throwaway copy of a task's starting state."""

    def __init__(self, path: Path, task: Task) -> None:
        self.path = path
        self.task = task
        self._hidden_added = False

    @property
    def spec_path(self) -> Path:
        return self.path / "SPEC.md"

    @property
    def tests_dir(self) -> Path:
        return self.path / "tests"

    @property
    def has_hidden_tests(self) -> bool:
        return self._hidden_added

    def add_hidden_tests(self) -> None:
        """Copy the graded tests in. Called only after a solver has finished."""
        if self._hidden_added:
            return
        _merge_tree(self.task.hidden_tests_dir, self.tests_dir / "hidden")
        self._hidden_added = True

    def apply_solution(self) -> None:
        """Overlay the reference solution onto the workspace."""
        _merge_tree(self.task.solution_dir, self.path)

    def files_differing_from_workspace(self) -> list[str]:
        """Workspace-relative paths a solver added or modified.

        Reported in grading notes: a task resolved with no file changes usually means
        the hidden tests were already passing, not that the solver was clever.
        """
        changed: list[str] = []
        original_root = self.task.workspace_dir
        originals = {
            p.relative_to(original_root).as_posix(): p
            for p in original_root.rglob("*")
            if p.is_file()
        }

        for path in sorted(self.path.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(self.path).as_posix()
            if relative.startswith(("tests/", "node_modules/")) or relative == "SPEC.md":
                continue
            original = originals.get(relative)
            if original is None or original.read_bytes() != path.read_bytes():
                changed.append(relative)
        return changed


@contextmanager
def sandbox(
    task: Task,
    *,
    parent: Path | None = None,
    include_hidden: bool = False,
    apply_solution: bool = False,
) -> Iterator[Sandbox]:
    """Materialise a task into a temporary directory, and remove it afterwards.

    ``parent`` lets a runner place the sandbox somewhere specific; the vitest runner
    uses it to put sandboxes beneath a directory with an installed ``node_modules``.
    """
    if parent is not None:
        parent.mkdir(parents=True, exist_ok=True)

    root = Path(tempfile.mkdtemp(prefix=SANDBOX_PREFIX, dir=str(parent) if parent else None))
    try:
        _merge_tree(task.workspace_dir, root)
        _merge_tree(task.public_tests_dir, root / "tests" / "public")
        if task.spec_md.is_file():
            shutil.copy2(task.spec_md, root / "SPEC.md")

        box = Sandbox(root, task)
        if include_hidden:
            box.add_hidden_tests()
        if apply_solution:
            box.apply_solution()
        yield box
    finally:
        shutil.rmtree(root, ignore_errors=True)
