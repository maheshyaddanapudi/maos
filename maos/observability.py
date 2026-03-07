"""Observability utilities for MAOS."""

import asyncio
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog

from maos.config.models import ObservabilityConfig  # noqa: F401

logger = structlog.get_logger()


# Optional OpenTelemetry integration
try:
    from opentelemetry import trace as otel_trace  # noqa: F401

    _has_otel = True
except ImportError:
    _has_otel = False


class RequestContext:
    """Per-request context for correlation."""

    def __init__(
        self,
        request_id: str,
        tenant_id: str | None = None,
    ):
        self.request_id = request_id
        self.tenant_id = tenant_id
        self.start_time = time.monotonic()
        self.spans: list[dict[str, Any]] = []

    def add_span(
        self,
        name: str,
        duration_ms: float,
        metadata: dict | None = None,
    ) -> None:
        """Record a completed span."""
        self.spans.append(
            {
                "name": name,
                "duration_ms": duration_ms,
                "metadata": metadata or {},
            }
        )

    @property
    def elapsed_ms(self) -> float:
        """Total elapsed time since context creation."""
        return (time.monotonic() - self.start_time) * 1000


@asynccontextmanager
async def trace_operation(
    name: str,
    context: RequestContext | None = None,
    **attrs: Any,
) -> AsyncIterator[None]:
    """Context manager to trace an async operation.

    Args:
        name: Operation name for logging and tracing.
        context: Optional request context for span recording.
        **attrs: Additional attributes to log.
    """
    start = time.monotonic()
    log = logger.bind(operation=name, **attrs)
    log.debug("operation_start")
    try:
        yield
    except Exception as e:
        duration_ms = (time.monotonic() - start) * 1000
        log.error(
            "operation_error",
            duration_ms=round(duration_ms, 2),
            error=str(e),
        )
        if context:
            context.add_span(name, duration_ms, {"error": str(e)})
        raise
    else:
        duration_ms = (time.monotonic() - start) * 1000
        log.info(
            "operation_complete",
            duration_ms=round(duration_ms, 2),
        )
        if context:
            context.add_span(name, duration_ms)


class CostTracker:
    """Tracks token usage and estimated costs."""

    # Approximate costs per 1M tokens (USD)
    MODEL_COSTS: dict[str, dict[str, float]] = {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "claude-sonnet-4-20250514": {
            "input": 3.00,
            "output": 15.00,
        },
        "claude-haiku-4-5-20251001": {
            "input": 0.80,
            "output": 4.00,
        },
        "claude-opus-4-20250514": {
            "input": 15.00,
            "output": 75.00,
        },
    }

    def __init__(self) -> None:
        self._usage: dict[str, dict[str, int]] = defaultdict(
            lambda: {"input": 0, "output": 0}
        )
        self._lock = asyncio.Lock()

    async def record(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record token usage for a model invocation.

        Args:
            model: Model name.
            input_tokens: Number of input tokens used.
            output_tokens: Number of output tokens used.
        """
        async with self._lock:
            self._usage[model]["input"] += input_tokens
            self._usage[model]["output"] += output_tokens

    async def get_total_cost(self) -> float:
        """Calculate total estimated cost in USD.

        Returns:
            Estimated total cost rounded to 6 decimal places.
        """
        async with self._lock:
            total = 0.0
            for model, usage in self._usage.items():
                costs = self.MODEL_COSTS.get(
                    model, {"input": 5.0, "output": 15.0}
                )
                total += (usage["input"] / 1_000_000) * costs["input"]
                total += (usage["output"] / 1_000_000) * costs["output"]
            return round(total, 6)

    async def get_usage_summary(self) -> dict[str, Any]:
        """Get a summary of usage by model and total cost.

        Returns:
            Dict with by_model breakdown and total_cost_usd.
        """
        async with self._lock:
            total = 0.0
            for model, usage in self._usage.items():
                costs = self.MODEL_COSTS.get(
                    model, {"input": 5.0, "output": 15.0}
                )
                total += (usage["input"] / 1_000_000) * costs["input"]
                total += (usage["output"] / 1_000_000) * costs["output"]
            return {
                "by_model": dict(self._usage),
                "total_cost_usd": round(total, 6),
            }

    async def reset(self) -> None:
        """Reset all tracked usage data."""
        async with self._lock:
            self._usage.clear()
