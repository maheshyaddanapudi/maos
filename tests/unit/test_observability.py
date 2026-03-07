"""Unit tests for observability module."""

import asyncio

import pytest

from maos.observability import ObservabilityConfig, RequestContext, trace_operation


@pytest.mark.unit
class TestObservabilityConfig:
    """Tests for ObservabilityConfig."""

    def test_default_values(self):
        """Test that defaults are applied correctly."""
        config = ObservabilityConfig()

        assert config.tracing_enabled is False
        assert config.metrics_enabled is False
        assert config.log_prompts is False
        assert config.log_tool_calls is True

    def test_custom_values(self):
        """Test that custom values override defaults."""
        config = ObservabilityConfig(
            tracing_enabled=True,
            metrics_enabled=True,
            log_prompts=True,
            log_tool_calls=False,
        )

        assert config.tracing_enabled is True
        assert config.metrics_enabled is True
        assert config.log_prompts is True
        assert config.log_tool_calls is False


@pytest.mark.unit
class TestRequestContext:
    """Tests for RequestContext."""

    def test_creation_with_request_id(self):
        """Test basic creation with request_id."""
        ctx = RequestContext(request_id="req-123")

        assert ctx.request_id == "req-123"
        assert ctx.tenant_id is None
        assert ctx.spans == []

    def test_creation_with_tenant(self):
        """Test creation with tenant_id."""
        ctx = RequestContext(request_id="req-456", tenant_id="tenant-a")

        assert ctx.request_id == "req-456"
        assert ctx.tenant_id == "tenant-a"

    def test_add_span_records_spans(self):
        """Test that add_span records spans correctly."""
        ctx = RequestContext(request_id="req-789")

        ctx.add_span("llm_call", 150.5, {"model": "gpt-4"})
        ctx.add_span("tool_call", 30.0)

        assert len(ctx.spans) == 2
        assert ctx.spans[0]["name"] == "llm_call"
        assert ctx.spans[0]["duration_ms"] == 150.5
        assert ctx.spans[0]["metadata"] == {"model": "gpt-4"}
        assert ctx.spans[1]["name"] == "tool_call"
        assert ctx.spans[1]["metadata"] == {}

    async def test_elapsed_ms_increases_over_time(self):
        """Test that elapsed_ms increases as time passes."""
        ctx = RequestContext(request_id="req-time")

        t1 = ctx.elapsed_ms
        await asyncio.sleep(0.05)
        t2 = ctx.elapsed_ms

        assert t2 > t1
        assert t2 >= 40  # at least ~50ms minus scheduling variance


@pytest.mark.unit
class TestTraceOperation:
    """Tests for trace_operation context manager."""

    async def test_successful_operation_completes(self):
        """Test that a successful operation completes without error."""
        async with trace_operation("test_op"):
            pass

        # If no exception is raised, the operation succeeded.

    async def test_failed_operation_reraises(self):
        """Test that a failed operation logs error and re-raises."""
        with pytest.raises(ValueError, match="boom"):
            async with trace_operation("failing_op"):
                raise ValueError("boom")

    async def test_context_span_tracking_on_success(self):
        """Test that trace_operation records a span on the context."""
        ctx = RequestContext(request_id="req-span")

        async with trace_operation("tracked_op", context=ctx):
            await asyncio.sleep(0.01)

        assert len(ctx.spans) == 1
        assert ctx.spans[0]["name"] == "tracked_op"
        assert ctx.spans[0]["duration_ms"] > 0
        assert ctx.spans[0]["metadata"] == {}

    async def test_context_span_tracking_on_failure(self):
        """Test that trace_operation records error span on failure."""
        ctx = RequestContext(request_id="req-err")

        with pytest.raises(RuntimeError):
            async with trace_operation("error_op", context=ctx):
                raise RuntimeError("oops")

        assert len(ctx.spans) == 1
        assert ctx.spans[0]["name"] == "error_op"
        assert ctx.spans[0]["metadata"] == {"error": "oops"}
        assert ctx.spans[0]["duration_ms"] >= 0
