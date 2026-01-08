"""Integration tests for graph module."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from maos.config.models import (
    AgentConfig,
    AgentKind,
    Config,
    GraphConfig,
    LLMConfig,
    LLMProvider,
)
from maos.llm.registry import LLMRegistry
from maos.graph.state import create_initial_state

from tests.mocks.llm import MockLLMAdapter, MockSupervisorLLM


@pytest.fixture
def test_config():
    """Create a test configuration."""
    return Config(
        llms={
            "default": LLMConfig(
                provider=LLMProvider.OPENAI,
                model="gpt-4o-mini"
            )
        },
        agents={
            "supervisor": AgentConfig(
                kind=AgentKind.SUPERVISOR,
                llm="default",
                system_prompt="Route tasks to workers."
            ),
            "worker1": AgentConfig(
                kind=AgentKind.NATIVE_WORKER,
                llm="default",
                system_prompt="You are a helpful worker.",
                description="General worker"
            )
        },
        graph=GraphConfig(max_iterations=5)
    )


@pytest.fixture
def mock_llm_registry():
    """Create a mock LLM registry with adapters."""
    registry = LLMRegistry()

    # Register mock supervisor LLM
    supervisor_llm = MockSupervisorLLM(routing_sequence=["worker1", "END"])
    registry.register_adapter("default", supervisor_llm)

    return registry


@pytest.mark.integration
class TestGraphStateIntegration:
    """Integration tests for graph state creation."""

    def test_create_initial_state(self):
        """Test creating initial graph state."""
        messages = [{"role": "user", "content": "Hello"}]
        roster = ["worker1", "worker2"]

        state = create_initial_state(messages, roster, thread_id="test")

        assert state["task"] == "Hello"
        assert state["roster"] == roster
        assert state["thread_id"] == "test"

    def test_initial_state_defaults(self):
        """Test initial state has correct defaults."""
        state = create_initial_state(
            messages=[{"role": "user", "content": "Test"}],
            roster=[]
        )

        assert state["done"] is False
        assert state["iteration"] == 0
        assert state["next"] is None
        assert state["last_result"] is None


@pytest.mark.integration
class TestMockLLMIntegration:
    """Integration tests for mock LLM adapters."""

    @pytest.mark.asyncio
    async def test_supervisor_routing_sequence(self):
        """Test supervisor LLM returns correct routing sequence."""
        from maos.llm.base import Message

        llm = MockSupervisorLLM(routing_sequence=["worker1", "worker2", "END"])

        response1 = await llm.invoke([Message.user("Test")])
        assert "worker1" in response1.content

        response2 = await llm.invoke([Message.user("Test")])
        assert "worker2" in response2.content

        response3 = await llm.invoke([Message.user("Test")])
        assert "END" in response3.content

    @pytest.mark.asyncio
    async def test_mock_adapter_responses(self):
        """Test mock adapter returns configured responses."""
        from maos.llm.base import Message

        llm = MockLLMAdapter(responses=["First", "Second", "Third"])

        r1 = await llm.invoke([Message.user("Test")])
        assert r1.content == "First"

        r2 = await llm.invoke([Message.user("Test")])
        assert r2.content == "Second"

        r3 = await llm.invoke([Message.user("Test")])
        assert r3.content == "Third"


@pytest.mark.integration
class TestLLMRegistryIntegration:
    """Integration tests for LLM registry."""

    def test_registry_registration(self, mock_llm_registry):
        """Test registering and retrieving adapters."""
        adapter = mock_llm_registry.get("default")
        assert adapter is not None

    def test_get_or_default(self, mock_llm_registry):
        """Test get_or_default returns correct adapter."""
        # Should return the default
        adapter = mock_llm_registry.get_or_default("nonexistent")
        assert adapter is not None

    def test_list_adapters(self, mock_llm_registry):
        """Test listing registered adapters."""
        names = mock_llm_registry.list()
        assert "default" in names
