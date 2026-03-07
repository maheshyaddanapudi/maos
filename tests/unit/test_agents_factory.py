"""Unit tests for agents factory and registry."""

from unittest.mock import MagicMock

import pytest

from maos.agents.factory import AgentFactory
from maos.agents.models import ExternalAgent, SupervisorAgent, WorkerAgent
from maos.agents.registry import AgentRegistry
from maos.config.models import (
    AgentConfig,
    AgentKind,
    Config,
    GraphConfig,
    LLMConfig,
    LLMProvider,
)
from maos.skills.models import Skill, Skillset
from maos.skills.registry import SkillRegistry, SkillsetRegistry
from maos.tools.models import Tool
from maos.tools.registry import ToolRegistry


def _make_tool(tool_id: str, server: str = "s1") -> Tool:
    """Create a tool with the given ID."""
    return Tool(
        id=tool_id,
        name=tool_id,
        description=f"Tool {tool_id}",
        server=server,
        mcp_tool_name=tool_id,
    )


def _make_tool_registry(*tool_ids: str) -> ToolRegistry:
    """Create a ToolRegistry pre-populated with tools."""
    mcp_reg = MagicMock()
    registry = ToolRegistry(mcp_reg)
    for tid in tool_ids:
        registry.register(_make_tool(tid))
    return registry


def _make_mock_llm_registry(adapter_names=None):
    """Create a mock LLM registry."""
    from maos.llm.registry import LLMRegistry

    registry = MagicMock(spec=LLMRegistry)
    mock_adapter = MagicMock()
    mock_adapter.get_model_name.return_value = "mock-model"
    registry.get_or_default.return_value = mock_adapter
    registry.get.return_value = mock_adapter
    registry.get_or_raise.return_value = mock_adapter
    return registry


def _make_factory(tool_ids=None, skill_defs=None, skillset_defs=None, graph_config=None):
    """Create an AgentFactory with optional test data."""
    tool_reg = _make_tool_registry(*(tool_ids or []))
    skill_reg = SkillRegistry(tool_reg)
    if skill_defs:
        for name, tool_list in skill_defs.items():
            skill_reg.register(Skill(name=name, tool_ids=tool_list))
    ss_reg = SkillsetRegistry(skill_reg, tool_reg)
    if skillset_defs:
        for name, skill_list in skillset_defs.items():
            ss_reg.register(Skillset(name=name, skill_names=skill_list))
    llm_reg = _make_mock_llm_registry()
    return AgentFactory(
        llm_registry=llm_reg,
        skillset_registry=ss_reg,
        skill_registry=skill_reg,
        tool_registry=tool_reg,
        graph_config=graph_config,
    )


@pytest.mark.unit
class TestAgentModels:
    """Tests for agent data models."""

    def test_worker_agent_creation(self):
        """Test WorkerAgent creation with defaults."""
        worker = WorkerAgent(
            name="w1",
            description="Worker one",
            system_prompt="You help.",
        )
        assert worker.name == "w1"
        assert worker.framework == "langchain"
        assert worker.timeout_seconds == 60
        assert worker.tool_ids == []
        assert worker.llm_name == "default"
        assert worker.skillset is None

    def test_worker_agent_with_tools(self):
        """Test WorkerAgent with tool IDs."""
        worker = WorkerAgent(
            name="w1",
            system_prompt="Do stuff.",
            tool_ids=["t1", "t2"],
            skillset="research",
        )
        assert worker.tool_ids == ["t1", "t2"]
        assert worker.skillset == "research"

    def test_worker_agent_instance(self):
        """Test WorkerAgent set_instance and instance property."""
        worker = WorkerAgent(name="w1", system_prompt="test")
        assert worker.instance is None

        mock_instance = MagicMock()
        worker.set_instance(mock_instance)
        assert worker.instance is mock_instance

    def test_supervisor_agent_creation(self):
        """Test SupervisorAgent creation."""
        sup = SupervisorAgent(
            name="sup",
            system_prompt="Route tasks.",
            roster=["w1", "w2"],
            max_iterations=10,
        )
        assert sup.name == "sup"
        assert sup.roster == ["w1", "w2"]
        assert sup.max_iterations == 10
        assert sup.llm is None

    def test_supervisor_agent_set_llm(self):
        """Test SupervisorAgent set_llm and llm property."""
        sup = SupervisorAgent(name="sup", system_prompt="test")
        mock_llm = MagicMock()
        sup.set_llm(mock_llm)
        assert sup.llm is mock_llm

    def test_external_agent_creation(self):
        """Test ExternalAgent creation."""
        ext = ExternalAgent(
            name="ext1",
            description="External agent",
            endpoint="http://localhost:9000",
            import_mode="node",
        )
        assert ext.name == "ext1"
        assert ext.endpoint == "http://localhost:9000"
        assert ext.node_id == "ext1"
        assert ext.supports_streaming is False

    def test_external_agent_node_id(self):
        """Test ExternalAgent node_id is the agent name."""
        ext = ExternalAgent(name="my-agent", endpoint="http://x")
        assert ext.node_id == "my-agent"

    def test_external_agent_discovered_agent_property(self):
        """Test ExternalAgent auto-creates a DiscoveredAgent lazily."""
        ext = ExternalAgent(
            name="ext1",
            description="Ext one",
            endpoint="http://localhost:9000",
            skills=["skill_a"],
        )
        discovered = ext.discovered_agent
        assert discovered is not None
        assert discovered.card.name == "ext1"
        assert discovered.endpoint == "http://localhost:9000"
        # Should return the same cached instance
        assert ext.discovered_agent is discovered


