"""Retry helpers."""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


def compute_backoff_delays(
    attempts: int,
    base_delay: float = 0.5,
    factor: float = 2.0,
    max_delay: float = 30.0,
) -> list[float]:
    """Exponential backoff delays, each capped at ``max_delay``.

    Delay ``i`` is ``min(base_delay * factor ** i, max_delay)``.
    """
    if attempts < 0:
        raise ValueError(f"attempts must not be negative: {attempts}")
    return [min(base_delay * factor**index, max_delay) for index in range(attempts)]


def retry(
    max_retries: int = 2,
    *,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    base_delay: float = 0.5,
    factor: float = 2.0,
    max_delay: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry a callable with exponential backoff.

    The wrapped callable runs at most ``max_retries + 1`` times. ``sleep`` is called
    once before each retry with the corresponding backoff delay, and never after the
    final attempt.
    """
    if max_retries < 0:
        raise ValueError(f"max_retries must not be negative: {max_retries}")

    delays = compute_backoff_delays(max_retries, base_delay, factor, max_delay)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    # The final attempt has nothing left to wait for, so re-raise
                    # rather than sleeping and looping.
                    if attempt == max_retries:
                        raise
                    sleep(delays[attempt])
            raise AssertionError("unreachable: the loop either returns or raises")

        return wrapper

    return decorator
