"""A2A protocol data models."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(StrEnum):
    """A2A task status values."""

    SUBMITTED = "SUBMITTED"
    WORKING = "WORKING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INPUT_REQUIRED = "INPUT_REQUIRED"


class AgentCapabilities(BaseModel):
    """Agent capability flags."""

    streaming: bool = False
    push_notifications: bool = False
    state_transition_history: bool = False


class AgentSkill(BaseModel):
    """A skill exposed by an A2A agent."""

    id: str
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)


class ServiceInterface(BaseModel):
    """A2A service interface definition."""

    url: str
    protocol_binding: str = "JSONRPC"


class AgentCard(BaseModel):
    """Parsed A2A Agent Card from /.well-known/agent.json."""

    name: str
    description: str = ""
    version: str = "1.0.0"
    protocol_version: str = Field(default="1.0", alias="protocolVersion")
    supported_interfaces: list[ServiceInterface] = Field(
        default_factory=list, alias="supportedInterfaces"
    )
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    default_input_modes: list[str] = Field(default=["text/plain"], alias="defaultInputModes")
    default_output_modes: list[str] = Field(default=["text/plain"], alias="defaultOutputModes")
    skills: list[AgentSkill] = Field(default_factory=list)

    # Source URL (not from JSON)
    url: str | None = None

    model_config = ConfigDict(populate_by_name=True)

    @property
    def endpoint(self) -> str | None:
        """Get primary endpoint URL."""
        if self.supported_interfaces:
            return self.supported_interfaces[0].url
        return None

    @property
    def skill_names(self) -> list[str]:
        """Get list of skill names."""
        return [skill.name for skill in self.skills]

    @property
    def all_tags(self) -> list[str]:
        """Get all unique tags across skills."""
        tags = set()
        for skill in self.skills:
            tags.update(skill.tags)
        return list(tags)


class DiscoveredAgent(BaseModel):
    """An agent discovered via A2A protocol."""

    card: AgentCard
    source_url: str
    endpoint: str
    import_mode: str = "node"  # "node" or "tool"
    assigned_to: str | None = None  # Worker name for tools_only mode


class MessagePart(BaseModel):
    """A part of an A2A message."""

    type: str  # "text", "data", "file"
    text: str | None = None
    data: dict[str, Any] | None = None
    mime_type: str | None = None


class A2AMessage(BaseModel):
    """An A2A protocol message."""

    role: str  # "user", "agent"
    parts: list[MessagePart] = Field(default_factory=list)

    @classmethod
    def from_text(cls, role: str, text: str) -> "A2AMessage":
        """Create a simple text message."""
        return cls(role=role, parts=[MessagePart(type="text", text=text)])

    def get_text(self) -> str:
        """Extract text content from parts."""
        texts = [p.text for p in self.parts if p.type == "text" and p.text]
        return "\n".join(texts)


class A2AConfiguration(BaseModel):
    """Configuration for an A2A request."""

    timeout: int = 40
    stream: bool = False
    accepted_output_modes: list[str] = Field(default=["text/plain"])


class A2AParams(BaseModel):
    """Parameters for message/send method."""

    message: A2AMessage
    configuration: A2AConfiguration = Field(default_factory=A2AConfiguration)


class A2ARequest(BaseModel):
    """A2A JSON-RPC 2.0 request."""

    jsonrpc: str = "2.0"
    method: str  # "message/send", "message/stream", "tasks/get"
    id: str
    params: A2AParams


class A2ATask(BaseModel):
    """An A2A task with status and result."""

    id: str
    status: TaskStatus
    result: A2AMessage | None = None
    error: str | None = None


class A2AResult(BaseModel):
    """Result of an A2A operation."""

    task: A2ATask


class A2AError(BaseModel):
    """A2A JSON-RPC error."""

    code: int
    message: str
    data: Any | None = None


class A2AResponse(BaseModel):
    """A2A JSON-RPC 2.0 response."""

    jsonrpc: str = "2.0"
    id: str
    result: A2AResult | None = None
    error: A2AError | None = None

    @property
    def is_success(self) -> bool:
        """Check if response is successful."""
        return self.error is None and self.result is not None

    @property
    def is_complete(self) -> bool:
        """Check if task is complete."""
        return self.result is not None and self.result.task.status == TaskStatus.COMPLETED

    def get_content(self) -> str | None:
        """Extract text content from successful response."""
        if self.result and self.result.task.result:
            return self.result.task.result.get_text()
        return None


class HostIndex(BaseModel):
    """A2A host index listing multiple agents."""

    version: str = "1.0"
    host: dict[str, str] | None = None
    agents: list[dict[str, Any]] = Field(default_factory=list)
