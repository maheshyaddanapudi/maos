"""
Integration tests for agent creation.
"""


import pytest

from maos.agents.factory import AgentFactory
from maos.agents.registry import AgentRegistry
from maos.config.models import AgentConfig, AgentKind
from maos.llm.registry import LLMRegistry
from maos.mcp.registry import MCPRegistry
from maos.skills.registry import SkillRegistry, SkillsetRegistry
from maos.tools.registry import ToolRegistry
from tests.mocks.llm import MockLLMAdapter


class TestAgentCreationIntegration:
    """Integration tests for agent creation flow."""

    @pytest.fixture
    def registries(self):
        """Set up all required registries."""
        llm_registry = LLMRegistry()
        llm_registry.register_adapter("default", MockLLMAdapter())
        llm_registry.register_adapter("claude", MockLLMAdapter(model="claude"))

        mcp_registry = MCPRegistry()
        tool_registry = ToolRegistry(mcp_registry)
        skill_registry = SkillRegistry(tool_registry)
        skillset_registry = SkillsetRegistry(skill_registry, tool_registry)

        return {
            "llm": llm_registry,
            "tool": tool_registry,
            "skill": skill_registry,
            "skillset": skillset_registry,
        }

    @pytest.mark.asyncio
    async def test_create_supervisor_agent(self, registries):
        """Test creating supervisor agent."""
        factory = AgentFactory(
            llm_registry=registries["llm"],
            skillset_registry=registries["skillset"],
            skill_registry=registries["skill"],
            tool_registry=registries["tool"],
        )

        config = AgentConfig(
            kind=AgentKind.SUPERVISOR,
            llm="default",
            system_prompt="You are a supervisor that routes tasks.",
            description="Main supervisor",
        )

        agent = await factory.create_agent("supervisor", config)

        assert agent.name == "supervisor"
        assert agent.kind == AgentKind.SUPERVISOR
        assert agent.llm_name == "default"

    @pytest.mark.asyncio
    async def test_create_worker_agent(self, registries):
        """Test creating native worker agent."""
        factory = AgentFactory(
            llm_registry=registries["llm"],
            skillset_registry=registries["skillset"],
            skill_registry=registries["skill"],
            tool_registry=registries["tool"],
        )

        config = AgentConfig(
            kind=AgentKind.NATIVE_WORKER,
            llm="claude",
            system_prompt="You are a research worker.",
            description="Research agent",
            timeout_seconds=120,
        )

        agent = await factory.create_agent("researcher", config)

        assert agent.name == "researcher"
        assert agent.kind == AgentKind.NATIVE_WORKER
        assert agent.llm_name == "claude"
        assert agent.timeout_seconds == 120

    @pytest.mark.asyncio
    async def test_create_multiple_agents(self, registries):
        """Test creating multiple agents at once."""
        factory = AgentFactory(
            llm_registry=registries["llm"],
            skillset_registry=registries["skillset"],
            skill_registry=registries["skill"],
            tool_registry=registries["tool"],
        )

        configs = {
            "supervisor": AgentConfig(
                kind=AgentKind.SUPERVISOR,
                system_prompt="Route tasks.",
            ),
            "worker1": AgentConfig(
                kind=AgentKind.NATIVE_WORKER,
                system_prompt="Worker 1",
            ),
            "worker2": AgentConfig(
                kind=AgentKind.NATIVE_WORKER,
                system_prompt="Worker 2",
            ),
        }

        agents = await factory.create_all(configs)

        assert len(agents) == 3
        names = list(agents.keys())
        assert "supervisor" in names
        assert "worker1" in names
        assert "worker2" in names

    @pytest.mark.asyncio
    async def test_agent_registry_integration(self, registries):
        """Test agent registry with created agents."""
        factory = AgentFactory(
            llm_registry=registries["llm"],
            skillset_registry=registries["skillset"],
            skill_registry=registries["skill"],
            tool_registry=registries["tool"],
        )

        configs = {
            "supervisor": AgentConfig(
                kind=AgentKind.SUPERVISOR,
                system_prompt="Route.",
            ),
            "worker": AgentConfig(
                kind=AgentKind.NATIVE_WORKER,
                system_prompt="Work.",
                description="Worker agent",
            ),
        }

        agents = await factory.create_all(configs)

        registry = AgentRegistry()
        registry.register_all(agents)

        # Test retrieval
        assert registry.get("supervisor") is not None
        assert registry.get("worker") is not None

        # Test supervisor/worker queries
        assert registry.get_supervisor().name == "supervisor"
        assert len(registry.get_workers()) == 1
        assert "worker" in registry.get_workers()

        # Test roster generation
        roster = registry.get_roster()
        assert any("worker" in line for line in roster)
