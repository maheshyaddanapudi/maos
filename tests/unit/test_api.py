"""Unit tests for API module."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from maos.api.models import (
    AgentInfo,
    AgentListResponse,
    ChatRequest,
    ChatResponse,
    ComponentHealth,
    ErrorResponse,
    HealthResponse,
    HealthStatus,
    InputRequiredResponse,
    Message,
    MessageRole,
    OpenAIChatRequest,
    OpenAIChatResponse,
    OpenAIMessage,
    ResumeRequest,
    StreamEvent,
    StreamEventType,
    WorkerResultInfo,
)
from maos.api.streaming import format_sse_event, create_stream_event


class TestMessage:
    """Tests for Message model."""

    def test_user_message(self):
        """Test user message creation."""
        msg = Message(role=MessageRole.USER, content="Hello")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"

    def test_message_with_name(self):
        """Test message with name."""
        msg = Message(
            role=MessageRole.ASSISTANT,
            content="Response",
            name="worker1"
        )
        assert msg.name == "worker1"


class TestChatRequest:
    """Tests for ChatRequest model."""

    def test_minimal_request(self):
        """Test minimal chat request."""
        request = ChatRequest(
            messages=[Message(role=MessageRole.USER, content="Hello")]
        )
        assert len(request.messages) == 1
        assert not request.stream

    def test_streaming_request(self):
        """Test streaming chat request."""
        request = ChatRequest(
            messages=[Message(role=MessageRole.USER, content="Hello")],
            stream=True,
            thread_id="test-123"
        )
        assert request.stream
        assert request.thread_id == "test-123"

    def test_empty_messages_rejected(self):
        """Test that empty messages list is rejected."""
        with pytest.raises(ValueError):
            ChatRequest(messages=[])


class TestChatResponse:
    """Tests for ChatResponse model."""

    def test_basic_response(self):
        """Test basic chat response."""
        response = ChatResponse(
            thread_id="thread-1",
            messages=[Message(role=MessageRole.ASSISTANT, content="Hi")],
            final_response="Hi",
            iterations=1
        )
        assert response.done
        assert response.iterations == 1


class TestInputRequiredResponse:
    """Tests for InputRequiredResponse model."""

    def test_input_required(self):
        """Test input required response."""
        response = InputRequiredResponse(
            thread_id="thread-1",
            prompt="What is your name?"
        )
        assert response.input_required
        assert response.prompt == "What is your name?"


class TestResumeRequest:
    """Tests for ResumeRequest model."""

    def test_resume_request(self):
        """Test resume request."""
        request = ResumeRequest(
            thread_id="thread-1",
            input="My name is Alice"
        )
        assert request.thread_id == "thread-1"
        assert request.input == "My name is Alice"


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_healthy_response(self):
        """Test healthy response."""
        response = HealthResponse(
            status=HealthStatus.HEALTHY,
            components=[
                ComponentHealth(
                    name="llm_registry",
                    status=HealthStatus.HEALTHY,
                    message="2 adapters registered"
                )
            ]
        )
        assert response.status == HealthStatus.HEALTHY

    def test_degraded_response(self):
        """Test degraded response."""
        response = HealthResponse(
            status=HealthStatus.DEGRADED,
            components=[
                ComponentHealth(
                    name="mcp_registry",
                    status=HealthStatus.DEGRADED,
                    message="1/2 servers connected"
                )
            ]
        )
        assert response.status == HealthStatus.DEGRADED


class TestAgentInfo:
    """Tests for AgentInfo model."""

    def test_supervisor_info(self):
        """Test supervisor agent info."""
        info = AgentInfo(
            name="supervisor",
            kind="supervisor",
            description="Routes tasks"
        )
        assert info.kind == "supervisor"

    def test_worker_info(self):
        """Test worker agent info."""
        info = AgentInfo(
            name="researcher",
            kind="native_worker",
            llm="default",
            tools=["search", "read"]
        )
        assert len(info.tools) == 2


class TestOpenAIModels:
    """Tests for OpenAI-compatible models."""

    def test_openai_chat_request(self):
        """Test OpenAI chat request."""
        request = OpenAIChatRequest(
            model="maos",
            messages=[OpenAIMessage(role="user", content="Hello")]
        )
        assert request.model == "maos"
        assert not request.stream

    def test_openai_chat_response(self):
        """Test OpenAI chat response."""
        response = OpenAIChatResponse(
            id="chatcmpl-123",
            created=1234567890,
            choices=[],
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        )
        assert response.object == "chat.completion"


class TestStreamingHelpers:
    """Tests for streaming helper functions."""

    def test_format_sse_event(self):
        """Test SSE event formatting."""
        sse = format_sse_event("chunk", {"content": "Hello"})

        assert "event: chunk" in sse
        assert "data:" in sse
        assert "Hello" in sse
        assert sse.endswith("\n\n")

    def test_create_stream_event(self):
        """Test creating stream event."""
        event = create_stream_event(
            StreamEventType.CHUNK,
            {"content": "Test"}
        )

        assert event.event == StreamEventType.CHUNK
        assert event.data["content"] == "Test"
        assert event.timestamp is not None


class TestWorkerResultInfo:
    """Tests for WorkerResultInfo model."""

    def test_basic_result(self):
        """Test basic worker result info."""
        result = WorkerResultInfo(
            from_agent="worker1",
            content="Task completed",
            duration_ms=100
        )
        assert result.from_agent == "worker1"
        assert result.result_type == "text"

    def test_result_with_tool_calls(self):
        """Test worker result with tool calls."""
        from maos.api.models import ToolCallInfo

        result = WorkerResultInfo(
            from_agent="worker1",
            content="Found results",
            tool_calls=[
                ToolCallInfo(
                    tool_id="tool_1",
                    tool_name="search",
                    input_args={"query": "test"},
                    output={"results": []},
                    success=True
                )
            ]
        )
        assert len(result.tool_calls) == 1


class TestStreamEventType:
    """Tests for StreamEventType enum."""

    def test_event_types(self):
        """Test all event type values."""
        assert StreamEventType.CHUNK.value == "chunk"
        assert StreamEventType.TOOL_CALL.value == "tool_call"
        assert StreamEventType.DONE.value == "done"
        assert StreamEventType.INPUT_REQUIRED.value == "input_required"
        assert StreamEventType.ERROR.value == "error"
