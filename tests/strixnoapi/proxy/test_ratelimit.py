"""Token-bucket rate limiter."""

from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

from strixnoapi.proxy.ratelimit import TokenBucket, rate_limit_check, reset_for_tests
from strixnoapi.proxy.settings import ProxySettings


def test_bucket_allows_burst():
    b = TokenBucket(capacity=5, refill_per_second=1.0, tokens=5.0, last_refill=time.monotonic())
    for _ in range(5):
        ok, _ = b.try_take()
        assert ok


def test_bucket_blocks_after_burst():
    b = TokenBucket(capacity=3, refill_per_second=1.0, tokens=3.0, last_refill=time.monotonic())
    for _ in range(3):
        assert b.try_take()[0]
    ok, wait = b.try_take()
    assert not ok
    assert wait > 0


def test_bucket_refills():
    b = TokenBucket(capacity=2, refill_per_second=100.0, tokens=0.0, last_refill=time.monotonic())
    time.sleep(0.1)
    ok, _ = b.try_take()
    assert ok


class FakeApp:
    def __init__(self, settings):
        self.state = type("S", (), {"settings": settings})()


class FakeRequest:
    def __init__(self, app, path="/v1/chat/completions"):
        self.app = app
        self.url = type("U", (), {"path": path})()


def test_rate_limit_check_under_limit(tmp_path):
    reset_for_tests()
    s = ProxySettings(
        port=9999,
        token="t",
        cli_mode="claude",
        audit_dir=tmp_path,
        rate_limit_rpm=60,
    )
    req = FakeRequest(FakeApp(s))
    for _ in range(5):
        rate_limit_check(req)  # should not raise


def test_rate_limit_check_blocks_over_limit(tmp_path):
    reset_for_tests()
    s = ProxySettings(
        port=9999,
        token="t",
        cli_mode="claude",
        audit_dir=tmp_path,
        rate_limit_rpm=3,
    )
    req = FakeRequest(FakeApp(s))
    rate_limit_check(req)
    rate_limit_check(req)
    rate_limit_check(req)
    with pytest.raises(HTTPException) as exc:
        rate_limit_check(req)
    assert exc.value.status_code == 429


def test_rate_limit_skips_health(tmp_path):
    reset_for_tests()
    s = ProxySettings(
        port=9999,
        token="t",
        cli_mode="claude",
        audit_dir=tmp_path,
        rate_limit_rpm=1,
    )
    req = FakeRequest(FakeApp(s), path="/health")
    for _ in range(10):
        rate_limit_check(req)  # exempt
