"""Rate limiting middleware for MAOS API."""

import asyncio
import time

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import ASGIApp

logger = structlog.get_logger()

# Maximum number of tracked client IPs to prevent memory exhaustion
_MAX_BUCKETS = 10_000
# Buckets not accessed within this window (seconds) are eligible for eviction
_EVICTION_AGE = 600.0


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""

    enabled: bool = False
    requests_per_minute: int = Field(default=60, ge=1)
    burst_size: int = Field(default=10, ge=1)


class TokenBucket:
    """Token bucket rate limiter.

    Allows bursts up to `capacity` tokens, then refills at
    `rate` tokens per second.
    """

    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self) -> bool:
        """Try to consume one token. Returns True if allowed."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.rate,
            )
            self.last_refill = now
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-client rate limiting middleware using token bucket."""

    def __init__(self, app: ASGIApp, config: RateLimitConfig) -> None:
        super().__init__(app)
        self.config = config
        self._buckets: dict[str, TokenBucket] = {}
        self._buckets_lock = asyncio.Lock()

    def _get_or_create_bucket(self, client_id: str) -> TokenBucket:
        """Get or create a token bucket for the client, with eviction.

        Must be called while holding ``_buckets_lock``.
        """
        if client_id in self._buckets:
            return self._buckets[client_id]

        # Evict stale entries if at capacity
        if len(self._buckets) >= _MAX_BUCKETS:
            now = time.monotonic()
            stale = [
                k
                for k, v in self._buckets.items()
                if now - v.last_refill > _EVICTION_AGE
            ]
            for k in stale:
                del self._buckets[k]

            # If still at capacity after eviction, remove oldest entry
            if len(self._buckets) >= _MAX_BUCKETS:
                oldest_key = min(
                    self._buckets,
                    key=lambda k: self._buckets[k].last_refill,
                )
                del self._buckets[oldest_key]

        bucket = TokenBucket(
            rate=self.config.requests_per_minute / 60.0,
            capacity=self.config.burst_size,
        )
        self._buckets[client_id] = bucket
        return bucket

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Rate-limit incoming requests by client IP."""
        if not self.config.enabled:
            return await call_next(request)

        client_id = (
            request.client.host if request.client else "unknown"
        )
        async with self._buckets_lock:
            bucket = self._get_or_create_bucket(client_id)

        if not await bucket.consume():
            logger.warning(
                "rate_limit_exceeded",
                client=client_id,
                path=request.url.path,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": "60"},
            )

        return await call_next(request)