@pytest.mark.unit
class TestAgentFactory:
    """Tests for AgentFactory."""

    def test_create_worker(self):
        """Test creating a native worker via factory."""
        factory = _make_factory()
        config = AgentConfig(
            kind=AgentKind.NATIVE_WORKER,
            llm="default",
            system_prompt="You help.",
            description="General worker",
        )
        worker = factory.create_worker("w1", config)

        assert isinstance(worker, WorkerAgent)
        assert worker.name == "w1"
        assert worker.description == "General worker"
        assert worker.system_prompt == "You help."

    def test_create_worker_wrong_kind_raises(self):
        """Test create_worker raises for non-worker kind."""
        factory = _make_factory()
        config = AgentConfig(
            kind=AgentKind.SUPERVISOR,
            llm="default",
            system_prompt="Route.",
        )
        with pytest.raises(ValueError, match="Expected native_worker"):
            factory.create_worker("sup", config)

    def test_create_worker_with_direct_tools(self):
        """Test creating a worker with direct tool references."""
        factory = _make_factory(tool_ids=["t1", "t2"])
        config = AgentConfig(
            kind=AgentKind.NATIVE_WORKER,
            llm="default",
            system_prompt="Work.",
            tools=["t1", "t2"],
        )
        worker = factory.create_worker("w1", config)
        assert set(worker.tool_ids) == {"t1", "t2"}

    def test_create_worker_with_skillset(self):
        """Test creating a worker that resolves tools from a skillset."""
        factory = _make_factory(
            tool_ids=["t1", "t2"],
            skill_defs={"search": ["t1"], "write": ["t2"]},
            skillset_defs={"research": ["search", "write"]},
        )
        config = AgentConfig(
            kind=AgentKind.NATIVE_WORKER,
            llm="default",
            system_prompt="Research.",
            skillset="research",
        )
        worker = factory.create_worker("researcher", config)
        assert set(worker.tool_ids) == {"t1", "t2"}

    def test_create_worker_with_missing_skillset(self):
        """Test creating a worker referencing a non-existent skillset."""
        factory = _make_factory()
        config = AgentConfig(
            kind=AgentKind.NATIVE_WORKER,
            llm="default",
            system_prompt="Work.",
            skillset="nonexistent",
        )
        worker = factory.create_worker("w1", config)
        # Should not crash, just have no tool IDs from the skillset
        assert isinstance(worker, WorkerAgent)
        assert worker.tool_ids == []

    def test_create_supervisor(self):
        """Test creating a supervisor via factory."""
        factory = _make_factory()
        config = AgentConfig(
            kind=AgentKind.SUPERVISOR,
            llm="default",
            system_prompt="Route tasks.",
        )
        sup = factory.create_supervisor("sup", config, ["w1", "w2"])

        assert isinstance(sup, SupervisorAgent)
        assert sup.name == "sup"
        assert sup.roster == ["w1", "w2"]
        assert sup.llm is not None  # Mock LLM was set

    def test_create_supervisor_wrong_kind_raises(self):
        """Test create_supervisor raises for non-supervisor kind."""
        factory = _make_factory()
        config = AgentConfig(
            kind=AgentKind.NATIVE_WORKER,
            llm="default",
            system_prompt="Work.",
        )
        with pytest.raises(ValueError, match="Expected supervisor"):
            factory.create_supervisor("sup", config, [])

    def test_create_supervisor_uses_graph_config_iterations(self):
        """Test supervisor uses max_iterations from graph config."""
        graph_config = GraphConfig(max_iterations=20)
        factory = _make_factory(graph_config=graph_config)
        config = AgentConfig(
            kind=AgentKind.SUPERVISOR,
            llm="default",
            system_prompt="Route.",
        )
        sup = factory.create_supervisor("sup", config, [])
        assert sup.max_iterations == 20

    def test_create_supervisor_default_iterations_without_graph_config(self):
        """Test supervisor defaults to 12 iterations without graph config."""
        factory = _make_factory(graph_config=None)
        config = AgentConfig(
            kind=AgentKind.SUPERVISOR,
            llm="default",
            system_prompt="Route.",
        )
        sup = factory.create_supervisor("sup", config, [])
        assert sup.max_iterations == 12

    def test_create_routes_by_kind_worker(self):
        """Test create() dispatches to create_worker for NATIVE_WORKER."""
        factory = _make_factory()
        config = AgentConfig(
            kind=AgentKind.NATIVE_WORKER,
            llm="default",
            system_prompt="Work.",
        )
        agent = factory.create("w1", config)
        assert isinstance(agent, WorkerAgent)

    def test_create_routes_by_kind_supervisor(self):
        """Test create() dispatches to create_supervisor for SUPERVISOR."""
        factory = _make_factory()
        config = AgentConfig(
            kind=AgentKind.SUPERVISOR,
            llm="default",
            system_prompt="Route.",
        )
        agent = factory.create("sup", config, roster=["w1"])
        assert isinstance(agent, SupervisorAgent)

    def test_create_external_raises(self):
        """Test create() raises for EXTERNAL kind."""
        factory = _make_factory()
        config = AgentConfig(
            kind=AgentKind.EXTERNAL,
            llm="default",
            system_prompt="Ext.",
        )
        with pytest.raises(ValueError, match="External agents"):
            factory.create("ext", config)

    def test_get_tools_for_worker(self):
        """Test getting resolved tools for a worker."""
        factory = _make_factory(tool_ids=["t1", "t2"])
        worker = WorkerAgent(name="w1", system_prompt="test", tool_ids=["t1", "t2"])
        tools = factory.get_tools_for_worker(worker)
        assert len(tools) == 2
        assert {t.id for t in tools} == {"t1", "t2"}

    def test_get_tools_for_worker_missing_tool(self):
        """Test getting tools for worker when some tools are missing."""
        factory = _make_factory(tool_ids=["t1"])
        worker = WorkerAgent(name="w1", system_prompt="test", tool_ids=["t1", "missing"])
        tools = factory.get_tools_for_worker(worker)
        assert len(tools) == 1
        assert tools[0].id == "t1"


