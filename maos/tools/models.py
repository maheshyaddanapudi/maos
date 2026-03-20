"""Tool data models."""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field


class JsonSchema(BaseModel):
    """JSON Schema for tool input validation."""
    type: str = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)
    description: str | None = None


class Tool(BaseModel):
    """Internal representation of a callable tool."""
    id: str  # Unique tool ID in registry
    name: str  # Display name
    description: str
    server: str  # MCP server name
    mcp_tool_name: str  # Tool name in MCP server
    input_schema: JsonSchema = Field(default_factory=JsonSchema)
    timeout_seconds: int = 30

    # Runtime handle (not serialized)
    _invoke_fn: Callable | None = None

    class Config:
        arbitrary_types_allowed = True
        underscore_attrs_are_private = True

    def set_invoke_fn(self, fn: Callable) -> None:
        """Set the invocation function."""
        self._invoke_fn = fn

    async def call(self, arguments: dict[str, Any]) -> Any:
        """
        Invoke the tool with given arguments.

        Args:
            arguments: Tool arguments.

        Returns:
            Tool result.

        Raises:
            RuntimeError: If tool is not connected.
        """
        if self._invoke_fn is None:
            raise RuntimeError(f"Tool {self.id} not connected")
        return await self._invoke_fn(arguments)

    def to_llm_definition(self) -> dict[str, Any]:
        """Convert to LLM tool definition format."""
        return {
            "name": self.id,
            "description": self.description,
            "parameters": self.input_schema.model_dump()
        }


class ToolCall(BaseModel):
    """A call to a tool."""
    id: str
    tool_id: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """Result of a tool invocation."""
    tool_id: str
    tool_name: str
    input_args: dict[str, Any]
    output: Any
    success: bool = True
    error_message: str | None = None
    duration_ms: int = 0
