"""Shared fixtures.

The interesting fixture here is :func:`write_python_task`, which builds a complete,
synthetic benchmark task on disk. It exists so the validator can be tested against
tasks that are deliberately broken in one specific way each -- a pre-solved task, a
reference that does not fix anything, a typo in ``task.json``. Asserting that the
validator rejects those is the only way to know the checks do anything.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TASKS_ROOT = REPO_ROOT / "tasks"

#: A specification body that passes ``spec_lint`` cleanly, so synthetic tasks fail only
#: for the reason a given test is about. ``{entrypoint}`` is substituted.
CLEAN_SPEC_TEMPLATE = """# Double a number

`{entrypoint}` exposes a single function that should return twice its argument.

## Context

The module holds one public function, `double`, which takes one integer and returns
another integer. Nothing else in the module is part of the public surface, and no other
module imports it. The starting implementation returns a value that does not match the
requirement below for at least one input, which is what the graded tests examine.

## Requirements

`double(value)` must return `value * 2` for every integer input, including zero and
negative integers. It must not print anything, must not raise for any integer, and must
return an `int` rather than a float.

## Examples

```python
>>> double(2)
4
>>> double(0)
0
>>> double(-3)
-6
```

## Definition of done

`double` returns exactly twice its argument for every integer, and the module imports
without side effects.

Change only `{entrypoint}`. Do not edit any file under `tests/`.
"""


@pytest.fixture
def write_python_task(tmp_path: Path) -> Callable[..., Path]:
    """Return a factory that writes a synthetic Python task and yields its directory."""

    def factory(
        *,
        task_id: str = "tmp-001-double",
        workspace_body: str = (
            # Passes the public test but fails the hidden one, so the factory's default
            # is a *valid* task and each negative test can break exactly one thing.
            "def double(value: int) -> int:\n"
            "    if value < 0:\n"
            "        return 0\n"
            "    return value * 2\n"
        ),
        solution_body: str | None = None,
        public_body: str | None = None,
        hidden_body: str | None = None,
        fail_to_pass: list[str] | None = None,
        pass_to_pass: list[str] | None = None,
        entrypoint: str = "doubling.py",
        spec_text: str | None = None,
        root: Path | None = None,
    ) -> Path:
        task_dir = (root or tmp_path) / task_id
        (task_dir / "workspace").mkdir(parents=True, exist_ok=True)
        (task_dir / "solution").mkdir(parents=True, exist_ok=True)
        (task_dir / "tests" / "public").mkdir(parents=True, exist_ok=True)
        (task_dir / "tests" / "hidden").mkdir(parents=True, exist_ok=True)

        module = entrypoint.removesuffix(".py")

        (task_dir / "workspace" / entrypoint).write_text(workspace_body, encoding="utf-8")
        (task_dir / "solution" / entrypoint).write_text(
            solution_body
            if solution_body is not None
            else "def double(value: int) -> int:\n    return value * 2\n",
            encoding="utf-8",
        )
        (task_dir / "tests" / "public" / "test_public_double.py").write_text(
            public_body
            if public_body is not None
            else (
                f"from {module} import double\n\n\n"
                "def test_doubles_a_positive_number():\n"
                "    assert double(2) == 4\n"
            ),
            encoding="utf-8",
        )
        (task_dir / "tests" / "hidden" / "test_hidden_double.py").write_text(
            hidden_body
            if hidden_body is not None
            else (
                f"from {module} import double\n\n\n"
                "def test_doubles_a_negative_number():\n"
                "    assert double(-3) == -6\n"
            ),
            encoding="utf-8",
        )
        (task_dir / "SPEC.md").write_text(
            spec_text
            if spec_text is not None
            else CLEAN_SPEC_TEMPLATE.format(entrypoint=entrypoint),
            encoding="utf-8",
        )
        (task_dir / "task.json").write_text(
            json.dumps(
                {
                    "id": task_id,
                    "language": "python",
                    "title": "Double a number",
                    "kind": "bug_fix",
                    "difficulty": "easy",
                    "entrypoint_files": [entrypoint],
                    "fail_to_pass": fail_to_pass
                    if fail_to_pass is not None
                    else ["test_doubles_a_negative_number"],
                    "pass_to_pass": pass_to_pass
                    if pass_to_pass is not None
                    else ["test_doubles_a_positive_number"],
                    "timeout_s": 60,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return task_dir

    return factory


def node_available() -> bool:
    return shutil.which("node") is not None and shutil.which("npm") is not None


requires_node = pytest.mark.skipif(
    not node_available(), reason="the TypeScript task track needs Node.js and npm"
)
