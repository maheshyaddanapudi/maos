"""Unit tests for LangGraph Studio-compatible API endpoints."""

from datetime import datetime
from unittest.mock import MagicMock

from maos.api.models import (
    Assistant,
    AssistantConfig,
    AssistantCreate,
    AssistantSearch,
    Run,
    RunCreate,
    RunStatus,
    Thread,
    ThreadCreate,
    ThreadState,
)
from maos.api.routes import langgraph_studio


class TestAssistantModels:
    """Tests for assistant models."""

    def test_assistant_create_defaults(self):
        """Test AssistantCreate has correct defaults."""
        request = AssistantCreate()
        assert request.graph_id == "maos"
        assert request.name is None
        assert request.config is None

    def test_assistant_create_with_values(self):
        """Test AssistantCreate with values."""
        request = AssistantCreate(
            graph_id="custom",
            name="My Assistant",
            description="Test assistant",
            config=AssistantConfig(configurable={"model": "gpt-4"}),
            metadata={"version": "1.0"}
        )
        assert request.graph_id == "custom"
        assert request.name == "My Assistant"
        assert request.config.configurable["model"] == "gpt-4"

    def test_assistant_search_defaults(self):
        """Test AssistantSearch has correct defaults."""
        request = AssistantSearch()
        assert request.limit == 100
        assert request.offset == 0
        assert request.graph_id is None


class TestThreadModels:
    """Tests for thread models."""

    def test_thread_create_generates_id(self):
        """Test ThreadCreate allows optional thread_id."""
        request = ThreadCreate()
        assert request.thread_id is None
        assert request.metadata is None

    def test_thread_create_with_id(self):
        """Test ThreadCreate with explicit thread_id."""
        request = ThreadCreate(
            thread_id="my-thread-123",
            metadata={"user": "test"}
        )
        assert request.thread_id == "my-thread-123"
        assert request.metadata["user"] == "test"

    def test_thread_state_defaults(self):
        """Test ThreadState has correct defaults."""
        state = ThreadState()
        assert state.values == {}
        assert state.next == []
        assert state.tasks == []


class TestRunModels:
    """Tests for run models."""

    def test_run_create_minimal(self):
        """Test RunCreate with minimal input."""
        request = RunCreate(assistant_id="default")
        assert request.assistant_id == "default"
        assert request.input is None
        assert request.stream_mode is None

    def test_run_create_full(self):
        """Test RunCreate with all options."""
        request = RunCreate(
            assistant_id="default",
            input={"messages": [{"role": "user", "content": "Hello"}]},
            stream_mode=["values", "messages"],
            interrupt_before=["supervisor"],
            multitask_strategy="reject"
        )
        assert request.stream_mode == ["values", "messages"]
        assert request.interrupt_before == ["supervisor"]

    def test_run_status_enum(self):
        """Test RunStatus enum values."""
        assert RunStatus.PENDING.value == "pending"
        assert RunStatus.RUNNING.value == "running"
        assert RunStatus.SUCCESS.value == "success"
        assert RunStatus.ERROR.value == "error"
        assert RunStatus.INTERRUPTED.value == "interrupted"


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_now_iso_format(self):
        """Test _now_iso returns valid ISO format."""
        result = langgraph_studio._now_iso()
        # Should be parseable as datetime
        datetime.fromisoformat(result.replace('Z', '+00:00'))

    def test_format_studio_event_chain_stream(self):
        """Test _format_studio_event for chain stream events."""
        event = {
            "event": "on_chain_stream",
            "data": {"chunk": {"messages": [{"content": "Hello"}]}}
        }
        result = langgraph_studio._format_studio_event(event)
        assert result is not None
        assert "event: updates" in result

    def test_format_studio_event_tool_start(self):
        """Test _format_studio_event for tool start events."""
        event = {
            "event": "on_tool_start",
            "data": {"name": "calculator"}
        }
        result = langgraph_studio._format_studio_event(event)
        assert result is not None
        assert "event: events" in result
        assert "tool_start" in result

    def test_format_studio_event_tool_end(self):
        """Test _format_studio_event for tool end events."""
        event = {
            "event": "on_tool_end",
            "data": {"name": "calculator"}
        }
        result = langgraph_studio._format_studio_event(event)
        assert result is not None
        assert "tool_end" in result

    def test_format_studio_event_unknown(self):
        """Test _format_studio_event returns None for unknown events."""
        event = {"event": "unknown_event", "data": {}}
        result = langgraph_studio._format_studio_event(event)
        assert result is None


