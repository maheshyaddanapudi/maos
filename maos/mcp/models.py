"""
MAOS MCP Models.

Data structures for MCP tool definitions and results.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MCPToolDef:
    """Tool definition from MCP server."""
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class MCPToolResult:
    """Result from MCP tool invocation."""
    content: Any
    is_error: bool = False
    error_message: str | None = None

    @classmethod
    def success(cls, content: Any) -> "MCPToolResult":
        """Create a successful result."""
        return cls(content=content, is_error=False)

    @classmethod
    def error(cls, message: str) -> "MCPToolResult":
        """Create an error result."""
        return cls(content=None, is_error=True, error_message=message)
