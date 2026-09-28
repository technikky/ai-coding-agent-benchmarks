"""Retry helpers."""

from __future__ import annotations

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

    Not implemented yet. See SPEC.md.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: Any, **kwargs: Any) -> T:
            raise NotImplementedError("retry() is not implemented yet; see SPEC.md")

        return wrapper

    return decorator
