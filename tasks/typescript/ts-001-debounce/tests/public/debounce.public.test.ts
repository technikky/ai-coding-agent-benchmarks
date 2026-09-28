import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { debounce } from "../../src/debounce";

describe("debounce (visible)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns a function", () => {
    expect(typeof debounce(() => {}, 50)).toBe("function");
  });

  it("does not invoke the callback before the wait elapses", () => {
    const spy = vi.fn();
    debounce(spy, 100)();

    vi.advanceTimersByTime(99);
    expect(spy).not.toHaveBeenCalled();
  });

  it("invokes the callback once for a single call", () => {
    const spy = vi.fn();
    debounce(spy, 100)();

    vi.advanceTimersByTime(100);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("invokes the callback only once for a burst of calls", () => {
    const spy = vi.fn();
    const debounced = debounce(spy, 100);

    debounced();
    debounced();
    debounced();

    vi.advanceTimersByTime(1000);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("starts a fresh wait window after invoking", () => {
    const spy = vi.fn();
    const debounced = debounce(spy, 100);

    debounced();
    vi.advanceTimersByTime(100);
    expect(spy).toHaveBeenCalledTimes(1);

    debounced();
    vi.advanceTimersByTime(100);
    expect(spy).toHaveBeenCalledTimes(2);
  });
});
