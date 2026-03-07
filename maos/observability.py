"""Observability utilities for MAOS."""

import time
from contextlib import asynccontextmanager
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class ObservabilityConfig(BaseModel):
    """Observability configuration."""

    tracing_enabled: bool = Field(
        default=False,
        description="Enable distributed tracing",
    )
    metrics_enabled: bool = Field(
        default=False,
        description="Enable metrics collection",
    )
    log_prompts: bool = Field(
        default=False,
        description="Log LLM prompts (may contain sensitive data)",
    )
    log_tool_calls: bool = Field(
        default=True,
        description="Log tool call invocations and results",
    )


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
    ):
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
    **attrs,
):
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
            context.add_span(
                name, duration_ms, {"error": str(e)}
            )
        raise
    else:
        duration_ms = (time.monotonic() - start) * 1000
        log.info(
            "operation_complete",
            duration_ms=round(duration_ms, 2),
        )
        if context:
            context.add_span(name, duration_ms)
