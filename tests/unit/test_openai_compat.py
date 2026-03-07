"""Unit tests for OpenAI-compatible API endpoints."""

from unittest.mock import MagicMock

import pytest

from maos.api.models import (
    OpenAIChatRequest,
    OpenAIChatResponse,
    OpenAIMessage,
)
from maos.api.routes.openai_compat import (
    _extract_final_content,
    _extract_interrupt_message,
)


@pytest.mark.unit
class TestExtractInterruptMessage:
    """Tests for interrupt message extraction."""

    def test_no_interrupt_when_state_not_waiting(self):
        """Test returns None when state.next is None."""
        state = MagicMock()
        state.next = None

        result = _extract_interrupt_message(state)
        assert result is None

    def test_no_interrupt_when_no_tasks(self):
        """Test returns None when no tasks."""
        state = MagicMock()
        state.next = ["some_node"]
        state.tasks = []

        result = _extract_interrupt_message(state)
        assert result is None

    def test_no_interrupt_when_no_interrupts(self):
        """Test returns None when tasks have no interrupts."""
        task = MagicMock()
        task.interrupts = []

        state = MagicMock()
        state.next = ["some_node"]
        state.tasks = [task]

        result = _extract_interrupt_message(state)
        assert result is None

    def test_extracts_interrupt_message(self):
        """Test extracts prompt from interrupt."""
        interrupt = MagicMock()
        interrupt.value = {"type": "input_required", "prompt": "What do you need help with?"}

        task = MagicMock()
        task.interrupts = [interrupt]

        state = MagicMock()
        state.next = ["some_node"]
        state.tasks = [task]

        result = _extract_interrupt_message(state)
        assert result == "What do you need help with?"

    def test_ignores_non_input_required_interrupts(self):
        """Test ignores interrupts that aren't input_required type."""
        interrupt = MagicMock()
        interrupt.value = {"type": "other_type", "data": "something"}

        task = MagicMock()
        task.interrupts = [interrupt]

        state = MagicMock()
        state.next = ["some_node"]
        state.tasks = [task]

        result = _extract_interrupt_message(state)
        assert result is None


@pytest.mark.unit
class TestExtractFinalContent:
    """Tests for final content extraction."""

    def test_extracts_from_ai_message_object(self):
        """Test extracts content from AIMessage-like object."""
        msg = MagicMock()
        msg.type = "ai"
        msg.content = "Hello, how can I help?"

        result = {"messages": [msg]}

        content = _extract_final_content(result)
        assert content == "Hello, how can I help?"

    def test_extracts_from_dict_message(self):
        """Test extracts content from dict message."""
        result = {
            "messages": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello there!"},
            ]
        }

        content = _extract_final_content(result)
        assert content == "Hello there!"

    def test_returns_empty_string_when_no_messages(self):
        """Test returns empty string when no messages."""
        result = {"messages": []}
        content = _extract_final_content(result)
        assert content == ""

    def test_returns_empty_string_when_no_content(self):
        """Test returns empty string when messages have no content."""
        msg = MagicMock()
        msg.type = "ai"
        msg.content = ""

        result = {"messages": [msg]}

        content = _extract_final_content(result)
        assert content == ""

    def test_returns_last_ai_message(self):
        """Test returns the last AI message content."""
        msg1 = MagicMock()
        msg1.type = "ai"
        msg1.content = "First response"

        msg2 = MagicMock()
        msg2.type = "ai"
        msg2.content = "Final response"

        result = {"messages": [msg1, msg2]}

        content = _extract_final_content(result)
        assert content == "Final response"


@pytest.mark.unit
class TestOpenAIChatRequestModel:
    """Tests for OpenAI chat request model."""

    def test_request_with_thread_id(self):
        """Test request can include thread_id."""
        request = OpenAIChatRequest(
            messages=[OpenAIMessage(role="user", content="Hello")], thread_id="test-thread-123"
        )

        assert request.thread_id == "test-thread-123"

    def test_request_thread_id_optional(self):
        """Test thread_id is optional."""
        request = OpenAIChatRequest(messages=[OpenAIMessage(role="user", content="Hello")])

        assert request.thread_id is None


@pytest.mark.unit
class TestOpenAIChatResponseModel:
    """Tests for OpenAI chat response model."""

    def test_response_includes_thread_id(self):
        """Test response includes thread_id."""
        from maos.api.models import OpenAIChoice

        response = OpenAIChatResponse(
            id="test-123",
            created=1234567890,
            choices=[
                OpenAIChoice(
                    message=OpenAIMessage(role="assistant", content="Hi"), finish_reason="stop"
                )
            ],
            thread_id="thread-abc",
            input_pending=False,
        )

        assert response.thread_id == "thread-abc"
        assert response.input_pending is False

    def test_response_input_pending_flag(self):
        """Test response input_pending flag for interrupts."""
        from maos.api.models import OpenAIChoice

        response = OpenAIChatResponse(
            id="test-123",
            created=1234567890,
            choices=[
                OpenAIChoice(
                    message=OpenAIMessage(
                        role="assistant", content="What would you like help with?"
                    ),
                    finish_reason="stop",
                )
            ],
            thread_id="thread-abc",
            input_pending=True,  # Indicates interrupt
        )

        assert response.input_pending is True


@pytest.mark.unit
class TestStreamingHelpers:
    """Tests for streaming helper functions."""

    def test_extract_stream_content_from_ai_message(self):
        """Test extracts content from AI message in stream event."""
        from maos.api.streaming import _extract_stream_content

        msg = MagicMock()
        msg.type = "ai"
        msg.content = "Streaming content"

        event = {"event": "on_chain_stream", "data": {"chunk": {"messages": [msg]}}}

        content = _extract_stream_content(event)
        assert content == "Streaming content"

    def test_extract_stream_content_from_dict_message(self):
        """Test extracts content from dict message in stream event."""
        from maos.api.streaming import _extract_stream_content

        event = {
            "event": "on_chain_stream",
            "data": {"chunk": {"messages": [{"content": "Dict content"}]}},
        }

        content = _extract_stream_content(event)
        assert content == "Dict content"

    def test_extract_stream_content_returns_none_for_other_events(self):
        """Test returns None for non-stream events."""
        from maos.api.streaming import _extract_stream_content

        event = {"event": "on_tool_start", "data": {}}

        content = _extract_stream_content(event)
        assert content is None

    def test_extract_interrupt_from_state(self):
        """Test extracts interrupt prompt from state."""
        from maos.api.streaming import _extract_interrupt_from_state

        interrupt = MagicMock()
        interrupt.value = {"type": "input_required", "prompt": "Please clarify your request"}

        task = MagicMock()
        task.interrupts = [interrupt]

        state = MagicMock()
        state.tasks = [task]

        result = _extract_interrupt_from_state(state)
        assert result == "Please clarify your request"

    def test_extract_interrupt_from_state_returns_none(self):
        """Test returns None when no interrupt."""
        from maos.api.streaming import _extract_interrupt_from_state

        state = MagicMock()
        state.tasks = []

        result = _extract_interrupt_from_state(state)
        assert result is None
