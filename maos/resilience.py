"""Resilience utilities: retry with backoff and circuit breaker."""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

import structlog

logger = structlog.get_logger()

T = TypeVar("T")


async def retry_with_backoff(
    fn: Callable[..., Awaitable[T]],
    *args: object,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs: object,
) -> T:
    """
    Retry an async function with exponential backoff.

    Args:
        fn: Async callable to retry.
        *args: Positional arguments for fn.
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay in seconds for backoff.
        max_delay: Maximum delay cap in seconds.
        jitter: Whether to add random jitter to delay.
        retryable_exceptions: Exception types that trigger retry.
        **kwargs: Keyword arguments for fn.

    Returns:
        The result of fn.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except retryable_exceptions as exc:
            last_exception = exc

            if attempt >= max_retries:
                logger.warning(
                    "retry_exhausted",
                    fn=getattr(fn, "__name__", str(fn)),
                    attempts=attempt + 1,
                    error=str(exc),
                )
                raise

            delay = min(
                (2**attempt) * base_delay,
                max_delay,
            )
            if jitter:
                delay += random.uniform(0, delay * 0.5)  # noqa: S311

            logger.info(
                "retry_attempt",
                fn=getattr(fn, "__name__", str(fn)),
                attempt=attempt + 1,
                max_retries=max_retries,
                delay=round(delay, 2),
                error=str(exc),
            )
            await asyncio.sleep(delay)

    # Should not reach here, but satisfy type checker
    raise last_exception  # type: ignore[misc]


class CircuitBreaker:
    """Circuit breaker for protecting async calls.

    States:
        closed  - Normal operation; failures are counted.
        open    - Calls fail immediately; waits for recovery.
        half_open - Allows limited test calls to probe recovery.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 2,
    ) -> None:
        """
        Initialize circuit breaker.

        Args:
            name: Identifier for logging.
            failure_threshold: Failures before opening.
            recovery_timeout: Seconds before trying half-open.
            half_open_max_calls: Test calls allowed in half-open.
        """
        self._name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        self._state = "closed"
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        """Current circuit state: closed, open, or half_open."""
        if self._state == "open":
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                return "half_open"
        return self._state

    async def call(
        self,
        fn: Callable[..., Awaitable[T]],
        *args: object,
        **kwargs: object,
    ) -> T:
        """
        Execute fn through the circuit breaker.

        Args:
            fn: Async callable to protect.
            *args: Positional arguments for fn.
            **kwargs: Keyword arguments for fn.

        Returns:
            The result of fn.

        Raises:
            RuntimeError: If circuit is open.
            Exception: If fn raises and breaker opens.
        """
        async with self._lock:
            current = self.state

            if current == "open":
                raise RuntimeError(
                    f"Circuit breaker '{self._name}' is open"
                )

            if current == "half_open":
                if self._half_open_calls >= self._half_open_max_calls:
                    raise RuntimeError(
                        f"Circuit breaker '{self._name}' "
                        f"half-open limit reached"
                    )
                self._half_open_calls += 1

        try:
            result = await fn(*args, **kwargs)
        except Exception as exc:
            await self._record_failure(exc)
            raise
        else:
            await self._record_success()
            return result

    async def _record_failure(self, exc: Exception) -> None:
        """Record a failure and possibly open the circuit."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._failure_count >= self._failure_threshold:
                prev = self._state
                self._state = "open"
                if prev != "open":
                    logger.warning(
                        "circuit_breaker_opened",
                        name=self._name,
                        failures=self._failure_count,
                        error=str(exc),
                    )

    async def _record_success(self) -> None:
        """Record a success and possibly close the circuit."""
        async with self._lock:
            if self._state in ("half_open", "open"):
                prev = self._state
                self._state = "closed"
                self._failure_count = 0
                self._half_open_calls = 0
                logger.info(
                    "circuit_breaker_closed",
                    name=self._name,
                    previous_state=prev,
                )
            else:
                # Reset consecutive failure count on success
                self._failure_count = 0
