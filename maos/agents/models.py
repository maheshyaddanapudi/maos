"""
MAOS Agent Models.

Data structures for agents and execution results.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from maos.config.models import AgentFramework, AgentKind
from maos.tools.models import Tool, ToolCallRecord


class ResultType(str, Enum):
    """Type of result output."""
    TEXT = "text"
    ERROR = "error"
    PARTIAL = "partial"
    STRUCTURED = "structured"


@dataclass
class ResultMetadata:
    """Metadata about the agent execution."""
    tokens_used: int = 0
    duration_ms: int = 0
    tools_invoked: list[str] = field(default_factory=list)
    model_used: str | None = None
    retry_count: int = 0


@dataclass
class ResultOutput:
    """Structured output from agent execution."""
    type: ResultType = ResultType.TEXT
    content: str = ""
    sources: list[str] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    structured_data: dict[str, Any] | None = None


@dataclass
class WorkerResult:
    """Complete result from a worker agent execution."""
    from_agent: str
    output: ResultOutput
    metadata: ResultMetadata = field(default_factory=ResultMetadata)

    @property
    def is_error(self) -> bool:
        """Check if result represents an error."""
        return self.output.type == ResultType.ERROR

    @property
    def is_partial(self) -> bool:
        """Check if result is partial (incomplete)."""
        return self.output.type == ResultType.PARTIAL

    @property
    def content(self) -> str:
        """Shortcut to output content."""
        return self.output.content

    def to_message(self) -> dict[str, Any]:
        """Convert to message format for graph state."""
        return {
            "role": "assistant",
            "name": self.from_agent,
            "content": self.output.content,
        }

    @classmethod
    def success(
        cls,
        from_agent: str,
        content: str,
        tool_calls: list[ToolCallRecord] | None = None,
        metadata: ResultMetadata | None = None,
    ) -> "WorkerResult":
        """Create a successful result."""
        return cls(
            from_agent=from_agent,
            output=ResultOutput(
                type=ResultType.TEXT,
                content=content,
                tool_calls=tool_calls or [],
            ),
            metadata=metadata or ResultMetadata(),
        )

    @classmethod
    def error(
        cls,
        from_agent: str,
        error_message: str,
        metadata: ResultMetadata | None = None,
    ) -> "WorkerResult":
        """Create an error result."""
        return cls(
            from_agent=from_agent,
            output=ResultOutput(
                type=ResultType.ERROR,
                content=error_message,
            ),
            metadata=metadata or ResultMetadata(),
        )


# Alias for compatibility
AgentResult = WorkerResult


class Agent:
    """Internal representation of an agent."""

    def __init__(
        self,
        name: str,
        kind: AgentKind,
        description: str = "",
        framework: AgentFramework = AgentFramework.LANGCHAIN,
        llm_name: str = "default",
        skillset_name: str | None = None,
        system_prompt: str = "",
        tools: list[Tool] | None = None,
        timeout_seconds: int = 60,
    ):
        self.name = name
        self.kind = kind
        self.description = description
        self.framework = framework
        self.llm_name = llm_name
        self.skillset_name = skillset_name
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.timeout_seconds = timeout_seconds

        # Runtime execution function (set by factory)
        self._execute_func: Callable[[str], Awaitable[WorkerResult]] | None = None

    def set_execute_func(self, func: Callable[[str], Awaitable[WorkerResult]]) -> None:
        """Set the execution function."""
        self._execute_func = func

    async def execute(self, task: str) -> WorkerResult:
        """Execute a task with this agent.

        Args:
            task: Task description

        Returns:
            Execution result
        """
        if self._execute_func is None:
            return WorkerResult.error(self.name, "Agent not initialized")

        return await self._execute_func(task)

    @property
    def is_supervisor(self) -> bool:
        """Check if this is the supervisor agent."""
        return self.kind == AgentKind.SUPERVISOR

    @property
    def is_worker(self) -> bool:
        """Check if this is a worker agent."""
        return self.kind == AgentKind.NATIVE_WORKER

    def get_tool_names(self) -> list[str]:
        """Get list of tool names."""
        return [t.name for t in self.tools]

    def __repr__(self) -> str:
        return f"Agent(name={self.name!r}, kind={self.kind})"
