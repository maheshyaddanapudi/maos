"""Agent data models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Agent(BaseModel):
    """Base agent model."""
    name: str
    description: str = ""
    system_prompt: str
    framework: str = "langchain"
    timeout_seconds: int = 60

    class Config:
        arbitrary_types_allowed = True


class WorkerAgent(Agent):
    """A native worker agent."""
    skillset: Optional[str] = None
    tool_ids: List[str] = Field(default_factory=list)
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
    roster: List[str] = Field(default_factory=list)
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
    """An agent discovered via A2A protocol."""
    name: str
    description: str = ""
    endpoint: str
    skills: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    supports_streaming: bool = False
    source_url: str = ""

    # Whether to import as node or tool
    import_mode: str = "node"  # "node" or "tool"
    assigned_to: Optional[str] = None  # Worker name for tool mode

    @property
    def node_id(self) -> str:
        """Get the LangGraph node ID for this agent."""
        return f"ext::{self.name}"
