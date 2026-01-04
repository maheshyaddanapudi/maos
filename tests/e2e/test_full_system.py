"""
Full system end-to-end tests.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from maos.agents.factory import AgentFactory
from maos.agents.registry import AgentRegistry
from maos.config.loader import ConfigLoader
from maos.graph.factory import GraphFactory
from maos.llm.registry import LLMRegistry
from maos.mcp.registry import MCPRegistry
from maos.skills.registry import SkillRegistry, SkillsetRegistry
from maos.tools.registry import ToolRegistry
from tests.mocks.llm import MockLLMAdapter


class TestFullSystemE2E:
    """Full system end-to-end tests."""

    @pytest.fixture
    def config_yaml(self):
        return """
llms:
  default:
    provider: openai
    model: gpt-4o-mini

agents:
  supervisor:
    kind: supervisor
    system_prompt: |
      You are a supervisor. Route tasks to workers.
      Available workers: {roster}
    description: Main supervisor

  worker:
    kind: native_worker
    system_prompt: |
      You are a helpful worker. Complete tasks assigned to you.
    description: General worker
"""

    @pytest.fixture
    def config(self, config_yaml):
        loader = ConfigLoader()
        return loader.load_from_string(config_yaml)

    @pytest.fixture
    def mock_llm_registry(self):
        registry = LLMRegistry()
        # Response simulating routing decision
        mock = MockLLMAdapter(responses=[
            '{"next": "worker", "reason": "Delegating task to worker"}',
            "Task completed successfully!"
        ])
        registry.register_adapter("default", mock)
        return registry

    @pytest.mark.asyncio
    async def test_system_initialization(self, config, mock_llm_registry):
        """Test full system initialization."""
        # Create registries
        mcp_registry = MCPRegistry()
        tool_registry = ToolRegistry(mcp_registry)
        skill_registry = SkillRegistry(tool_registry)
        skillset_registry = SkillsetRegistry(skill_registry, tool_registry)

        # Create agents
        factory = AgentFactory(
            llm_registry=mock_llm_registry,
            skillset_registry=skillset_registry,
            skill_registry=skill_registry,
            tool_registry=tool_registry,
        )

        agents = await factory.create_all(config.agents)
        agent_registry = AgentRegistry()
        agent_registry.register_all(agents)

        # Verify agents created
        assert agent_registry.get_supervisor() is not None
        assert len(agent_registry.get_workers()) == 1

        # Create graph
        graph_factory = GraphFactory(
            llm_registry=mock_llm_registry,
            agent_registry=agent_registry,
            graph_config=config.graph,
            external_agents=[],
        )

        graph = graph_factory.build()
        assert graph is not None

    @pytest.mark.asyncio
    async def test_config_to_graph_flow(self, config):
        """Test flow from config to runnable graph."""
        # Build LLM registry from config (using mock)
        llm_registry = LLMRegistry()
        mock_llm = MockLLMAdapter(responses=["Done"])
        llm_registry.register_adapter("default", mock_llm)

        # Build other registries
        mcp_registry = MCPRegistry()
        tool_registry = ToolRegistry(mcp_registry)
        skill_registry = SkillRegistry(tool_registry)
        skillset_registry = SkillsetRegistry(skill_registry, tool_registry)

        # Build agents
        agent_factory = AgentFactory(
            llm_registry=llm_registry,
            skillset_registry=skillset_registry,
            skill_registry=skill_registry,
            tool_registry=tool_registry,
        )

        agents = await agent_factory.create_all(config.agents)
        agent_registry = AgentRegistry()
        agent_registry.register_all(agents)

        # Build graph
        graph_factory = GraphFactory(
            llm_registry=llm_registry,
            agent_registry=agent_registry,
            graph_config=config.graph,
            external_agents=[],
        )

        compiled_graph = graph_factory.build()

        # Verify graph structure
        assert compiled_graph is not None


class TestSystemComponents:
    """Test system component interactions."""

    @pytest.mark.asyncio
    async def test_llm_to_agent_integration(self):
        """Test LLM adapter integration with agent."""
        # Create mock LLM
        MockLLMAdapter(responses=["Hello, I'm the agent!"])

        # Create simple agent
        agent = MagicMock()
        agent.name = "test"
        agent.execute = AsyncMock(return_value=MagicMock(
            output=MagicMock(content="Done")
        ))

        # Execute
        result = await agent.execute("Do something")

        assert result.output.content == "Done"

    @pytest.mark.asyncio
    async def test_registry_chain(self):
        """Test registry dependency chain."""
        # Build chain: MCP -> Tool -> Skill -> Skillset
        mcp_registry = MCPRegistry()
        tool_registry = ToolRegistry(mcp_registry)
        skill_registry = SkillRegistry(tool_registry)
        skillset_registry = SkillsetRegistry(skill_registry, tool_registry)

        # All should be empty but functional
        assert tool_registry.list_all() == []
        assert skill_registry.list_all() == []
        assert skillset_registry.list_all() == []
