# Authoring a task

A checklist and the reasoning behind it. The short version: write the specification so
that someone who has never seen your solution can implement it from the instructions
alone, then prove mechanically that the task measures something.

## 1. Lay out the directory

```
tasks/<language>/<task-id>/
    task.json
    SPEC.md
    workspace/          the starting state, defect included
    tests/public/       visible to the agent
    tests/hidden/       withheld until grading
    solution/           files that overlay workspace/
```

The directory name **is** the task id, and `task.json` must agree with it.

`solution/` is an overlay, not a patch: each file in it replaces the file at the same
relative path in `workspace/`. No patch tooling, no merge conflicts, and a reviewer can
read the reference solution as an ordinary file.

Test **filenames** must be unique across `tests/public/` and `tests/hidden/`. pytest's
default import mode cannot load two same-named modules from directories that are not
packages, and the failure aborts collection for the whole task. `structure` checks this.

## 2. Choose the defect before writing the specification

The order matters. Decide exactly what is wrong, then describe the desired behaviour
without mentioning the defect's shape. If you write the spec first you will describe
your fix, and the spec will read like a patch instruction rather than a requirement.

**Independent defects.** If a task carries more than one, make each separately
detectable by its own graded test. `ts-002-cart-total` has two — a rounding error and a
loop that drops the last line — and fixing either does not fix the other. An agent that
finds one and misses the other should score 1 of 2 fail-to-pass, not 0.

## 3. Write the specification

Required sections: `## Context`, `## Requirements`, `## Definition of done`. At least
one fenced block with an exact input and its exact expected output.

The rule that does the most work: **state every convention explicitly, and give exact
expected values.**

| Instead of | Write |
| --- | --- |
| "handle invalid input appropriately" | "raise `ValueError` with exactly `interval start must not exceed end: (3, 1)`" |
| "merge overlapping intervals" | "merge when `next_start <= current_end`; because the intervals are closed, `(1, 2)` and `(2, 3)` both contain 2 and merge to `(1, 3)`" |
| "round the total" | "round the exact value once, at the end, with an exact half rounded up" |
| "retry a few times" | "call the function at most `max_retries + 1` times; sleep exactly `max_retries` times when every attempt fails" |

`spec_lint` flags words that defer a decision — *appropriately*, *correctly*,
*properly*, *reasonable*, *gracefully*, *as needed*, *handle edge cases*. They are
warnings, not errors, because occasionally one is genuinely fine. Read each one and ask
whether a grader could disagree with a competent implementer. If so, the word is hiding
a requirement.

**Never name a graded test in the specification.** The agent is told the spec and
nothing else; naming a test turns "implement this behaviour" into "satisfy this named
assertion". `spec-leaks-test-name` is an error, not a warning.

**Say what not to touch.** Every shipped spec ends with "Change only `<file>`. Do not
edit any file under `tests/`."

## 4. Split the tests

**Public tests** (`tests/public/`) describe behaviour that already works. They are the
agent's safety net and they become your pass-to-pass set. They must pass on the
unmodified workspace.

**Hidden tests** (`tests/hidden/`) grade the change. They must fail on the unmodified
workspace and pass after the reference solution.

For a **feature** task where the function does not exist yet, the public tests cannot
cover it. Cover a *different, already-working* function in the same module instead —
that is what `py-002-retry-backoff` does with `compute_backoff_delays`, and it is what
gives a from-scratch task a meaningful pass-to-pass set.

Make the stub fail at **call** time, not import time. A decorator that raises when
applied breaks collection of the hidden test module, and the graded tests then read as
"never collected" rather than "failing".

Assert exact values. `assert result == 1254`, not `assert result > 1250`.

## 5. Declare the tests

```json
{
  "fail_to_pass": ["test_touching_intervals_are_merged"],
  "pass_to_pass": ["test_strictly_overlapping_intervals_merge"]
}
```

Names are the test's own title. For vitest you may write either the bare title or the
full `describe > title` form; both normalise to the same thing. Titles must be unique
within a task, and `tests-declared` rejects a name that was never collected — which is
what stops `base-fail-to-pass-fails` from passing vacuously on a typo.

A hidden test may be pass-to-pass. `py-001` does this with
`test_a_single_point_interval_is_valid`: it holds before and after, and keeping it
hidden means an agent cannot read it while working.

## 6. Validate

```bash
agentbench lint --task <task-id>        # fast, no test execution
agentbench validate --task <task-id>    # the seven checks
```

What the failures mean:

| Failure | Cause | Fix |
| --- | --- | --- |
| `base-fail-to-pass-fails` | A graded test already passes on the starting workspace | The defect is not actually present, or the test does not exercise it |
| `base-pass-to-pass-passes` | A public test fails before the fix | The workspace is broken beyond the intended defect |
| `solution-resolves` (F2P) | The reference does not satisfy the spec | Fix the reference, or the test is wrong |
| `solution-resolves` (P2P) | The reference regresses working behaviour | The fix is too broad |
| `tests-declared` | A declared name was not collected | Typo, or the test file is not collected at all |
| `solution-differs` | `solution/` is byte-identical to `workspace/` | Nothing was actually fixed |
| `spec-lint` | See the linter output | Usually a missing section or a missing example |

## 7. Implement it blind

The step no tool can do for you, and the one that catches most ambiguity.

Put the reference solution aside. From `SPEC.md` alone, implement the change. Then run
the hidden tests against *that* implementation.

Every test that fails is a question the specification did not answer. Do not fix your
implementation — fix the specification, then try again. Repeat until a blind
implementation passes on the first attempt.

This is what "removed ambiguity so tests reward only correct behaviour" means in
practice, and it is why `spec_lint` is described as a smell detector rather than a
check.

## 8. Calibrate

A task solved on every attempt and a task solved on none carry the same information
about an agent: none. Both still cost money to run.

```bash
for i in 1 2 3 4 5; do
  agentbench grade --solver command --command '<agent>' --out "reports/run-$i"
done
agentbench calibrate reports/ --band 0.1 0.7
```

`too_easy` — tighten the requirements, remove the hint, or drop the task.
`too_hard` — the spec is probably ambiguous rather than the problem hard. Re-read it
before making the task easier.

Set difficulty labels from observed solve rates once you have them. Until then they are
the author's judgement, and the README says so.

## 9. Before opening a pull request

- [ ] `agentbench validate --task <id>` passes all seven checks
- [ ] `agentbench grade --solver noop --task <id> --expect-resolve-rate 0.0`
- [ ] `agentbench grade --solver reference --task <id> --expect-resolve-rate 1.0`
- [ ] A blind implementation from `SPEC.md` alone passes the hidden tests
- [ ] Each independent defect has its own graded test
- [ ] The spec states exact expected values, including exact error messages
- [ ] The spec names no graded test
- [ ] The spec says which file to change and not to edit `tests/`
- [ ] Nothing in the task comes from an employer, a client or another benchmark
- [ ] No credentials, tokens or private data anywhere in the task directory
