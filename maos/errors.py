"""
MAOS - Custom exception classes.
"""

from typing import Any


class MAOSError(Exception):
    """Base exception for MAOS errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigError(MAOSError):
    """Configuration-related errors."""
    pass


class ValidationError(MAOSError):
    """Validation errors."""
    pass


class LLMError(MAOSError):
    """LLM provider errors."""
    pass


class MCPError(MAOSError):
    """MCP connection or tool errors."""
    pass


class MCPConnectionError(MCPError):
    """MCP connection failed."""
    pass


class ToolError(MAOSError):
    """Tool execution errors."""
    pass


class ToolTimeoutError(ToolError):
    """Tool execution timed out."""
    pass


class A2AError(MAOSError):
    """A2A protocol errors."""
    pass


class A2ADiscoveryError(A2AError):
    """A2A agent discovery errors."""
    pass


class A2AConnectionError(A2AError):
    """A2A connection errors."""
    pass


class GraphError(MAOSError):
    """LangGraph orchestration errors."""
    pass


class MaxIterationsError(GraphError):
    """Maximum iterations exceeded."""
    pass


class RoutingError(GraphError):
    """Supervisor routing errors."""
    pass


class AgentError(MAOSError):
    """Agent execution errors."""
    pass


class AgentTimeoutError(AgentError):
    """Agent execution timed out."""
    pass
