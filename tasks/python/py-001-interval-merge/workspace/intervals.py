"""Interval arithmetic."""

from __future__ import annotations

Interval = tuple[int, int]


def merge_intervals(intervals: list[Interval]) -> list[Interval]:
    """Collapse overlapping closed intervals into the smallest equivalent set.

    Returns a new list, sorted by start.
    """
    if not intervals:
        return []

    intervals.sort(key=lambda pair: pair[0])

    merged: list[Interval] = [tuple(intervals[0])]  # type: ignore[list-item]
    for interval in intervals[1:]:
        start, end = interval
        last_start, last_end = merged[-1]
        if start < last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def total_length(intervals: list[Interval]) -> int:
    """Total length covered by the intervals, counting each point once."""
    return sum(end - start for start, end in merge_intervals(list(intervals)))
