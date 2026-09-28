"""Visible tests, covering the helper that already works."""

import pytest

from retrying import compute_backoff_delays


def test_delays_grow_by_the_factor():
    assert compute_backoff_delays(4, base_delay=0.5, factor=2.0) == [0.5, 1.0, 2.0, 4.0]


def test_delays_are_capped_at_max_delay():
    assert compute_backoff_delays(4, base_delay=10.0, factor=10.0, max_delay=100.0) == [
        10.0,
        100.0,
        100.0,
        100.0,
    ]


def test_zero_attempts_produces_no_delays():
    assert compute_backoff_delays(0) == []


def test_negative_attempts_is_rejected():
    with pytest.raises(ValueError):
        compute_backoff_delays(-1)
