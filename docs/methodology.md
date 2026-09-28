# Methodology

Why the harness is built the way it is. Most of these decisions exist to stop a number
from looking more meaningful than it is.

## 1. A task must prove it measures something

The seven validation checks exist because none of the following are visible by reading a
task, and all of them produce a benchmark that still runs and still prints a number:

- a graded test that already passes on the starting workspace
- a reference solution that does not satisfy its own specification
- a declared test name that never resolves to a collected test
- a starting workspace broken beyond its intended defect

The load-bearing pair is `tests-declared` and `base-fail-to-pass-fails`.

`base-fail-to-pass-fails` asserts that every fail-to-pass test does **not** pass before
the fix. Taken alone, that check succeeds trivially when a test was never collected — a
missing test does not pass either. `tests-declared` closes that hole by requiring every
declared name to have been collected exactly once. Neither check is sufficient; together
they are. This is not hypothetical: it is exactly what happened while building the
TypeScript track, where vitest's `describe`-qualified test names did not match the
declared bare names, `tests-declared` failed loudly, and `base-fail-to-pass-fails`
reported a cheerful pass on four tests that had not run at all.

## 2. Resolution is all-or-nothing

A task is resolved when **every** fail-to-pass test passes **and every** pass-to-pass
test still passes.

Partial credit on fail-to-pass would reward an agent for satisfying the easy half of a
specification. Dropping the pass-to-pass requirement would reward one for deleting the
assertions that got in its way — and agents do try that, which is why a solver that
removes a test file is recorded as *tests not collected* and graded unresolved rather
than silently scoring on what remains.

The counts are still reported, because "7 of 8 and it broke nothing" and "1 of 8" are
very different failures when you are calibrating a task.

A skipped test does not count as passed, for the same reason.

## 3. "Hidden" means withheld at solve time, not secret

The mechanism is deliberately dull: the graded tests are not copied into the sandbox
while the solver works, and are copied in afterwards to grade. There is no sandbox
escape to worry about, because anything the solver can read, it was meant to read.

What this does **not** give you is secrecy. The graded tests are in this repository, so
any model trained on public GitHub may have seen them. Every public coding benchmark
shares this problem. The honest framing is that a public task set demonstrates a harness
and serves as a template; numbers you intend to trust need a private held-out set. The
README says this in *Limitations* rather than burying it.

A weaker form of leakage is worth closing anyway: `spec-leaks-test-name` rejects a
specification that names a graded test, because the agent is given the spec and nothing
else, and naming a test converts a behavioural requirement into a named assertion to
satisfy.

## 4. Specifications are graded by a smell detector, not a checker

`spec_lint` enforces what can be enforced: required sections, at least one exact worked
example, no unresolved placeholders, the entrypoint file actually mentioned, no graded
test names. It warns on words that defer a decision — *appropriately*, *correctly*,
*gracefully*, *as needed* — because in a benchmark specification those almost always
stand in for a choice the author has not made, and the disagreement surfaces at grading
time as a correct agent failing a test.

Weasel terms are warnings, not errors, and terms inside fenced code blocks are ignored
entirely: an exact expected output may legitimately contain any word, and flagging it
would teach authors to stop reading the linter.

What the linter cannot do is tell whether a requirement is unambiguous. The real test is
implementing the specification blind, from the instructions alone, and seeing whether the
hidden tests pass on the first attempt. Every failure there is a question the spec did
not answer. That step is human, it is documented in
[task-authoring.md](task-authoring.md), and the repository does not claim to automate it.

## 5. Two controls, asserted in CI

Per-task validation cannot catch a harness-level fault: a grader that reports success
regardless, a sandbox that leaks the reference, a test selector that matches nothing.

`noop` must resolve 0 tasks. `reference` must resolve all of them. Both run on every
push with `--expect-resolve-rate`, which exits non-zero on any deviation. They bound the
benchmark from both ends: the floor proves no task is pre-solved, the ceiling proves
every task is solvable as specified.

They also cost nothing — no model, no API key, no network — which is why they can run on
every commit rather than nightly.

## 6. One result format across languages

pytest node ids and vitest test titles have nothing in common, and a grader that
understood both would need a language-specific selector for each.

Both write JUnit XML, so that is the contract. The grader parses one format, and adding
a language means adding a runner that can emit JUnit.

Identity is the test's own name. vitest prefixes the `describe` ancestry; pytest does
not. Both the declared names and the collected names pass through one normalisation, so
a task may spell them either way. Two tests that collapse to the same normalised name
are reported as a **duplicate** rather than resolved in favour of whichever ran first,
because silently grading the wrong test is worse than refusing to grade.

## 7. Failures are isolated, not swallowed

| Failure | Effect |
| --- | --- |
| Unknown scorer or a judge-less rubric | Raise at construction, before any work |
| Malformed task metadata | Raise with the file and line |
| A solver that hangs | Timeout, recorded as unresolved for that task only |
| A solver that exits non-zero | Recorded, but still graded — an agent may fail its own exit contract and still have left a correct edit |
| A test runner that produces no report | That task is unresolved with the runner's output attached |
| A deleted or renamed graded test | *tests not collected*, unresolved |

Configuration errors fail fast; runtime errors degrade to a recorded result for one task.
A hundred-task run is not aborted by task 42, and nothing is silently coerced into a
pass.

## 8. Reproducibility is an artifact

Each task carries a SHA-256 digest over every file in its directory, recorded in
validation reports. Editing a hidden test changes the digest. A published solve rate can
therefore be tied to the exact task content that produced it, and a benchmark whose items
drift silently is not a benchmark.

## 9. Calibration is a policy, not a measurement

The default target band is a solve rate in `[0.1, 0.7]`. That is a choice, not a fact,
and it is stated as one.

The reasoning: a task solved on every attempt and a task solved on none carry the same
information about an agent, and both cost the same to run. The band keeps items that a
target model fails often enough to discriminate between agents, and drops the free ones
and the impossible ones.

A `too_hard` verdict usually means the specification is ambiguous rather than the problem
hard. Re-read the spec before making the task easier.

No calibration run is published in this repository, because none has been performed. The
difficulty labels on the four tasks are the author's judgement, and the README says so.
