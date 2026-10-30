from datetime import UTC, datetime, timedelta

import pytest

from daftar.clock import FixedClock
from daftar.problems import ApiError
from daftar.throttle import LoginThrottle, RateLimiter


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(datetime(2026, 10, 30, 8, 0, tzinfo=UTC))


def test_five_attempts_per_email_and_ip(clock: FixedClock) -> None:
    t = LoginThrottle(clock)
    assert all(t.reserve("a@x.tn", "1.1.1.1") for _ in range(5))
    assert not t.reserve("a@x.tn", "1.1.1.1")
    assert t.reserve("a@x.tn", "2.2.2.2")  # another IP has its own budget
    assert t.reserve("b@x.tn", "1.1.1.1")  # another e-mail from the same IP too


def test_twenty_attempts_per_ip(clock: FixedClock) -> None:
    t = LoginThrottle(clock)
    for i in range(20):
        assert t.reserve(f"user{i}@x.tn", "1.1.1.1")
    assert not t.reserve("new@x.tn", "1.1.1.1")


def test_window_is_fifteen_minutes(clock: FixedClock) -> None:
    t = LoginThrottle(clock)
    for _ in range(5):
        t.reserve("a@x.tn", "1.1.1.1")
    clock.advance(minutes=14, seconds=59)
    assert not t.reserve("a@x.tn", "1.1.1.1")
    clock.advance(seconds=1)
    assert t.reserve("a@x.tn", "1.1.1.1")


def test_success_clears_the_email_ip_bucket(clock: FixedClock) -> None:
    t = LoginThrottle(clock)
    for _ in range(4):
        t.reserve("a@x.tn", "1.1.1.1")
    t.success("a@x.tn", "1.1.1.1")
    assert all(t.reserve("a@x.tn", "1.1.1.1") for _ in range(5))


def test_single_keys(clock: FixedClock) -> None:
    t = LoginThrottle(clock)
    assert all(t.reserve_key("password:1") for _ in range(5))
    assert not t.reserve_key("password:1")
    assert t.reserve_key("password:2")
    t.clear_key("password:1")
    assert t.reserve_key("password:1")


def test_memory_is_released_after_the_window(clock: FixedClock) -> None:
    t = LoginThrottle(clock)
    for i in range(50):
        t.reserve(f"user{i}@x.tn", f"10.0.0.{i}")
    assert t.size() == 100
    clock.advance(minutes=16)
    assert t.size() == 0


def test_rate_limiter_counts_per_key(clock: FixedClock) -> None:
    limiter = RateLimiter(clock, 2, timedelta(hours=1))
    assert limiter.hit("1.1.1.1") and limiter.hit("1.1.1.1")
    assert not limiter.hit("1.1.1.1")
    assert limiter.allowed("2.2.2.2")
    assert not limiter.allowed("1.1.1.1")
    clock.advance(hours=1)
    assert limiter.hit("1.1.1.1")


def test_rate_limiter_enforce_raises_429_with_retry_after(clock: FixedClock) -> None:
    limiter = RateLimiter(clock, 1, timedelta(hours=1))
    limiter.enforce("1.1.1.1")
    clock.advance(minutes=30)
    with pytest.raises(ApiError) as caught:
        limiter.enforce("1.1.1.1")
    assert caught.value.status == 429
    assert caught.value.code == "too_many_requests"
    assert caught.value.headers == {"Retry-After": "1801"}


def test_rate_limiter_global_key_and_reset(clock: FixedClock) -> None:
    limiter = RateLimiter(clock, 3, timedelta(days=1))
    for _ in range(3):
        limiter.enforce()
    assert not limiter.allowed()
    limiter.reset()
    assert limiter.allowed()
    with pytest.raises(ValueError):
        RateLimiter(clock, 0, timedelta(hours=1))
