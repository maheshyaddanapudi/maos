"""Unit tests for graph module."""

import pytest

from maos.graph.state import (
    ResultMetadata,
    ResultOutput,
    ResultType,
    ToolCallRecord,
    WorkerResult,
    create_initial_state,
)


@pytest.mark.unit
class TestResultType:
    """Tests for ResultType enum."""

    def test_result_types(self):
        """Test all result type values."""
        assert ResultType.TEXT.value == "text"
        assert ResultType.ERROR.value == "error"
        assert ResultType.PARTIAL.value == "partial"
        assert ResultType.STRUCTURED.value == "structured"


@pytest.mark.unit
class TestToolCallRecord:
    """Tests for ToolCallRecord model."""

    def test_successful_call(self):
        """Test successful tool call record."""
        record = ToolCallRecord(
            tool_id="tool_1",
            tool_name="search",
            input_args={"query": "test"},
            output={"results": []},
            success=True,
            duration_ms=100,
        )
        assert record.success
        assert record.error_message is None

    def test_failed_call(self):
        """Test failed tool call record."""
        record = ToolCallRecord(
            tool_id="tool_1",
            tool_name="search",
            input_args={"query": "test"},
            output=None,
            success=False,
            error_message="Tool not found",
        )
        assert not record.success
        assert "not found" in record.error_message


@pytest.mark.unit
class TestResultOutput:
    """Tests for ResultOutput model."""

    def test_text_output(self):
        """Test text output."""
        output = ResultOutput(type=ResultType.TEXT, content="Hello world")
        assert output.type == ResultType.TEXT
        assert output.content == "Hello world"

    def test_output_with_sources(self):
        """Test output with sources."""
        output = ResultOutput(
            type=ResultType.TEXT, content="Research results", sources=["https://example.com"]
        )
        assert len(output.sources) == 1


@pytest.mark.unit
class TestWorkerResult:
    """Tests for WorkerResult model."""

    def test_successful_result(self):
        """Test successful worker result."""
        result = WorkerResult(
            from_agent="researcher", output=ResultOutput(type=ResultType.TEXT, content="Found data")
        )
        assert not result.is_error
        assert result.content == "Found data"

    def test_error_result(self):
        """Test error worker result."""
        result = WorkerResult(
            from_agent="researcher", output=ResultOutput(type=ResultType.ERROR, content="Failed")
        )
        assert result.is_error

    def test_to_message(self):
        """Test converting to message format."""
        result = WorkerResult(
            from_agent="worker1", output=ResultOutput(type=ResultType.TEXT, content="Done")
        )
        msg = result.to_message()
        assert msg["role"] == "assistant"
        assert msg["name"] == "worker1"
        assert msg["content"] == "Done"


@pytest.mark.unit
class TestCreateInitialState:
    """Tests for create_initial_state function."""

    def test_basic_state(self):
        """Test creating basic initial state."""
        messages = [{"role": "user", "content": "Hello"}]
        roster = ["worker1", "worker2"]

        state = create_initial_state(messages, roster)

        assert state["task"] == "Hello"
        assert state["roster"] == roster
        assert state["iteration"] == 0
        assert not state["done"]

    def test_state_with_thread_id(self):
        """Test creating state with thread ID."""
        state = create_initial_state(
            messages=[{"role": "user", "content": "Test"}],
            roster=["worker"],
            thread_id="thread-123",
        )

        assert state["thread_id"] == "thread-123"

    def test_extracts_task_from_last_user_message(self):
        """Test that task is extracted from last user message."""
        messages = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "Response"},
            {"role": "user", "content": "Second message"},
        ]

        state = create_initial_state(messages, [])

        assert state["task"] == "Second message"


@pytest.mark.unit
class TestGraphState:
    """Tests for GraphState structure."""

    def test_state_keys(self, sample_graph_state):
        """Test all required state keys exist."""
        required_keys = [
            "messages",
            "task",
            "context",
            "roster",
            "last_result",
            "next",
            "done",
            "iteration",
            "metadata",
            "thread_id",
        ]
        for key in required_keys:
            assert key in sample_graph_state

    def test_state_has_correct_types(self):
        """Test that state values have correct types."""
        state = create_initial_state(
            messages=[{"role": "user", "content": "Test"}], roster=["worker1"]
        )

        assert isinstance(state["messages"], list)
        assert isinstance(state["task"], str)
        assert isinstance(state["roster"], list)
        assert isinstance(state["iteration"], int)
        assert isinstance(state["done"], bool)


@pytest.mark.unit
class TestResultMetadata:
    """Tests for ResultMetadata model."""

    def test_basic_metadata(self):
        """Test basic metadata creation."""
        metadata = ResultMetadata(tokens_used=100, duration_ms=500, model_used="gpt-4")
        assert metadata.tokens_used == 100
        assert metadata.duration_ms == 500

    def test_metadata_with_tools_invoked(self):
        """Test metadata with tools invoked."""
        metadata = ResultMetadata(
            tokens_used=50, duration_ms=200, tools_invoked=["search", "calculate"]
        )
        assert len(metadata.tools_invoked) == 2
        assert "search" in metadata.tools_invoked
