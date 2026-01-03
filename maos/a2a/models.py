"""
MAOS A2A Models.

Data structures for A2A protocol communication.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    """A2A task status values."""
    SUBMITTED = "SUBMITTED"
    WORKING = "WORKING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INPUT_REQUIRED = "INPUT_REQUIRED"


@dataclass
class AgentSkill:
    """A skill exposed by an A2A agent."""
    id: str
    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentSkill":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            examples=data.get("examples", []),
        )


@dataclass
class AgentCapabilities:
    """Agent capability flags."""
    streaming: bool = False
    push_notifications: bool = False
    state_transition_history: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentCapabilities":
        return cls(
            streaming=data.get("streaming", False),
            push_notifications=data.get("pushNotifications", False),
            state_transition_history=data.get("stateTransitionHistory", False),
        )


@dataclass
class ServiceInterface:
    """A2A service interface definition."""
    url: str
    protocol_binding: str = "JSONRPC"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServiceInterface":
        return cls(
            url=data.get("url", ""),
            protocol_binding=data.get("protocolBinding", "JSONRPC"),
        )


@dataclass
class AgentCard:
    """Parsed A2A Agent Card from /.well-known/agent.json."""
    name: str
    description: str = ""
    version: str = "1.0.0"
    protocol_version: str = "1.0"
    supported_interfaces: list[ServiceInterface] = field(default_factory=list)
    capabilities: AgentCapabilities = field(default_factory=AgentCapabilities)
    default_input_modes: list[str] = field(default_factory=lambda: ["text/plain"])
    default_output_modes: list[str] = field(default_factory=lambda: ["text/plain"])
    skills: list[AgentSkill] = field(default_factory=list)
    url: str | None = None  # Source URL

    @property
    def endpoint(self) -> str | None:
        """Get primary endpoint URL."""
        if self.supported_interfaces:
            return self.supported_interfaces[0].url
        return self.url

    @property
    def skill_names(self) -> list[str]:
        """Get list of skill names."""
        return [skill.name for skill in self.skills]

    @property
    def all_tags(self) -> list[str]:
        """Get all unique tags across skills."""
        tags: set[str] = set()
        for skill in self.skills:
            tags.update(skill.tags)
        return list(tags)

    @classmethod
    def from_dict(cls, data: dict[str, Any], url: str | None = None) -> "AgentCard":
        interfaces = [
            ServiceInterface.from_dict(i)
            for i in data.get("supportedInterfaces", [])
        ]
        capabilities = AgentCapabilities.from_dict(data.get("capabilities", {}))
        skills = [
            AgentSkill.from_dict(s)
            for s in data.get("skills", [])
        ]

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            protocol_version=data.get("protocolVersion", "1.0"),
            supported_interfaces=interfaces,
            capabilities=capabilities,
            default_input_modes=data.get("defaultInputModes", ["text/plain"]),
            default_output_modes=data.get("defaultOutputModes", ["text/plain"]),
            skills=skills,
            url=url,
        )


@dataclass
class DiscoveredAgent:
    """An agent discovered via A2A."""
    card: AgentCard
    source_url: str
    endpoint: str
    import_mode: str = "node"  # "node" or "tool"
    assigned_to: str | None = None  # Worker name for tools_only mode


@dataclass
class MessagePart:
    """A part of an A2A message."""
    type: str  # "text", "data", "file"
    text: str | None = None
    data: dict[str, Any] | None = None
    mime_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type}
        if self.text is not None:
            d["text"] = self.text
        if self.data is not None:
            d["data"] = self.data
        if self.mime_type is not None:
            d["mimeType"] = self.mime_type
        return d


@dataclass
class A2AMessage:
    """An A2A protocol message."""
    role: str  # "user", "agent"
    parts: list[MessagePart] = field(default_factory=list)

    @classmethod
    def from_text(cls, role: str, text: str) -> "A2AMessage":
        """Create a simple text message."""
        return cls(role=role, parts=[MessagePart(type="text", text=text)])

    def get_text(self) -> str:
        """Extract text content from parts."""
        texts = [p.text for p in self.parts if p.type == "text" and p.text]
        return "\n".join(texts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "parts": [p.to_dict() for p in self.parts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "A2AMessage":
        parts = [
            MessagePart(
                type=p.get("type", "text"),
                text=p.get("text"),
                data=p.get("data"),
                mime_type=p.get("mimeType"),
            )
            for p in data.get("parts", [])
        ]
        return cls(role=data.get("role", "user"), parts=parts)


@dataclass
class A2AConfiguration:
    """Configuration for an A2A request."""
    timeout: int = 40
    stream: bool = False
    accepted_output_modes: list[str] = field(default_factory=lambda: ["text/plain"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeout": self.timeout,
            "stream": self.stream,
            "acceptedOutputModes": self.accepted_output_modes,
        }


@dataclass
class A2ARequest:
    """A2A JSON-RPC 2.0 request."""
    method: str
    id: str
    message: A2AMessage
    configuration: A2AConfiguration = field(default_factory=A2AConfiguration)

    def to_dict(self) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "method": self.method,
            "id": self.id,
            "params": {
                "message": self.message.to_dict(),
                "configuration": self.configuration.to_dict(),
            },
        }


@dataclass
class A2ATask:
    """An A2A task with status and result."""
    id: str
    status: TaskStatus
    result: A2AMessage | None = None
    error: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "A2ATask":
        result = None
        if "result" in data and data["result"]:
            result = A2AMessage.from_dict(data["result"])

        return cls(
            id=data.get("id", ""),
            status=TaskStatus(data.get("status", "FAILED")),
            result=result,
            error=data.get("error"),
        )


@dataclass
class A2AResponse:
    """A2A JSON-RPC 2.0 response."""
    id: str
    task: A2ATask | None = None
    error: dict[str, Any] | None = None

    @property
    def is_success(self) -> bool:
        """Check if response is successful."""
        return self.error is None and self.task is not None

    @property
    def is_complete(self) -> bool:
        """Check if task is complete."""
        return self.task is not None and self.task.status == TaskStatus.COMPLETED

    def get_content(self) -> str | None:
        """Extract text content from successful response."""
        if self.task and self.task.result:
            return self.task.result.get_text()
        return None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "A2AResponse":
        task = None
        result = data.get("result")
        if result and "task" in result:
            task = A2ATask.from_dict(result["task"])

        return cls(
            id=data.get("id", ""),
            task=task,
            error=data.get("error"),
        )
