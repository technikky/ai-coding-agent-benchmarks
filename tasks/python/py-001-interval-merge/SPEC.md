# Merge intervals

`intervals.py` provides `merge_intervals`, which collapses a collection of closed
integer intervals into the smallest equivalent set. It currently has three defects.

## Context

An interval is a 2-tuple `(start, end)` representing the **closed** range from `start`
to `end`, so both endpoints are inside the interval. `merge_intervals` takes a list of
such tuples and returns a new list of merged tuples.

The existing implementation handles the common case of strictly overlapping intervals.
It fails on intervals that only touch, it rejects nothing, and it reorders the list it
was given.

## Requirements

Modify `intervals.py` so that `merge_intervals(intervals)` behaves as follows.

1. **Touching intervals merge.** Two intervals merge when they overlap *or* when they
   share an endpoint. Because the intervals are closed, `(1, 2)` and `(2, 3)` both
   contain `2`, so they merge into `(1, 3)`. Merge when
   `next_start <= current_end`, not when `next_start < current_end`.

2. **The input is never modified.** `merge_intervals` must not sort, reorder or
   otherwise alter the list passed to it, nor any tuple inside it. After the call, the
   caller's list must compare equal to what it was before.

3. **Inverted intervals are rejected.** If any interval has `start > end`, raise
   `ValueError`. Check the intervals in the order they appear in the input and raise on
   the first offending one, before doing any merging. The exception message must be
   exactly:

   ```text
   interval start must not exceed end: (3, 1)
   ```

   that is, the fixed prefix `interval start must not exceed end: ` followed by the
   offending interval formatted as a Python tuple. An interval where `start == end`,
   such as `(4, 4)`, is valid and represents a single point.

## Behaviour that must not change

- An empty input returns an empty list.
- The returned list is sorted by `start`, ascending.
- The input may arrive in any order.
- Every element of the returned list is a `tuple`, even if the input contained lists.
- A fully nested interval is absorbed: `[(1, 10), (3, 4)]` merges to `[(1, 10)]`.

## Examples

```python
>>> merge_intervals([(1, 5), (3, 8)])
[(1, 8)]
>>> merge_intervals([(1, 2), (2, 3)])
[(1, 3)]
>>> merge_intervals([(5, 6), (1, 2)])
[(1, 2), (5, 6)]
>>> merge_intervals([(1, 2), (2, 3), (3, 4)])
[(1, 4)]
>>> merge_intervals([])
[]
>>> merge_intervals([(4, 4)])
[(4, 4)]
>>> merge_intervals([(1, 2), (3, 1)])
Traceback (most recent call last):
ValueError: interval start must not exceed end: (3, 1)
```

```python
>>> original = [(5, 6), (1, 2)]
>>> merge_intervals(original)
[(1, 2), (5, 6)]
>>> original
[(5, 6), (1, 2)]
```

## Definition of done

`merge_intervals` merges touching intervals, leaves its argument untouched, and raises
`ValueError` with the exact message above for an inverted interval, while every
behaviour listed under "Behaviour that must not change" still holds.

Change only `intervals.py`. Do not edit any file under `tests/`.
