import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { debounce } from "../../src/debounce";

describe("debounce (graded)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("resets the pending timer when called again inside the wait window", () => {
    const spy = vi.fn();
    const debounced = debounce(spy, 100);

    debounced();
    vi.advanceTimersByTime(50);
    debounced();

    // t = 100, but only 50ms since the most recent call.
    vi.advanceTimersByTime(50);
    expect(spy).not.toHaveBeenCalled();

    vi.advanceTimersByTime(50);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("pushes the deadline further on every call in a burst", () => {
    const spy = vi.fn();
    const debounced = debounce(spy, 100);

    debounced();
    vi.advanceTimersByTime(90);
    debounced();
    vi.advanceTimersByTime(90);
    debounced();

    vi.advanceTimersByTime(99);
    expect(spy).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("invokes the callback with the arguments from the most recent call", () => {
    const spy = vi.fn();
    const debounced = debounce(spy, 100);

    debounced("a");
    vi.advanceTimersByTime(10);
    debounced("b");

    vi.advanceTimersByTime(100);
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith("b");
  });

  it("throws a RangeError when waitMs is negative", () => {
    expect(() => debounce(() => {}, -1)).toThrow(RangeError);
    expect(() => debounce(() => {}, -1)).toThrow(
      "waitMs must be a non-negative finite number, received -1",
    );
  });
});
