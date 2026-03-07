"""Rate limiting middleware for MAOS API."""

import asyncio
import time
from collections import defaultdict

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


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

    def __init__(self, app, config: RateLimitConfig):
        super().__init__(app)
        self.config = config
        self._buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(
                rate=config.requests_per_minute / 60.0,
                capacity=config.burst_size,
            )
        )

    async def dispatch(self, request: Request, call_next):
        """Rate-limit incoming requests by client IP."""
        if not self.config.enabled:
            return await call_next(request)

        client_id = (
            request.client.host if request.client else "unknown"
        )
        bucket = self._buckets[client_id]

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
