type AnyFn = (...args: never[]) => void;

/**
 * Delay `fn` until `waitMs` has passed.
 */
export function debounce<T extends AnyFn>(
  fn: T,
  waitMs: number,
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout> | null = null;
  let firstArgs: Parameters<T> | null = null;

  return (...args: Parameters<T>): void => {
    if (firstArgs === null) {
      firstArgs = args;
    }
    if (timer !== null) {
      return;
    }
    timer = setTimeout(() => {
      timer = null;
      const call = firstArgs as Parameters<T>;
      firstArgs = null;
      fn(...call);
    }, waitMs);
  };
}
