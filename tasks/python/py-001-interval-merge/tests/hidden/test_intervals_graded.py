"""Graded tests. Withheld from the agent until grading."""

import pytest

from intervals import merge_intervals


def test_touching_intervals_are_merged():
    # Closed intervals: (1, 2) and (2, 3) both contain 2.
    assert merge_intervals([(1, 2), (2, 3)]) == [(1, 3)]


def test_a_chain_of_touching_intervals_collapses_to_one():
    assert merge_intervals([(1, 2), (2, 3), (3, 4)]) == [(1, 4)]


def test_the_input_list_is_not_mutated():
    original = [(5, 6), (1, 2), (2, 4)]
    snapshot = list(original)

    assert merge_intervals(original) == [(1, 4), (5, 6)]
    assert original == snapshot, "merge_intervals reordered the caller's list"


def test_an_inverted_interval_raises_value_error():
    with pytest.raises(ValueError):
        merge_intervals([(1, 2), (3, 1)])


def test_the_error_message_names_the_offending_interval():
    # The first offending interval in input order, formatted as a Python tuple.
    with pytest.raises(ValueError) as excinfo:
        merge_intervals([(1, 2), (3, 1), (9, 0)])

    assert str(excinfo.value) == "interval start must not exceed end: (3, 1)"


def test_a_single_point_interval_is_valid():
    assert merge_intervals([(4, 4)]) == [(4, 4)]
