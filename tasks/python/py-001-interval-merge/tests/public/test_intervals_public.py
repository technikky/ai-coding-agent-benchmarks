"""Visible tests. These describe behaviour that already works."""

from intervals import merge_intervals


def test_empty_input_returns_an_empty_list():
    assert merge_intervals([]) == []


def test_a_single_interval_is_returned_unchanged():
    assert merge_intervals([(1, 3)]) == [(1, 3)]


def test_strictly_overlapping_intervals_merge():
    assert merge_intervals([(1, 5), (3, 8)]) == [(1, 8)]


def test_disjoint_intervals_stay_separate():
    assert merge_intervals([(1, 2), (5, 6)]) == [(1, 2), (5, 6)]


def test_a_fully_nested_interval_is_absorbed():
    assert merge_intervals([(1, 10), (3, 4)]) == [(1, 10)]


def test_output_is_sorted_by_start():
    assert merge_intervals([(5, 6), (1, 2)]) == [(1, 2), (5, 6)]