@pytest.mark.unit
class TestAgentRegistry:
    """Tests for AgentRegistry."""

    def _make_config(self, workers=None, supervisor=True, externals=None):
        """Create a Config with the given agent definitions."""
        agents = {}
        if supervisor:
            agents["supervisor"] = AgentConfig(
                kind=AgentKind.SUPERVISOR,
                llm="default",
                system_prompt="Route tasks.",
            )
        if workers:
            for name in workers:
                agents[name] = AgentConfig(
                    kind=AgentKind.NATIVE_WORKER,
                    llm="default",
                    system_prompt=f"Worker {name}.",
                    description=f"Description {name}",
                )
        if externals:
            for name in externals:
                agents[name] = AgentConfig(
                    kind=AgentKind.EXTERNAL,
                    llm="default",
                    system_prompt=f"External {name}.",
                    description=f"Description {name}",
                )

        return Config(
            llms={
                "default": LLMConfig(provider=LLMProvider.OPENAI, model="gpt-4o-mini"),
            },
            agents=agents,
        )

    def _make_registry(self, config=None, workers=None, supervisor=True, externals=None):
        """Create and build an AgentRegistry."""
        if config is None:
            config = self._make_config(workers=workers, supervisor=supervisor, externals=externals)
        factory = _make_factory()
        registry = AgentRegistry(factory)
        registry.build(config)
        return registry

    def test_build_with_supervisor_and_workers(self):
        """Test building registry with supervisor and workers."""
        registry = self._make_registry(workers=["w1", "w2"])

        assert len(registry) == 3  # 1 supervisor + 2 workers
        assert registry.get_supervisor() is not None
        assert registry.get_supervisor().name == "supervisor"
        assert len(registry.get_workers()) == 2

    def test_build_without_supervisor(self):
        """Test building registry without a supervisor."""
        registry = self._make_registry(workers=["w1"], supervisor=False)
        assert registry.get_supervisor() is None
        assert len(registry.get_workers()) == 1

    def test_build_with_external_agents(self):
        """Test building registry with external agent configs."""
        registry = self._make_registry(workers=["w1"], externals=["ext1"])
        external_configs = registry.get_external_configs()
        assert "ext1" in external_configs

    def test_get_worker(self):
        """Test getting a worker by name."""
        registry = self._make_registry(workers=["researcher", "writer"])
        worker = registry.get_worker("researcher")
        assert worker is not None
        assert worker.name == "researcher"
        assert registry.get_worker("nonexistent") is None

    def test_get_roster(self):
        """Test getting the full roster."""
        registry = self._make_registry(workers=["w1", "w2"])
        roster = registry.get_roster()
        assert set(roster) == {"w1", "w2"}

    def test_get_roster_includes_externals(self):
        """Test that get_roster includes external agents imported as nodes."""
        registry = self._make_registry(workers=["w1"])
        ext = ExternalAgent(name="ext1", endpoint="http://localhost:9000", import_mode="node")
        registry.add_external(ext)
        roster = registry.get_roster()
        assert "w1" in roster
        assert "ext1" in roster

    def test_add_external_updates_supervisor_roster(self):
        """Test adding external agent updates supervisor roster when import_mode is node."""
        registry = self._make_registry(workers=["w1"])
        sup = registry.get_supervisor()
        initial_roster_len = len(sup.roster)

        ext = ExternalAgent(name="ext1", endpoint="http://localhost:9000", import_mode="node")
        registry.add_external(ext)

        assert len(sup.roster) == initial_roster_len + 1

    def test_get_agent_finds_worker(self):
        """Test get_agent finds workers."""
        registry = self._make_registry(workers=["w1"])
        agent = registry.get_agent("w1")
        assert agent is not None
        assert isinstance(agent, WorkerAgent)

    def test_get_agent_finds_supervisor(self):
        """Test get_agent finds supervisor."""
        registry = self._make_registry(workers=["w1"])
        agent = registry.get_agent("supervisor")
        assert agent is not None
        assert isinstance(agent, SupervisorAgent)

    def test_get_agent_finds_external(self):
        """Test get_agent finds external agents."""
        registry = self._make_registry(workers=["w1"])
        ext = ExternalAgent(name="ext1", endpoint="http://localhost:9000")
        registry.add_external(ext)
        agent = registry.get_agent("ext1")
        assert agent is not None
        assert isinstance(agent, ExternalAgent)

    def test_get_agent_returns_none_for_missing(self):
        """Test get_agent returns None for non-existent agent."""
        registry = self._make_registry(workers=["w1"])
        assert registry.get_agent("nonexistent") is None

    def test_contains_checks_all_types(self):
        """Test __contains__ checks workers, externals, and supervisor."""
        registry = self._make_registry(workers=["w1"])
        assert "w1" in registry
        assert "supervisor" in registry
        assert "missing" not in registry

    def test_list_worker_names(self):
        """Test listing worker names."""
        registry = self._make_registry(workers=["w1", "w2"])
        assert set(registry.list_worker_names()) == {"w1", "w2"}

    def test_list_external_names(self):
        """Test listing external agent names."""
        registry = self._make_registry(workers=["w1"])
        ext = ExternalAgent(name="ext1", endpoint="http://localhost:9000")
        registry.add_external(ext)
        assert registry.list_external_names() == ["ext1"]

    def test_get_externals(self):
        """Test getting all externals."""
        registry = self._make_registry(workers=["w1"])
        ext = ExternalAgent(name="ext1", endpoint="http://localhost:9000")
        registry.add_external(ext)

        externals = registry.get_externals()
        assert len(externals) == 1
        assert externals[0][0] == "ext1"

    def test_len_counts_all_agents(self):
        """Test __len__ counts supervisor + workers + externals."""
        registry = self._make_registry(workers=["w1", "w2"])
        ext = ExternalAgent(name="ext1", endpoint="http://localhost:9000")
        registry.add_external(ext)
        # 1 supervisor + 2 workers + 1 external = 4
        assert len(registry) == 4
