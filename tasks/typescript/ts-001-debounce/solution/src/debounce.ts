type AnyFn = (...args: never[]) => void;

/**
 * Delay `fn` until `waitMs` has passed with no further calls.
 *
 * Every call cancels a pending timer and starts a new one, so `fn` runs once,
 * `waitMs` after the last call of a burst, with that call's arguments.
 *
 * @throws RangeError if `waitMs` is negative or not finite.
 */
export function debounce<T extends AnyFn>(
  fn: T,
  waitMs: number,
): (...args: Parameters<T>) => void {
  if (!Number.isFinite(waitMs) || waitMs < 0) {
    throw new RangeError(
      `waitMs must be a non-negative finite number, received ${waitMs}`,
    );
  }

  let timer: ReturnType<typeof setTimeout> | null = null;
  let pendingArgs: Parameters<T> | null = null;

  return (...args: Parameters<T>): void => {
    pendingArgs = args;
    if (timer !== null) {
      clearTimeout(timer);
    }
    timer = setTimeout(() => {
      timer = null;
      const call = pendingArgs as Parameters<T>;
      pendingArgs = null;
      fn(...call);
    }, waitMs);
  };
}
