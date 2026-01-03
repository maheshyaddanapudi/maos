"""End-to-end tests for chat functionality."""

import pytest
from unittest.mock import MagicMock


@pytest.mark.e2e
class TestAPIModelsE2E:
    """End-to-end tests for API models."""

    def test_chat_request_creation(self):
        """Test ChatRequest model creation."""
        from maos.api.models import ChatRequest, Message, MessageRole

        request = ChatRequest(
            messages=[Message(role=MessageRole.USER, content="Hello")]
        )
        assert len(request.messages) == 1
        assert not request.stream

    def test_chat_response_creation(self):
        """Test ChatResponse model creation."""
        from maos.api.models import ChatResponse, Message, MessageRole

        response = ChatResponse(
            thread_id="test-123",
            messages=[Message(role=MessageRole.ASSISTANT, content="Hi!")],
            final_response="Hi!",
            iterations=1
        )
        assert response.done
        assert response.thread_id == "test-123"

    def test_health_response_creation(self):
        """Test HealthResponse model creation."""
        from maos.api.models import HealthResponse, HealthStatus

        response = HealthResponse(status=HealthStatus.HEALTHY)
        assert response.status == HealthStatus.HEALTHY

    def test_agent_info_creation(self):
        """Test AgentInfo model creation."""
        from maos.api.models import AgentInfo

        agent = AgentInfo(
            name="test_agent",
            kind="native_worker",
            description="A test agent"
        )
        assert agent.name == "test_agent"
        assert agent.kind == "native_worker"


@pytest.mark.e2e
class TestOpenAICompatE2E:
    """End-to-end tests for OpenAI compatibility."""

    def test_openai_request_creation(self):
        """Test OpenAI-compatible request creation."""
        from maos.api.models import OpenAIChatRequest, OpenAIMessage

        request = OpenAIChatRequest(
            model="maos",
            messages=[OpenAIMessage(role="user", content="Hello")]
        )
        assert request.model == "maos"
        assert not request.stream

    def test_openai_response_creation(self):
        """Test OpenAI-compatible response creation."""
        from maos.api.models import (
            OpenAIChatResponse,
            OpenAIChoice,
            OpenAIMessage,
        )
        import time

        response = OpenAIChatResponse(
            id="chatcmpl-123",
            created=int(time.time()),
            choices=[
                OpenAIChoice(
                    message=OpenAIMessage(role="assistant", content="Hi!")
                )
            ]
        )
        assert response.object == "chat.completion"
        assert len(response.choices) == 1


@pytest.mark.e2e
class TestStreamingE2E:
    """End-to-end tests for streaming functionality."""

    def test_format_sse_event(self):
        """Test SSE event formatting."""
        from maos.api.streaming import format_sse_event

        event = format_sse_event("chunk", {"content": "Hello"})
        assert "event: chunk" in event
        assert "Hello" in event
        assert event.endswith("\n\n")

    def test_stream_event_types(self):
        """Test stream event types."""
        from maos.api.models import StreamEventType

        assert StreamEventType.CHUNK.value == "chunk"
        assert StreamEventType.DONE.value == "done"
        assert StreamEventType.ERROR.value == "error"
        assert StreamEventType.INPUT_REQUIRED.value == "input_required"


@pytest.mark.e2e
class TestGraphStateE2E:
    """End-to-end tests for graph state."""

    def test_create_initial_state(self):
        """Test creating initial graph state."""
        from maos.graph.state import create_initial_state

        state = create_initial_state(
            messages=[{"role": "user", "content": "Hello"}],
            roster=["worker1"],
            thread_id="test-thread"
        )

        assert state["task"] == "Hello"
        assert state["roster"] == ["worker1"]
        assert state["thread_id"] == "test-thread"
        assert not state["done"]

    def test_worker_result_creation(self):
        """Test WorkerResult creation."""
        from maos.graph.state import (
            WorkerResult,
            ResultOutput,
            ResultType,
            ResultMetadata,
        )

        result = WorkerResult(
            from_agent="worker1",
            output=ResultOutput(
                type=ResultType.TEXT,
                content="Task completed"
            ),
            metadata=ResultMetadata(duration_ms=100)
        )

        assert result.from_agent == "worker1"
        assert result.content == "Task completed"
        assert not result.is_error

    def test_worker_result_to_message(self):
        """Test WorkerResult to message conversion."""
        from maos.graph.state import (
            WorkerResult,
            ResultOutput,
            ResultType,
        )

        result = WorkerResult(
            from_agent="worker1",
            output=ResultOutput(
                type=ResultType.TEXT,
                content="Done"
            )
        )

        msg = result.to_message()
        assert msg["role"] == "assistant"
        assert msg["name"] == "worker1"
        assert msg["content"] == "Done"
