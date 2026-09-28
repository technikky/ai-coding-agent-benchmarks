# ai-coding-agent-benchmarks

A benchmark harness for AI coding agents, where every task has to prove it measures
something before it is allowed to measure anything. Tasks are directories with a
specification, a defective workspace, a hidden graded test suite and a reference
solution, in Python/pytest and TypeScript/vitest.

[![CI](https://github.com/technikky/ai-coding-agent-benchmarks/actions/workflows/ci.yml/badge.svg)](https://github.com/technikky/ai-coding-agent-benchmarks/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

## Problem

Writing tests is easy. Writing a *benchmark task* is not, and the failures are
specific and repeatable:

- **The task is already solved.** A graded test that passes on the starting workspace
  gives every agent a free point. The task's solve rate is 100% for reasons that have
  nothing to do with the agent.
- **The specification is ambiguous.** A correct agent fails a graded test because the
  spec never said which of two reasonable behaviours was wanted.
- **The reference does not work.** The solution shipped with the task does not satisfy
  the specification it shipped with, so the task is unsolvable as written.
- **A declared test never runs.** A typo in the manifest silently shrinks the graded
  set, and the task quietly grades on fewer assertions than it claims.
- **The starting state is broken beyond the intended defect**, so the agent has to fix
  something nobody asked it to.

None of these are visible by reading the task. All of them are mechanically
detectable, which is what this harness is for.

## The validation contract

`agentbench validate` runs seven checks per task. A task that fails any of them is not
part of the benchmark.

| Check | What it proves |
| --- | --- |
| `structure` | Every referenced file exists; no two test files share a basename (which would abort pytest collection for the whole task). |
| `spec-lint` | The specification has the required sections, an exact worked example, no unresolved placeholders, and does not name the graded tests. |
| `solution-differs` | The reference actually changes the workspace. |
| `tests-declared` | Every test named in `task.json` was collected, exactly once. **This is what stops the next check from succeeding vacuously.** |
| `base-fail-to-pass-fails` | Every fail-to-pass test fails *before* the fix. The task is not pre-solved. |
| `base-pass-to-pass-passes` | Every pass-to-pass test passes *before* the fix. The starting state is broken only in the intended way. |
| `solution-resolves` | The reference makes every fail-to-pass test pass without regressing any pass-to-pass test. |

What this cannot check is whether a specification is genuinely unambiguous. The only
real test for that is implementing it blind from the instructions alone and seeing
whether the hidden tests pass; `spec-lint` catches recurring smells, not meaning. That
blind-implementation pass is a human step, and the repository says so rather than
pretending otherwise.

## The two controls

Validation checks tasks one at a time. Two solvers check the benchmark as a whole, and
CI asserts both on every push:

```bash
agentbench grade --solver noop      --expect-resolve-rate 0.0   # negative control
agentbench grade --solver reference --expect-resolve-rate 1.0   # positive control
```

- **`noop`** changes nothing. If it resolves any task, that task is pre-solved.
- **`reference`** applies the author's own solution. If it fails any task, that
  reference does not satisfy its own specification.

A benchmark that cannot state those two numbers has not been validated, and the number
it reports for a real agent is not interpretable.

## Architecture

```
tasks/<language>/<task-id>/
        task.json         metadata + the fail-to-pass and pass-to-pass test names
        SPEC.md           the only thing the agent is told
        workspace/        starting state, defect included
        tests/public/     visible to the agent
        tests/hidden/     withheld until grading
        solution/         reference files, overlaid onto workspace/
                    |
                    v
           discover_tasks() -> [Task]        digest() = sha256 over the whole directory
                    |
        +-----------+------------------------------+
        |                                          |
   validate                                     grade
        |                                          |
  sandbox(include_hidden=True)            sandbox(include_hidden=False)
   run on base -> F2P must fail                    |
                  P2P must pass              solver.solve(sandbox)
  sandbox(apply_solution=True)            noop / reference / command
   run -> F2P and P2P must pass                    |
        |                                  add_hidden_tests()
        |                                          |
        |                                  run -> select by test name
        |                                          |
        v                                          v
  TaskValidation (7 checks)                  TaskGrade (resolved?)
        |                                          |
        v                                          v
  validation.json / .md                      run.json / run.md
                                                   |
                                          calibrate over repeated runs
                                                   |
                                          solve rate vs target band
                                          -> too_easy / in_band / too_hard
```

Both languages report through **JUnit XML**, which pytest and vitest both emit. That
one format is the whole of the polyglot support: adding a third language means adding a
runner that can write JUnit, not teaching the grader a third result format.

### Two implementation details worth naming

**`node_modules` is installed once, not per sandbox.** Installing vitest into every
sandbox would dominate a benchmark pass, copying a `node_modules` tree is worse, and
symlinking is unreliable on Windows without elevated privileges. Instead, sandboxes are
created *inside* a runtime directory that already has `node_modules`. Node resolves
modules by walking up the directory tree, so a test at
`<runtime>/agentbench-ab12/tests/hidden/x.test.ts` finds `<runtime>/node_modules` with
no symlink, no copy and no per-sandbox install.

**Test identity is the test's own name.** pytest node ids and vitest test titles have
nothing in common. vitest prefixes a test with its `describe` ancestry
(`"cart totals (visible) > returns zero for an empty cart"`); pytest writes the bare
function name. Both the declared names and the collected names pass through
`normalize_test_name`, so a task may spell them either way. Two tests that collapse to
the same name are reported as a duplicate rather than resolved silently in favour of
whichever ran first.

## Features

- **Seven-check task validation**, with the exact failure reason reported per check
- **Hidden graded tests**, withheld from the solver's sandbox and copied in only to grade
- **Two languages**: Python/pytest and TypeScript/vitest, over one JUnit-based grader
- **A specification linter** that rejects missing sections, absent examples, unresolved
  placeholders, graded-test-name leaks, and flags weasel words that defer a decision
- **All-or-nothing resolution**: every fail-to-pass test passes and no pass-to-pass test
  regresses, so an agent cannot score by satisfying half a spec or deleting an assertion
- **Difficulty calibration** against a target solve-rate band, across repeated runs
- **Content digests** per task, so a published solve rate is tied to exact task content
- **Built-in controls** (`noop`, `reference`) and a `command` solver for a real agent CLI
- **Timeout and failure isolation**: a hanging or crashing task is a result, not an
  aborted run

## Tech stack

Python 3.10+ · pydantic 2 · pytest · `argparse` · vitest 3 · Node 20+ · ruff · mypy
(strict) · Docker · GitHub Actions

One runtime dependency (pydantic). Node is needed only for the TypeScript track; the
Python track runs without it, and `--language python` skips it entirely.

## Project structure

```
src/agentbench/
    types.py            validated data model, test-name normalisation
    task.py             task loading, discovery, digests, structural checks
    spec_lint.py        mechanical specification checks
    workspace.py        sandbox construction, hidden-test withholding, change detection
    validate.py         the seven validation checks
    grade.py            solver orchestration and resolution
    calibrate.py        solve rates across runs vs a target band
    report.py           JSON and markdown rendering
    solvers.py          noop, reference, command
    cli.py              list / lint / validate / grade / calibrate
    runners/
        base.py         the TestRunner protocol, subprocess handling
        junit.py        JUnit XML parsing (the cross-language contract)
        pytest_runner.py
        vitest_runner.py
tasks/
    python/             py-001-interval-merge, py-002-retry-backoff
    typescript/         ts-001-debounce, ts-002-cart-total
tests/                  138 harness tests
docs/
    task-authoring.md   how to write a task that validates
    methodology.md      why the checks are what they are
```

## Installation

```bash
git clone https://github.com/technikky/ai-coding-agent-benchmarks.git
cd ai-coding-agent-benchmarks
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Node 20+ is required for the TypeScript tasks. The first TypeScript run installs vitest
into `.agentbench-cache/` (gitignored) and reuses it afterwards.

## Configuration

There is nothing to configure and no API key to supply. The harness itself never calls
a model; the `command` solver runs an agent CLI whose own credentials come from that
tool's environment. No secret is read, written or logged by this project, and CI runs
`gitleaks` on every push.

## Usage

```bash
agentbench list                      # the task set
agentbench lint                      # specifications only, no test execution
agentbench validate                  # the seven checks, per task
agentbench validate --language python --out reports/validation
```

Run the controls:

```bash
agentbench grade --solver noop      --expect-resolve-rate 0.0
agentbench grade --solver reference --expect-resolve-rate 1.0
```

Run a real coding agent. `{spec}` and `{workspace}` are substituted, and the agent sees
the workspace and the public tests but never the graded ones:

```bash
agentbench grade --solver command \
  --command 'claude -p "$(cat {spec})" --permission-mode acceptEdits' \
  --out reports/agent-run-1
```

Calibrate difficulty over repeated runs:

```bash
for i in 1 2 3 4 5; do
  agentbench grade --solver command --command '...' --out "reports/run-$i"
done
agentbench calibrate reports/ --band 0.1 0.7 --fail-outside-band
```

As a library:

```python
from agentbench import discover_tasks, grade_tasks, validate_tasks
from agentbench.solvers import ReferenceSolver

tasks = discover_tasks("tasks", language="python")
assert all(v.valid for v in validate_tasks(tasks))

run = grade_tasks(tasks, ReferenceSolver())
print(run.n_resolved, "/", run.n_tasks, run.resolve_rate)
```

## The task set

Four tasks, all written from scratch for this repository.

| Task | Language | Kind | Difficulty | F2P | P2P | What it tests |
| --- | --- | --- | --- | --- | --- | --- |
| `py-001-interval-merge` | Python | bug fix | medium | 5 | 7 | Three independent defects: touching closed intervals not merged, the caller's list mutated, no input validation. Exact error message specified. |
| `py-002-retry-backoff` | Python | feature | hard | 10 | 4 | Implement a retry decorator: exact attempt counts, an exponential delay schedule, never sleeping after the final failure, re-raising unchanged, metadata preserved. |
| `ts-001-debounce` | TypeScript | bug fix | medium | 4 | 5 | A debounce that throttles instead: the timer is never reset, the first call's arguments are kept, and an invalid wait is accepted. Fake timers. |
| `ts-002-cart-total` | TypeScript | bug fix | easy | 4 | 4 | Two independent defects: per-unit flooring instead of one half-up rounding, and a loop that drops the last cart line. |

**23 fail-to-pass and 20 pass-to-pass tests**, 43 graded assertions in total.

`py-002` is a feature task rather than a bug fix, which is why its public tests cover a
*different, already-working* function in the same module: that is what gives a
from-scratch implementation task a meaningful pass-to-pass set.

## Measured results

Everything in this table came from a command in this repository. Reproduce with
`agentbench validate` and the two `grade` commands above.

| Metric | Result |
| --- | --- |
| Tasks | 4 (2 Python, 2 TypeScript) |
| Validation | **4 / 4 valid**, 7 of 7 checks each |
| `noop` control | **0 / 4 resolved (0.0%)** — 0 of 23 fail-to-pass, 20 of 20 pass-to-pass |
| `reference` control | **4 / 4 resolved (100.0%)** — 23 of 23 fail-to-pass, 20 of 20 pass-to-pass |
| Harness tests | **138 passed** |
| Statement coverage | **95%** |
| ruff / ruff format / mypy --strict | clean |

**No agent solve rates are published here.** Running a real coding agent over these
tasks costs money and I have not paid for a run whose numbers I would then be asserting
as fact. The `--solver command` invocation above is exactly what produces them, and
`agentbench calibrate` is what turns repeated runs into a difficulty verdict. Until
then those rows read *not measured* rather than carrying a plausible-looking figure.

## Testing

```bash
pytest                                                  # 138 tests
pytest -m "not slow"                                    # fast unit tests only
pytest --cov=agentbench --cov-report=term-missing
ruff check . && ruff format --check .
mypy
```

The tests worth knowing about are in
[`tests/test_validation_catches_authoring_bugs.py`](tests/test_validation_catches_authoring_bugs.py).
Each one builds a synthetic task that is broken in exactly one way — pre-solved, a
reference that fixes nothing, a reference that regresses a passing test, a typo'd test
name, a workspace broken beyond its defect, a specification that says "make it work" —
and asserts the matching check rejects it. Without those, `validate` printing all-PASS
would only prove that it prints.

TypeScript tests skip with a clear reason when Node is absent; CI installs Node so they
never skip there.

## Docker

```bash
docker compose up --build validate     # the seven checks per task
docker compose up --build noop         # must resolve 0
docker compose up --build reference    # must resolve 4
```

The runtime image carries Node as well as Python, because an image without Node could
only run half the benchmark, and the vitest runtime is installed at build time so a
benchmark pass does not reach the network. It runs as a non-root user (uid 10001).

## CI/CD

```
push / PR
   |
   +-- harness (Python 3.10, 3.11, 3.12, each with Node 20)
   |     ruff check -> ruff format --check -> mypy --strict -> pytest --cov
   |
   +-- benchmark controls
   |     agentbench lint
   |     agentbench validate                                    (all 4 must be valid)
   |     agentbench grade --solver noop      --expect-resolve-rate 0.0
   |     agentbench grade --solver reference --expect-resolve-rate 1.0
   |
   +-- secret scan (gitleaks, full history)
   |
   +-- docker build -> run both controls inside the image
```

Node is installed in the harness matrix on purpose: without it the TypeScript tests
would skip, and the matrix would be quietly weaker than its green tick suggests.

## Originality and confidentiality

Every task, specification, test and reference solution in this repository was written
from scratch for it. No task, prompt, dataset, test or rubric from any employer or
client appears here, in whole or in part. The repository demonstrates the *methodology*
of benchmark authoring — unambiguous specifications, fail-to-pass and pass-to-pass
tests, hidden graded suites, difficulty calibration — using material that is entirely
my own and freely publishable.

## Limitations

- **The task set is small.** Four tasks demonstrate the harness; they do not rank
  models. Ranking needs tens of tasks per category.
- **A public benchmark is contaminable.** "Hidden" means hidden from the agent at solve
  time, not secret: the graded tests are in this repository, so any model trained on
  public GitHub may have seen them. Comparable published benchmarks share this problem.
  Use these tasks as a harness demonstration and a template; keep a private task set
  for numbers you intend to trust.
- **Difficulty labels are the author's judgement**, not observed solve rates. No
  calibration run has been performed yet, which is why `calibrate` exists and why no
  band verdict is published.
- **No agent is benchmarked here.** See *Measured results*.
- **Grading is all-or-nothing.** Deliberate, but it means a near-miss and a total
  failure are the same verdict, even though the reported counts differ.
- **`spec_lint` is a smell detector.** It cannot tell whether a requirement is
  genuinely unambiguous.
- **Sandboxing is filesystem-level only.** Solver commands run with the privileges of
  the invoking user. Run untrusted agents in a container.
- **The vitest runtime is resolved at install time**, not pinned by a committed
  lockfile, so a vitest patch release could in principle change behaviour.

## Roadmap

- [ ] More tasks per category; a target of 10+ per language before any ranking claim
- [ ] A private held-out task set, with only aggregate results published
- [ ] Committed lockfile for the TypeScript runtime
- [ ] Container-level isolation for solver commands
- [ ] `agentbench compare` for two run reports, as a CI regression gate
- [ ] Multi-file and cross-module tasks; currently every task edits one file
- [ ] Record per-attempt agent transcripts alongside grades
- [ ] Partial-credit reporting as a secondary metric, without changing resolution

## License

MIT — see [LICENSE](LICENSE).
