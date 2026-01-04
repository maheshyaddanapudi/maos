"""
MAOS Tool Models.

Data structures for tools and tool execution.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


class JsonSchema(BaseModel):
    """JSON Schema for tool input validation."""
    type: str = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)
    description: str | None = None


@dataclass
class ToolCall:
    """A request to call a tool."""
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result from a tool execution."""
    tool_id: str
    tool_name: str
    output: Any
    success: bool = True
    error: str | None = None
    duration_ms: int = 0

    @classmethod
    def success_result(cls, tool_id: str, tool_name: str, output: Any, duration_ms: int = 0) -> "ToolResult":
        """Create a successful result."""
        return cls(
            tool_id=tool_id,
            tool_name=tool_name,
            output=output,
            success=True,
            duration_ms=duration_ms,
        )

    @classmethod
    def error_result(cls, tool_id: str, tool_name: str, error: str, duration_ms: int = 0) -> "ToolResult":
        """Create an error result."""
        return cls(
            tool_id=tool_id,
            tool_name=tool_name,
            output=None,
            success=False,
            error=error,
            duration_ms=duration_ms,
        )


@dataclass
class ToolCallRecord:
    """Record of a tool invocation during execution."""
    tool_id: str
    tool_name: str
    input_args: dict[str, Any]
    output: Any
    success: bool = True
    error_message: str | None = None
    duration_ms: int = 0

    @classmethod
    def from_result(cls, call: ToolCall, result: ToolResult) -> "ToolCallRecord":
        """Create from call and result."""
        return cls(
            tool_id=call.id,
            tool_name=call.name,
            input_args=call.arguments,
            output=result.output,
            success=result.success,
            error_message=result.error,
            duration_ms=result.duration_ms,
        )


class Tool:
    """Internal representation of a callable tool."""

    def __init__(
        self,
        id: str,
        name: str,
        description: str,
        server: str,
        mcp_tool_name: str,
        input_schema: dict[str, Any],
        timeout_seconds: int = 30,
        invoke_func: Callable[[dict[str, Any]], Awaitable[Any]] | None = None,
    ):
        self.id = id
        self.name = name
        self.description = description
        self.server = server
        self.mcp_tool_name = mcp_tool_name
        self.input_schema = input_schema
        self.timeout_seconds = timeout_seconds
        self._invoke_func = invoke_func

    def set_invoke_func(self, func: Callable[[dict[str, Any]], Awaitable[Any]]) -> None:
        """Set the invocation function."""
        self._invoke_func = func

    async def call(self, arguments: dict[str, Any]) -> Any:
        """Invoke the tool with given arguments.

        Args:
            arguments: Tool arguments

        Returns:
            Tool output

        Raises:
            RuntimeError: If tool not connected
        """
        if self._invoke_func is None:
            raise RuntimeError(f"Tool {self.id} not connected")
        return await self._invoke_func(arguments)

    def to_llm_tool_definition(self) -> dict[str, Any]:
        """Convert to LLM tool definition format."""
        return {
            "type": "function",
            "function": {
                "name": self.id,
                "description": self.description,
                "parameters": self.input_schema,
            }
        }

    def __repr__(self) -> str:
        return f"Tool(id={self.id!r}, server={self.server!r})"
