"""Graded tests for the retry decorator."""

import pytest

from retrying import retry


def test_a_successful_call_runs_once_and_never_sleeps():
    calls: list[int] = []
    slept: list[float] = []

    @retry(max_retries=3, sleep=slept.append)
    def succeed() -> str:
        calls.append(1)
        return "ok"

    assert succeed() == "ok"
    assert len(calls) == 1
    assert slept == []


def test_the_return_value_is_passed_through():
    @retry(max_retries=1, sleep=lambda _: None)
    def add(left: int, right: int, *, offset: int = 0) -> int:
        return left + right + offset

    assert add(2, 3, offset=5) == 10


def test_total_attempts_is_max_retries_plus_one():
    calls: list[int] = []

    @retry(max_retries=3, sleep=lambda _: None)
    def always_fails() -> None:
        calls.append(1)
        raise ConnectionError("down")

    with pytest.raises(ConnectionError):
        always_fails()

    assert len(calls) == 4


def test_sleep_is_never_called_after_the_final_attempt():
    slept: list[float] = []

    @retry(max_retries=2, base_delay=1.0, factor=3.0, sleep=slept.append)
    def always_fails() -> None:
        raise TimeoutError("still down")

    with pytest.raises(TimeoutError):
        always_fails()

    # Exactly max_retries sleeps: one before each retry, none after the last failure.
    assert len(slept) == 2


def test_the_sleep_durations_follow_the_backoff_schedule():
    slept: list[float] = []
    calls: list[int] = []

    @retry(max_retries=3, base_delay=0.5, factor=2.0, sleep=slept.append)
    def flaky() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("boom")
        return "ok"

    assert flaky() == "ok"
    assert calls == [1, 1, 1]
    assert slept == [0.5, 1.0]


def test_the_last_exception_is_reraised_unchanged():
    @retry(max_retries=2, sleep=lambda _: None)
    def always_fails() -> None:
        raise TimeoutError("still down")

    with pytest.raises(TimeoutError) as excinfo:
        always_fails()

    assert str(excinfo.value) == "still down"


def test_an_unlisted_exception_is_not_retried():
    calls: list[int] = []
    slept: list[float] = []

    @retry(max_retries=5, exceptions=(ConnectionError,), sleep=slept.append)
    def wrong_kind() -> None:
        calls.append(1)
        raise KeyError("not retried")

    with pytest.raises(KeyError):
        wrong_kind()

    assert len(calls) == 1
    assert slept == []


def test_zero_retries_means_a_single_attempt():
    calls: list[int] = []
    slept: list[float] = []

    @retry(max_retries=0, sleep=slept.append)
    def always_fails() -> None:
        calls.append(1)
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError):
        always_fails()

    assert len(calls) == 1
    assert slept == []


def test_a_negative_max_retries_raises_value_error():
    with pytest.raises(ValueError) as excinfo:
        retry(max_retries=-1)

    assert str(excinfo.value) == "max_retries must not be negative: -1"


def test_the_wrapper_keeps_the_name_and_docstring():
    @retry(max_retries=1, sleep=lambda _: None)
    def documented() -> None:
        """A docstring worth keeping."""

    assert documented.__name__ == "documented"
    assert documented.__doc__ == "A docstring worth keeping."
