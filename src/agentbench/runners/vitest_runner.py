"""vitest runner for TypeScript tasks.

The interesting problem here is ``node_modules``. Installing vitest into every sandbox
would dominate the runtime of a benchmark pass, and copying a ``node_modules`` tree per
sandbox is worse. Symlinking is unreliable on Windows without elevated privileges.

The approach taken instead needs none of those: sandboxes are created *inside* a
runtime directory that already holds an installed ``node_modules``. Node resolves
modules by walking up the directory tree, so a test at
``<runtime>/sandbox-ab12/tests/hidden/x.test.ts`` finds ``<runtime>/node_modules``
without a symlink, a copy or a per-sandbox install. One install serves every task and
is reused across invocations.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from agentbench.runners.base import RunnerError, failed_suite, run_subprocess, tail
from agentbench.runners.junit import parse_junit_file
from agentbench.types import SuiteResult, normalize_test_name

REPORT_NAME = ".agentbench-junit.xml"
DEFAULT_CACHE_DIR = Path(".agentbench-cache")

#: The runtime's own dependencies, kept in code so the digest below is stable and the
#: install directory is reused rather than rebuilt whenever a task changes.
RUNTIME_PACKAGE: dict[str, object] = {
    "name": "agentbench-ts-runtime",
    "version": "0.0.0",
    "private": True,
    "type": "module",
    "devDependencies": {"vitest": "^3.2.0"},
}


def _which(executable: str) -> str:
    resolved = shutil.which(executable)
    if resolved is None:
        raise RunnerError(
            f"{executable} is not on PATH. The TypeScript tasks need Node.js and npm; "
            f"install Node 20 or newer, or restrict the run with --language python."
        )
    return resolved


class VitestRunner:
    """Runs ``vitest run`` inside a sandbox beneath a shared runtime directory."""

    def __init__(
        self, cache_dir: str | Path | None = None, *, install_timeout_s: int = 600
    ) -> None:
        # Resolved eagerly: the runtime path is handed to a subprocess whose cwd is the
        # sandbox, so a relative path would resolve against the sandbox and not find
        # node_modules.
        self._cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR).resolve()
        self._install_timeout_s = install_timeout_s
        self._runtime_root: Path | None = None

    @property
    def name(self) -> str:
        return "vitest"

    @property
    def runtime_root(self) -> Path:
        digest = hashlib.sha256(
            json.dumps(RUNTIME_PACKAGE, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:12]
        return self._cache_dir / f"ts-runtime-{digest}"

    def sandbox_parent(self) -> Path:
        if self._runtime_root is None:
            self._runtime_root = self._ensure_runtime()
        return self._runtime_root

    def _ensure_runtime(self) -> Path:
        root = self.runtime_root
        root.mkdir(parents=True, exist_ok=True)

        package_json = root / "package.json"
        desired = json.dumps(RUNTIME_PACKAGE, indent=2) + "\n"
        if not package_json.is_file() or package_json.read_text(encoding="utf-8") != desired:
            package_json.write_text(desired, encoding="utf-8")

        if (root / "node_modules" / "vitest").is_dir():
            return root

        npm = _which("npm")
        returncode, output, _ = run_subprocess(
            [npm, "install", "--no-audit", "--no-fund", "--loglevel=error"],
            cwd=root,
            timeout_s=self._install_timeout_s,
        )
        if returncode != 0 or not (root / "node_modules" / "vitest").is_dir():
            raise RunnerError(
                f"npm install failed in {root} (exit {returncode}):\n{tail(output, 2000)}"
            )
        return root

    def _vitest_command(self, report: Path) -> list[str]:
        """Prefer the installed entry point; fall back to npx."""
        entry = self.sandbox_parent() / "node_modules" / "vitest" / "vitest.mjs"
        common = ["run", "--reporter=junit", f"--outputFile={report}"]
        if entry.is_file():
            return [_which("node"), str(entry), *common]
        return [_which("npx"), "--no-install", "vitest", *common]

    def run(self, root: Path, *, label: str, timeout_s: int) -> SuiteResult:
        report = root / REPORT_NAME
        report.unlink(missing_ok=True)

        returncode, output, duration = run_subprocess(
            self._vitest_command(report),
            cwd=root,
            timeout_s=timeout_s,
            env={"CI": "true", "NO_COLOR": "1"},
        )

        if not report.is_file():
            return failed_suite(
                label,
                f"vitest produced no JUnit report (exit {returncode}):\n{tail(output, 1500)}",
                duration,
            )

        cases = [
            case.model_copy(update={"name": normalize_test_name(case.name)})
            for case in parse_junit_file(report)
        ]
        report.unlink(missing_ok=True)
        return SuiteResult(
            label=label,
            returncode=returncode,
            duration_s=duration,
            cases=cases,
            output_tail=tail(output),
        )