class TestAssistantStore:
    """Tests for in-memory assistant store operations."""

    def setup_method(self):
        """Clear stores before each test."""
        langgraph_studio._assistants.clear()
        langgraph_studio._threads.clear()
        langgraph_studio._runs.clear()

    def test_init_default_assistant(self):
        """Test _init_default_assistant creates default."""
        context = {"config": MagicMock()}
        langgraph_studio._init_default_assistant(context)

        assert "default" in langgraph_studio._assistants
        assistant = langgraph_studio._assistants["default"]
        assert assistant.name == "MAOS Default Assistant"
        assert assistant.graph_id == "maos"

    def test_init_default_assistant_idempotent(self):
        """Test _init_default_assistant doesn't duplicate."""
        context = {"config": MagicMock()}
        langgraph_studio._init_default_assistant(context)
        langgraph_studio._init_default_assistant(context)

        assert len([a for a in langgraph_studio._assistants if a == "default"]) == 1


class TestThreadStore:
    """Tests for in-memory thread store operations."""

    def setup_method(self):
        """Clear stores before each test."""
        langgraph_studio._assistants.clear()
        langgraph_studio._threads.clear()
        langgraph_studio._runs.clear()

    def test_thread_creation(self):
        """Test thread is stored correctly."""
        now = langgraph_studio._now_iso()
        thread = Thread(
            thread_id="test-thread",
            created_at=now,
            updated_at=now,
            status="idle"
        )
        langgraph_studio._threads["test-thread"] = thread

        assert "test-thread" in langgraph_studio._threads
        assert langgraph_studio._threads["test-thread"].status == "idle"


class TestRunStore:
    """Tests for in-memory run store operations."""

    def setup_method(self):
        """Clear stores before each test."""
        langgraph_studio._assistants.clear()
        langgraph_studio._threads.clear()
        langgraph_studio._runs.clear()

    def test_run_creation(self):
        """Test run is stored correctly."""
        now = langgraph_studio._now_iso()
        run = Run(
            run_id="run-123",
            thread_id="thread-123",
            assistant_id="default",
            status=RunStatus.RUNNING,
            created_at=now,
            updated_at=now
        )
        langgraph_studio._runs["run-123"] = run

        assert "run-123" in langgraph_studio._runs
        assert langgraph_studio._runs["run-123"].status == RunStatus.RUNNING

    def test_run_status_update(self):
        """Test run status can be updated."""
        now = langgraph_studio._now_iso()
        run = Run(
            run_id="run-123",
            thread_id="thread-123",
            assistant_id="default",
            status=RunStatus.RUNNING,
            created_at=now,
            updated_at=now
        )
        langgraph_studio._runs["run-123"] = run

        # Update status
        run.status = RunStatus.SUCCESS
        run.updated_at = langgraph_studio._now_iso()

        assert langgraph_studio._runs["run-123"].status == RunStatus.SUCCESS


class TestAssistantModel:
    """Tests for Assistant model."""

    def test_assistant_full(self):
        """Test creating a full Assistant model."""
        now = langgraph_studio._now_iso()
        assistant = Assistant(
            assistant_id="test-id",
            graph_id="maos",
            name="Test Assistant",
            description="A test assistant",
            config=AssistantConfig(configurable={"temperature": 0.7}),
            metadata={"created_by": "test"},
            created_at=now,
            updated_at=now
        )

        assert assistant.assistant_id == "test-id"
        assert assistant.graph_id == "maos"
        assert assistant.config.configurable["temperature"] == 0.7
        assert assistant.metadata["created_by"] == "test"


class TestThreadModel:
    """Tests for Thread model."""

    def test_thread_status_values(self):
        """Test thread can have different status values."""
        now = langgraph_studio._now_iso()

        for status in ["idle", "busy", "interrupted", "error"]:
            thread = Thread(
                thread_id=f"thread-{status}",
                created_at=now,
                updated_at=now,
                status=status
            )
            assert thread.status == status


class TestRunModel:
    """Tests for Run model."""

    def test_run_all_statuses(self):
        """Test run can have all status values."""
        now = langgraph_studio._now_iso()

        for status in RunStatus:
            run = Run(
                run_id=f"run-{status.value}",
                thread_id="thread-123",
                assistant_id="default",
                status=status,
                created_at=now,
                updated_at=now
            )
            assert run.status == status
