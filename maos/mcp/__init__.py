"""
MAOS MCP Module.

Provides MCP (Model Context Protocol) integration for tool servers.
"""

from maos.mcp.connection import MCPConnection
from maos.mcp.models import MCPToolDef, MCPToolResult
from maos.mcp.registry import MCPRegistry

__all__ = [
    "MCPToolDef",
    "MCPToolResult",
    "MCPConnection",
    "MCPRegistry",
]
