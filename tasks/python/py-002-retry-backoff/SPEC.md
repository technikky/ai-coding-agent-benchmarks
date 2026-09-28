# A retry decorator with exponential backoff

`retrying.py` already contains a working `compute_backoff_delays`. The `retry`
decorator in the same module is a stub that raises `NotImplementedError`. Implement it.

## Context

`compute_backoff_delays(attempts, base_delay, factor, max_delay)` returns a list of
`attempts` delays, where delay *i* (zero-based) is
`min(base_delay * factor ** i, max_delay)`. It is complete and must keep working
exactly as it does now.

`retry` is a decorator factory with this signature, already present in the file:

```python
def retry(
    max_retries: int = 2,
    *,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    base_delay: float = 0.5,
    factor: float = 2.0,
    max_delay: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
):
```

`sleep` is injected so that tests can observe the delays without waiting.

## Requirements

1. **Attempt count.** The wrapped function is called at most `max_retries + 1` times:
   one initial attempt plus up to `max_retries` retries. With `max_retries=0` it is
   called exactly once.

2. **Success returns immediately.** As soon as a call returns, return its value and make
   no further attempts. Return the value unchanged.

3. **Only listed exceptions are retried.** If a raised exception is an instance of one
   of the types in `exceptions`, retry. Otherwise let it propagate immediately, with no
   sleep and no further attempts.

4. **Delay schedule.** The delays come from
   `compute_backoff_delays(max_retries, base_delay, factor, max_delay)`. Before retry
   *i* (zero-based), call `sleep` once with `delays[i]`. So with `max_retries=3`,
   `base_delay=0.5` and `factor=2.0`, a function that always fails produces calls to
   `sleep` with `0.5`, then `1.0`, then `2.0`.

5. **Never sleep after the final attempt.** When every attempt fails, `sleep` is called
   exactly `max_retries` times, never `max_retries + 1`. There is nothing left to wait
   for after the last failure.

6. **Re-raise the last exception.** When all attempts fail, re-raise the exception from
   the final attempt, unchanged: the same exception type and the same message. Do not
   wrap it in another exception type.

7. **Reject a negative `max_retries`.** If `max_retries < 0`, raise `ValueError` when the
   decorator is applied, with exactly this message:

   ```text
   max_retries must not be negative: -1
   ```

   that is, the fixed prefix `max_retries must not be negative: ` followed by the value.

8. **Preserve function metadata.** The returned wrapper keeps the wrapped function's
   `__name__` and `__doc__`.

## Examples

```python
calls = []
slept = []

@retry(max_retries=3, base_delay=0.5, factor=2.0, sleep=slept.append)
def flaky():
    """Docstring is preserved."""
    calls.append(1)
    if len(calls) < 3:
        raise ConnectionError("boom")
    return "ok"

assert flaky() == "ok"
assert len(calls) == 3       # two failures, then a success
assert slept == [0.5, 1.0]   # one sleep before each retry, none after the success
assert flaky.__name__ == "flaky"
```

```python
slept = []

@retry(max_retries=2, base_delay=1.0, factor=3.0, sleep=slept.append)
def always_fails():
    raise TimeoutError("still down")

try:
    always_fails()
except TimeoutError as exc:
    assert str(exc) == "still down"
assert slept == [1.0, 3.0]   # exactly max_retries sleeps, none after the last failure
```

```python
@retry(max_retries=5, exceptions=(ConnectionError,), sleep=lambda _: None)
def wrong_kind():
    raise KeyError("not retried")

# KeyError is not a ConnectionError, so it propagates on the first attempt.
```

## Behaviour that must not change

`compute_backoff_delays` keeps its current behaviour, including raising `ValueError`
for a negative `attempts`.

## Definition of done

`retry` satisfies all eight requirements above, and `compute_backoff_delays` is
unchanged.

Change only `retrying.py`. Do not edit any file under `tests/`.
