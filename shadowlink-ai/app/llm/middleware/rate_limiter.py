"""Rate limiter middleware — prevents exceeding provider rate limits.

Uses a token bucket algorithm for smooth rate limiting.
"""

from __future__ import annotations

import asyncio
import time

import structlog

logger = structlog.get_logger("llm.middleware.rate_limiter")


class RateLimiter:
    """Token bucket rate limiter for LLM API calls."""

    def __init__(self, max_requests_per_minute: int = 60, max_tokens_per_minute: int = 100_000):
        self.max_rpm = max_requests_per_minute
        self.max_tpm = max_tokens_per_minute
        self._request_tokens = float(max_requests_per_minute)
        self._token_tokens = float(max_tokens_per_minute)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, estimated_tokens: int = 1) -> None:
        """Wait until rate limit allows the request."""
        async with self._lock:
            self._refill()

            while self._request_tokens < 1 or self._token_tokens < estimated_tokens:
                wait = 1.0 / (self.max_rpm / 60)
                await asyncio.sleep(wait)
                self._refill()

            self._request_tokens -= 1
            self._token_tokens -= estimated_tokens

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._last_refill = now

        self._request_tokens = min(
            float(self.max_rpm),
            self._request_tokens + elapsed * (self.max_rpm / 60),
        )
        self._token_tokens = min(
            float(self.max_tpm),
            self._token_tokens + elapsed * (self.max_tpm / 60),
        )
