"""Unit tests for graph module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from maos.graph.state import (
    GraphState,
    ResultMetadata,
    ResultOutput,
    ResultType,
    ToolCallRecord,
    WorkerResult,
    create_initial_state,
)
from maos.graph.nodes.supervisor import SupervisorNode
from maos.graph.nodes.worker import NativeWorkerNode

from tests.mocks.llm import MockLLMAdapter, MockSupervisorLLM


class TestResultType:
    """Tests for ResultType enum."""

    def test_result_types(self):
        """Test all result type values."""
        assert ResultType.TEXT.value == "text"
        assert ResultType.ERROR.value == "error"
        assert ResultType.PARTIAL.value == "partial"
        assert ResultType.STRUCTURED.value == "structured"


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
            duration_ms=100
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
            error_message="Tool not found"
        )
        assert not record.success
        assert "not found" in record.error_message


class TestResultOutput:
    """Tests for ResultOutput model."""

    def test_text_output(self):
        """Test text output."""
        output = ResultOutput(
            type=ResultType.TEXT,
            content="Hello world"
        )
        assert output.type == ResultType.TEXT
        assert output.content == "Hello world"

    def test_output_with_sources(self):
        """Test output with sources."""
        output = ResultOutput(
            type=ResultType.TEXT,
            content="Research results",
            sources=["https://example.com"]
        )
        assert len(output.sources) == 1


class TestWorkerResult:
    """Tests for WorkerResult model."""

    def test_successful_result(self):
        """Test successful worker result."""
        result = WorkerResult(
            from_agent="researcher",
            output=ResultOutput(type=ResultType.TEXT, content="Found data")
        )
        assert not result.is_error
        assert result.content == "Found data"

    def test_error_result(self):
        """Test error worker result."""
        result = WorkerResult(
            from_agent="researcher",
            output=ResultOutput(type=ResultType.ERROR, content="Failed")
        )
        assert result.is_error

    def test_to_message(self):
        """Test converting to message format."""
        result = WorkerResult(
            from_agent="worker1",
            output=ResultOutput(type=ResultType.TEXT, content="Done")
        )
        msg = result.to_message()
        assert msg["role"] == "assistant"
        assert msg["name"] == "worker1"
        assert msg["content"] == "Done"


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
            thread_id="thread-123"
        )

        assert state["thread_id"] == "thread-123"

    def test_extracts_task_from_last_user_message(self):
        """Test that task is extracted from last user message."""
        messages = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "Response"},
            {"role": "user", "content": "Second message"}
        ]

        state = create_initial_state(messages, [])

        assert state["task"] == "Second message"


class TestSupervisorNode:
    """Tests for SupervisorNode."""

    @pytest.fixture
    def supervisor(self):
        """Create a supervisor node with mock LLM."""
        llm = MockSupervisorLLM(routing_sequence=["worker1", "END"])
        return SupervisorNode(
            llm=llm,
            roster=["worker1", "worker2"],
            max_iterations=10
        )

    @pytest.mark.asyncio
    async def test_routing_decision(self, supervisor, sample_graph_state):
        """Test supervisor makes routing decision."""
        result = await supervisor.run(sample_graph_state)

        assert "next" in result
        assert result["iteration"] == 1

    @pytest.mark.asyncio
    async def test_max_iterations(self):
        """Test supervisor respects max iterations."""
        llm = MockSupervisorLLM(routing_sequence=["worker1"])
        supervisor = SupervisorNode(llm=llm, roster=["worker1"], max_iterations=3)

        # State with high iteration count
        state = {
            "messages": [{"role": "user", "content": "Test"}],
            "iteration": 3,  # At limit
            "next": None,
            "done": False
        }

        result = await supervisor.run(state)

        assert result["next"] == "END"
        assert result["done"]

    def test_roster_property(self, supervisor):
        """Test roster property."""
        assert supervisor.roster == ["worker1", "worker2"]

    def test_update_roster(self, supervisor):
        """Test updating roster."""
        supervisor.update_roster(["new_worker"])
        assert supervisor.roster == ["new_worker"]


class TestNativeWorkerNode:
    """Tests for NativeWorkerNode."""

    @pytest.fixture
    def worker_agent(self):
        """Create a mock worker agent."""
        agent = MagicMock()
        agent.name = "test_worker"
        agent.system_prompt = "You are a helpful assistant."
        return agent

    @pytest.fixture
    def worker_node(self, worker_agent):
        """Create a worker node with mock LLM."""
        llm = MockLLMAdapter(responses=["Task completed successfully"])
        return NativeWorkerNode(
            agent=worker_agent,
            llm=llm,
            tools=[],
            timeout=30
        )

    @pytest.mark.asyncio
    async def test_execution(self, worker_node, sample_graph_state):
        """Test worker execution."""
        result = await worker_node.run(sample_graph_state)

        assert "last_result" in result
        assert "messages" in result
        assert result["last_result"].from_agent == "test_worker"

    @pytest.mark.asyncio
    async def test_timeout_handling(self, worker_agent, sample_graph_state):
        """Test timeout handling."""
        # Create LLM that takes too long
        slow_llm = MockLLMAdapter()

        async def slow_invoke(*args, **kwargs):
            import asyncio
            await asyncio.sleep(10)  # Too slow
            return MagicMock()

        slow_llm.invoke = slow_invoke

        worker = NativeWorkerNode(
            agent=worker_agent,
            llm=slow_llm,
            tools=[],
            timeout=0.1  # Very short timeout
        )

        result = await worker.run(sample_graph_state)

        assert result["last_result"].is_error
        assert "timed out" in result["last_result"].content.lower()

    def test_name_property(self, worker_node):
        """Test name property."""
        assert worker_node.name == "test_worker"


class TestGraphState:
    """Tests for GraphState structure."""

    def test_state_keys(self, sample_graph_state):
        """Test all required state keys exist."""
        required_keys = [
            "messages", "task", "context", "roster",
            "last_result", "next", "done", "iteration",
            "metadata", "thread_id"
        ]
        for key in required_keys:
            assert key in sample_graph_state
