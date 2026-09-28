# Fix `debounce`

`src/debounce.ts` exports `debounce`, which is meant to delay a callback until a burst
of calls has stopped. It currently behaves like a throttle, and it has two further
defects.

## Context

```ts
export function debounce<T extends AnyFn>(fn: T, waitMs: number): (...args: Parameters<T>) => void
```

`debounce(fn, waitMs)` returns a wrapper. Calling the wrapper schedules `fn` to run
`waitMs` milliseconds later. The three defects in the current implementation are that
it ignores calls made while a timer is already pending, that it remembers the arguments
from the *first* call of a burst rather than the last, and that it accepts any
`waitMs` at all.

The tests drive time with `vi.useFakeTimers()` and `vi.advanceTimersByTime()`, so the
implementation must schedule work with `setTimeout` and cancel it with `clearTimeout`.

## Requirements

1. **Each call restarts the wait.** Calling the wrapper while a timer is pending cancels
   that timer and starts a new one. `fn` therefore runs `waitMs` after the **last** call
   in a burst, not `waitMs` after the first. Given `waitMs = 100` and calls at `t = 0`
   and `t = 50`, `fn` runs at `t = 150` and must not have run at `t = 100`.

2. **The most recent arguments win.** `fn` receives the arguments from the call that
   started the wait window that actually elapsed. Calling the wrapper with `"a"` and
   then `"b"` inside the window invokes `fn("b")` exactly once.

3. **Reject an invalid wait.** If `waitMs` is negative, or is not a finite number, throw
   a `RangeError` from `debounce` itself, before any wrapper is returned. The message
   must be exactly:

   ```text
   waitMs must be a non-negative finite number, received -1
   ```

   that is, the fixed prefix `waitMs must be a non-negative finite number, received `
   followed by the offending value. `waitMs = 0` is valid.

## Behaviour that must not change

- `debounce` returns a function.
- `fn` is not invoked before `waitMs` has elapsed.
- A single call invokes `fn` exactly once.
- A burst of calls invokes `fn` exactly once in total.
- After `fn` runs, a later call starts a fresh wait window and invokes `fn` again.

## Examples

```ts
vi.useFakeTimers();
const spy = vi.fn();
const debounced = debounce(spy, 100);

debounced("a");
vi.advanceTimersByTime(50);
debounced("b");          // restarts the 100ms wait

vi.advanceTimersByTime(50);   // t = 100, only 50ms since the last call
expect(spy).not.toHaveBeenCalled();

vi.advanceTimersByTime(50);   // t = 150
expect(spy).toHaveBeenCalledTimes(1);
expect(spy).toHaveBeenCalledWith("b");
```

```ts
expect(() => debounce(() => {}, -1)).toThrow(RangeError);
// message: "waitMs must be a non-negative finite number, received -1"
```

## Definition of done

`debounce` restarts its timer on every call, invokes the callback with the latest
arguments, and throws `RangeError` with the exact message above for an invalid
`waitMs`, while every behaviour listed under "Behaviour that must not change" still
holds.

Change only `src/debounce.ts`. Do not edit any file under `tests/`.
