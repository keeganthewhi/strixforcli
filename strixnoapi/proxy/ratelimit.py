"""Token-bucket rate limiter — one bucket per proxy process."""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request


if TYPE_CHECKING:
    from strixnoapi.proxy.settings import ProxySettings


@dataclass
class TokenBucket:
    capacity: float
    refill_per_second: float
    tokens: float
    last_refill: float

    def try_take(self, cost: float = 1.0) -> tuple[bool, float]:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        self.last_refill = now
        if self.tokens >= cost:
            self.tokens -= cost
            return True, 0.0
        deficit = cost - self.tokens
        wait = deficit / self.refill_per_second if self.refill_per_second > 0 else float("inf")
        return False, wait


_lock = Lock()
_bucket: TokenBucket | None = None


def _get_bucket(rpm: int) -> TokenBucket:
    global _bucket
    if _bucket is None:
        _bucket = TokenBucket(
            capacity=float(rpm),
            refill_per_second=rpm / 60.0,
            tokens=float(rpm),
            last_refill=time.monotonic(),
        )
    return _bucket


def rate_limit_check(request: Request) -> None:
    if request.url.path in {"/health", "/healthz", "/"}:
        return
    settings: ProxySettings = request.app.state.settings
    with _lock:
        bucket = _get_bucket(settings.rate_limit_rpm)
        allowed, wait = bucket.try_take()
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"rate limit exceeded, retry in {wait:.1f}s",
            headers={"Retry-After": str(int(wait) + 1)},
        )


def reset_for_tests() -> None:
    """Test-only hook."""
    global _bucket
    with _lock:
        _bucket = None
