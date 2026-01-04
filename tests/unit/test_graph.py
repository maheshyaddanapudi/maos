"""
Unit tests for graph module.
"""


import pytest

from maos.agents.models import Agent, WorkerResult
from maos.agents.registry import AgentRegistry
from maos.config.models import AgentKind, GraphConfig
from maos.graph.factory import GraphFactory
from maos.graph.state import create_initial_state
from maos.llm.registry import LLMRegistry
from tests.mocks.llm import MockLLMAdapter


class TestGraphState:
    """Tests for GraphState."""

    def test_create_initial_state(self):
        state = create_initial_state(
            messages=[{"role": "user", "content": "Test task"}],
            roster=["worker"],
            thread_id="thread-1",
        )

        assert len(state["messages"]) == 1
        assert state["thread_id"] == "thread-1"
        assert state["iteration"] == 0
        assert state["done"] is False
        assert state["task"] == "Test task"

    def test_create_initial_state_extracts_task(self):
        state = create_initial_state(
            messages=[
                {"role": "system", "content": "System msg"},
                {"role": "user", "content": "Do something"},
            ],
            roster=["worker"],
        )

        assert state["task"] == "Do something"


class TestGraphFactory:
    """Tests for GraphFactory."""

    @pytest.fixture
    def mock_registry(self):
        supervisor = Agent(
            name="supervisor",
            kind=AgentKind.SUPERVISOR,
            system_prompt="Supervisor",
            description="Supervisor",
        )
        worker = Agent(
            name="worker",
            kind=AgentKind.NATIVE_WORKER,
            system_prompt="Worker",
            description="Worker",
        )

        async def mock_execute(task: str) -> WorkerResult:
            return WorkerResult.success(
                from_agent="worker",
                content="Done",
            )

        worker.set_execute_func(mock_execute)

        registry = AgentRegistry()
        registry.register(supervisor)
        registry.register(worker)
        return registry

    @pytest.fixture
    def mock_llm_registry(self):
        registry = LLMRegistry()
        registry.register_adapter("default", MockLLMAdapter())
        return registry

    @pytest.fixture
    def graph_config(self):
        return GraphConfig()

    def test_factory_creation(self, mock_registry, mock_llm_registry, graph_config):
        factory = GraphFactory(
            llm_registry=mock_llm_registry,
            agent_registry=mock_registry,
            graph_config=graph_config,
            external_agents=[],
        )
        assert factory is not None

    def test_build_graph(self, mock_registry, mock_llm_registry, graph_config):
        factory = GraphFactory(
            llm_registry=mock_llm_registry,
            agent_registry=mock_registry,
            graph_config=graph_config,
            external_agents=[],
        )

        graph = factory.build()

        assert graph is not None
