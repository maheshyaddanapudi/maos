"""Tests for the agent registry."""

from unittest.mock import MagicMock

import pytest

from maos.agents.factory import AgentFactory
from maos.agents.models import ExternalAgent, SupervisorAgent, WorkerAgent
from maos.agents.registry import AgentRegistry
from maos.config.models import (
    AgentConfig,
    AgentKind,
    Config,
    LLMConfig,
    LLMProvider,
)


@pytest.fixture
def mock_factory():
    factory = MagicMock(spec=AgentFactory)

    def create_worker(name, config):
        return WorkerAgent(
            name=name,
            description=config.description or f"Worker {name}",
            system_prompt=config.system_prompt,
            llm_name=config.llm,
        )

    def create_supervisor(name, config, roster):
        sup = SupervisorAgent(
            name=name,
            system_prompt=config.system_prompt,
            llm_name=config.llm,
            roster=roster,
        )
        sup.set_llm(MagicMock())
        return sup

    factory.create_worker = MagicMock(side_effect=create_worker)
    factory.create_supervisor = MagicMock(side_effect=create_supervisor)
    return factory


@pytest.fixture
def multi_agent_config():
    return Config(
        llms={"default": LLMConfig(provider=LLMProvider.OPENAI, model="gpt-4o-mini")},
        agents={
            "supervisor": AgentConfig(
                kind=AgentKind.SUPERVISOR,
                llm="default",
                system_prompt="Route tasks.",
            ),
            "worker1": AgentConfig(
                kind=AgentKind.NATIVE_WORKER,
                llm="default",
                system_prompt="Worker 1",
                description="First worker",
            ),
            "worker2": AgentConfig(
                kind=AgentKind.NATIVE_WORKER,
                llm="default",
                system_prompt="Worker 2",
                description="Second worker",
            ),
            "ext_agent": AgentConfig(
                kind=AgentKind.EXTERNAL,
                llm="default",
                system_prompt="External",
                description="External agent",
            ),
        },
    )


class TestAgentRegistryBuild:
    def test_build_creates_workers(self, mock_factory, multi_agent_config):
        registry = AgentRegistry(factory=mock_factory)
        registry.build(multi_agent_config)
        assert mock_factory.create_worker.call_count == 2
        assert registry.get_worker("worker1") is not None
        assert registry.get_worker("worker2") is not None

    def test_build_creates_supervisor(self, mock_factory, multi_agent_config):
        registry = AgentRegistry(factory=mock_factory)
        registry.build(multi_agent_config)
        sup = registry.get_supervisor()
        assert sup is not None
        assert "worker1" in sup.roster
        assert "worker2" in sup.roster

    def test_build_collects_external_configs(self, mock_factory, multi_agent_config):
        registry = AgentRegistry(factory=mock_factory)
        registry.build(multi_agent_config)
        ext_configs = registry.get_external_configs()
        assert "ext_agent" in ext_configs

    def test_build_supervisor_roster_includes_externals(
        self, mock_factory, multi_agent_config
    ):
        registry = AgentRegistry(factory=mock_factory)
        registry.build(multi_agent_config)
        sup = registry.get_supervisor()
        assert "ext_agent" in sup.roster


class TestAgentRegistryLookup:
    def test_get_worker(self, mock_factory, multi_agent_config):
        registry = AgentRegistry(factory=mock_factory)
        registry.build(multi_agent_config)
        worker = registry.get_worker("worker1")
        assert worker is not None
        assert worker.name == "worker1"

    def test_get_worker_nonexistent(self, mock_factory, multi_agent_config):
        registry = AgentRegistry(factory=mock_factory)
        registry.build(multi_agent_config)
        assert registry.get_worker("nonexistent") is None

    def test_get_supervisor(self, mock_factory, multi_agent_config):
        registry = AgentRegistry(factory=mock_factory)
        registry.build(multi_agent_config)
        sup = registry.get_supervisor()
        assert sup is not None
        assert isinstance(sup, SupervisorAgent)

    def test_get_workers(self, mock_factory, multi_agent_config):
        registry = AgentRegistry(factory=mock_factory)
        registry.build(multi_agent_config)
        workers = registry.get_workers()
        assert len(workers) == 2
        names = {name for name, agent in workers}
        assert names == {"worker1", "worker2"}

    def test_get_agent_finds_worker(self, mock_factory, multi_agent_config):
        registry = AgentRegistry(factory=mock_factory)
        registry.build(multi_agent_config)
        agent = registry.get_agent("worker1")
        assert agent is not None
        assert agent.name == "worker1"

    def test_get_agent_finds_supervisor(self, mock_factory, multi_agent_config):
        registry = AgentRegistry(factory=mock_factory)
        registry.build(multi_agent_config)
        agent = registry.get_agent("supervisor")
        assert agent is not None

    def test_get_agent_nonexistent(self, mock_factory, multi_agent_config):
        registry = AgentRegistry(factory=mock_factory)
        registry.build(multi_agent_config)
        assert registry.get_agent("ghost") is None


class TestAgentRegistryExternal:
    def test_add_external(self, mock_factory, multi_agent_config):
        registry = AgentRegistry(factory=mock_factory)
        registry.build(multi_agent_config)

        ext = ExternalAgent(
            name="discovered_agent",
            description="Discovered via A2A",
            endpoint="http://localhost:9000",
            import_mode="node",
        )
        registry.add_external(ext)
        assert registry.get_external("discovered_agent") is not None
        sup = registry.get_supervisor()
        assert "discovered_agent" in sup.roster

    def test_add_external_tool_mode(self, mock_factory, multi_agent_config):
        registry = AgentRegistry(factory=mock_factory)
        registry.build(multi_agent_config)

        ext = ExternalAgent(
            name="tool_agent",
            description="Tool-only agent",
            endpoint="http://localhost:9001",
            import_mode="tool",
        )
        registry.add_external(ext)
        assert registry.get_external("tool_agent") is not None

    def test_get_roster(self, mock_factory, multi_agent_config):
        registry = AgentRegistry(factory=mock_factory)
        registry.build(multi_agent_config)
        roster = registry.get_roster()
        assert "worker1" in roster
        assert "worker2" in roster

    def test_get_roster_includes_node_externals(
        self, mock_factory, multi_agent_config
    ):
        registry = AgentRegistry(factory=mock_factory)
        registry.build(multi_agent_config)

        ext = ExternalAgent(
            name="node_ext",
            description="Node external",
            endpoint="http://localhost:9002",
            import_mode="node",
        )
        registry.add_external(ext)
        roster = registry.get_roster()
        assert "node_ext" in roster
