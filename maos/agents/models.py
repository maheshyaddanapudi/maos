"""Agent data models."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr


class Agent(BaseModel):
    """Base agent model."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str = ""
    system_prompt: str
    framework: str = "langchain"
    timeout_seconds: int = 60


class WorkerAgent(Agent):
    """A native worker agent."""

    skillset: str | None = None
    tool_ids: list[str] = Field(default_factory=list)
    llm_name: str = "default"

    # Runtime instance (set by factory)
    _instance: Any = None

    def set_instance(self, instance: Any) -> None:
        """Set the agent runtime instance."""
        self._instance = instance

    @property
    def instance(self) -> Any:
        """Get the agent runtime instance."""
        return self._instance


class SupervisorAgent(Agent):
    """The supervisor agent for routing."""

    roster: list[str] = Field(default_factory=list)
    llm_name: str = "default"
    max_iterations: int = 12

    # Runtime instance (set by factory)
    _llm: Any = None

    def set_llm(self, llm: Any) -> None:
        """Set the LLM adapter."""
        self._llm = llm

    @property
    def llm(self) -> Any:
        """Get the LLM adapter."""
        return self._llm


class ExternalAgent(BaseModel):
    """An agent discovered via A2A protocol or managed locally."""

    name: str
    description: str = ""
    endpoint: str
    skills: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    supports_streaming: bool = False
    source_url: str = ""

    # Whether to import as node or tool
    import_mode: str = "node"  # "node" or "tool"
    assigned_to: str | None = None  # Worker name for tool mode

    # For managed external agents - the server instance
    _server: Any = PrivateAttr(default=None)
    # The discovered agent representation (used by A2A client)
    _discovered_agent: Any = PrivateAttr(default=None)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def node_id(self) -> str:
        """Get the LangGraph node ID for this agent."""
        # Use simple name - LangGraph doesn't allow ':' in node names
        return self.name

    @property
    def discovered_agent(self) -> Any:
        """Get the DiscoveredAgent representation for A2A calls."""
        if self._discovered_agent is not None:
            return self._discovered_agent

        # Create a minimal DiscoveredAgent for A2A client
        from maos.a2a.models import AgentCard, AgentSkill, DiscoveredAgent, ServiceInterface

        card = AgentCard(
            name=self.name,
            description=self.description,
            supportedInterfaces=[ServiceInterface(url=self.endpoint, protocol_binding="JSONRPC")],
            skills=[AgentSkill(id=s, name=s, description="") for s in self.skills],
        )
        self._discovered_agent = DiscoveredAgent(
            card=card,
            source_url=self.source_url or self.endpoint,
            endpoint=self.endpoint,
            import_mode=self.import_mode,
        )
        return self._discovered_agent

    def set_discovered_agent(self, discovered: Any) -> None:
        """Set the discovered agent representation."""
        self._discovered_agent = discovered
