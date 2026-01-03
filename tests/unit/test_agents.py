"""
Unit tests for agents module.
"""


import pytest

from maos.agents.factory import AgentFactory
from maos.agents.models import Agent, ResultOutput, ResultType, WorkerResult
from maos.agents.registry import AgentRegistry
from maos.config.models import AgentConfig, AgentFramework
from maos.config.models import AgentKind as ConfigAgentKind
from maos.llm.registry import LLMRegistry
from maos.mcp.registry import MCPRegistry
from maos.skills.registry import SkillRegistry, SkillsetRegistry
from maos.tools.registry import ToolRegistry
from tests.mocks.llm import MockLLMAdapter


class TestAgentModels:
    """Tests for agent models."""

    def test_worker_result_text(self):
        result = WorkerResult(
            from_agent="test_agent",
            output=ResultOutput(type=ResultType.TEXT, content="Hello"),
        )
        assert result.from_agent == "test_agent"
        assert result.output.content == "Hello"

    def test_worker_result_success_factory(self):
        result = WorkerResult.success(
            from_agent="test_agent",
            content="Task completed.",
        )
        assert result.from_agent == "test_agent"
        assert result.output.type == ResultType.TEXT
        assert result.output.content == "Task completed."

    def test_worker_result_error_factory(self):
        result = WorkerResult.error(
            from_agent="test_agent",
            error_message="Something went wrong",
        )
        assert result.from_agent == "test_agent"
        assert result.is_error
        assert result.output.type == ResultType.ERROR

    def test_agent_creation(self):
        agent = Agent(
            name="test",
            kind=ConfigAgentKind.NATIVE_WORKER,
            framework=AgentFramework.LANGCHAIN,
            llm_name="default",
            system_prompt="You are a test agent.",
            description="Test agent",
        )
        assert agent.name == "test"
        assert agent.kind == ConfigAgentKind.NATIVE_WORKER

    @pytest.mark.asyncio
    async def test_agent_execute_without_func(self):
        agent = Agent(
            name="test",
            kind=ConfigAgentKind.NATIVE_WORKER,
            system_prompt="Test",
            description="Test",
        )

        # Should return error when no execute func is set
        result = await agent.execute("Do something")

        assert result.is_error

    @pytest.mark.asyncio
    async def test_agent_execute_with_func(self):
        async def mock_execute(task: str) -> WorkerResult:
            return WorkerResult.success(
                from_agent="test",
                content="Done",
            )

        agent = Agent(
            name="test",
            kind=ConfigAgentKind.NATIVE_WORKER,
            system_prompt="Test",
            description="Test",
        )
        agent.set_execute_func(mock_execute)

        result = await agent.execute("Do something")

        assert result.output.content == "Done"


class TestAgentFactory:
    """Tests for AgentFactory."""

    @pytest.fixture
    def registries(self):
        """Create mock registries."""
        llm_registry = LLMRegistry()
        llm_registry.register_adapter("default", MockLLMAdapter())

        mcp_registry = MCPRegistry()
        tool_registry = ToolRegistry(mcp_registry)
        skill_registry = SkillRegistry(tool_registry)
        skillset_registry = SkillsetRegistry(skill_registry, tool_registry)

        return llm_registry, skillset_registry, skill_registry, tool_registry

    @pytest.mark.asyncio
    async def test_create_supervisor(self, registries):
        llm_registry, skillset_registry, skill_registry, tool_registry = registries

        factory = AgentFactory(
            llm_registry=llm_registry,
            skillset_registry=skillset_registry,
            skill_registry=skill_registry,
            tool_registry=tool_registry,
        )

        config = AgentConfig(
            kind=ConfigAgentKind.SUPERVISOR,
            system_prompt="You are a supervisor.",
        )

        agent = await factory.create_agent("supervisor", config)

        assert agent.name == "supervisor"
        assert agent.kind == ConfigAgentKind.SUPERVISOR

    @pytest.mark.asyncio
    async def test_create_native_worker(self, registries):
        llm_registry, skillset_registry, skill_registry, tool_registry = registries

        factory = AgentFactory(
            llm_registry=llm_registry,
            skillset_registry=skillset_registry,
            skill_registry=skill_registry,
            tool_registry=tool_registry,
        )

        config = AgentConfig(
            kind=ConfigAgentKind.NATIVE_WORKER,
            system_prompt="You are a worker.",
        )

        agent = await factory.create_agent("worker", config)

        assert agent.name == "worker"
        assert agent.kind == ConfigAgentKind.NATIVE_WORKER

    @pytest.mark.asyncio
    async def test_create_all(self, registries):
        llm_registry, skillset_registry, skill_registry, tool_registry = registries

        factory = AgentFactory(
            llm_registry=llm_registry,
            skillset_registry=skillset_registry,
            skill_registry=skill_registry,
            tool_registry=tool_registry,
        )

        configs = {
            "supervisor": AgentConfig(
                kind=ConfigAgentKind.SUPERVISOR,
                system_prompt="Supervisor",
            ),
            "worker": AgentConfig(
                kind=ConfigAgentKind.NATIVE_WORKER,
                system_prompt="Worker",
            ),
        }

        agents = await factory.create_all(configs)

        assert len(agents) == 2


class TestAgentRegistry:
    """Tests for AgentRegistry."""

    def test_register_and_get(self):
        registry = AgentRegistry()
        agent = Agent(
            name="test",
            kind=ConfigAgentKind.NATIVE_WORKER,
            system_prompt="Test",
            description="Test",
        )

        registry.register(agent)

        assert registry.get("test") is agent

    def test_get_nonexistent(self):
        registry = AgentRegistry()
        assert registry.get("nonexistent") is None

    def test_register_all(self):
        registry = AgentRegistry()
        agents = {
            "a": Agent(
                name="a",
                kind=ConfigAgentKind.NATIVE_WORKER,
                system_prompt="A",
                description="A",
            ),
            "b": Agent(
                name="b",
                kind=ConfigAgentKind.NATIVE_WORKER,
                system_prompt="B",
                description="B",
            ),
        }

        registry.register_all(agents)

        assert registry.get("a") is not None
        assert registry.get("b") is not None

    def test_get_supervisor(self):
        registry = AgentRegistry()
        supervisor = Agent(
            name="supervisor",
            kind=ConfigAgentKind.SUPERVISOR,
            system_prompt="Supervisor",
            description="Supervisor",
        )
        worker = Agent(
            name="worker",
            kind=ConfigAgentKind.NATIVE_WORKER,
            system_prompt="Worker",
            description="Worker",
        )

        registry.register(supervisor)
        registry.register(worker)

        assert registry.get_supervisor().name == "supervisor"

    def test_get_workers(self):
        registry = AgentRegistry()
        supervisor = Agent(
            name="supervisor",
            kind=ConfigAgentKind.SUPERVISOR,
            system_prompt="Supervisor",
            description="Supervisor",
        )
        worker = Agent(
            name="worker",
            kind=ConfigAgentKind.NATIVE_WORKER,
            system_prompt="Worker",
            description="Worker",
        )

        registry.register(supervisor)
        registry.register(worker)

        workers = registry.get_workers()
        assert len(workers) == 1
        assert "worker" in workers

    def test_roster(self):
        registry = AgentRegistry()
        worker = Agent(
            name="worker",
            kind=ConfigAgentKind.NATIVE_WORKER,
            system_prompt="Worker",
            description="Does work",
        )

        registry.register(worker)

        roster = registry.get_roster()
        assert len(roster) == 1
        assert "worker" in roster[0]
        assert "Does work" in roster[0]
