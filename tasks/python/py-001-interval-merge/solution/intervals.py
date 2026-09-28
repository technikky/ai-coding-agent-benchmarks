"""Interval arithmetic."""

from __future__ import annotations

Interval = tuple[int, int]


def merge_intervals(intervals: list[Interval]) -> list[Interval]:
    """Collapse overlapping or touching closed intervals into the smallest set.

    Returns a new list, sorted by start. The argument is not modified.

    Raises:
        ValueError: if any interval has start > end.
    """
    for interval in intervals:
        start, end = interval
        if start > end:
            raise ValueError(f"interval start must not exceed end: {(start, end)}")

    ordered: list[Interval] = sorted(
        (tuple(interval) for interval in intervals),  # type: ignore[misc]
        key=lambda pair: pair[0],
    )
    if not ordered:
        return []

    merged: list[Interval] = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        # Closed intervals: sharing an endpoint is enough to merge.
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def total_length(intervals: list[Interval]) -> int:
    """Total length covered by the intervals, counting each point once."""
    return sum(end - start for start, end in merge_intervals(list(intervals)))
