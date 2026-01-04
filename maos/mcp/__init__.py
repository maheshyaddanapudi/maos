"""MCP integration using the official Anthropic MCP SDK.

This module provides MCP server connections using the official SDK,
which handles:
- Protocol negotiation
- JSON-RPC framing
- Session lifecycle management
- Tool invocation

Usage:
    from maos.mcp import MCPRegistry, MCPToolDefinition

    registry = MCPRegistry()
    await registry.register("server", config)
    await registry.connect_all()

    tools = registry.get_all_tools()
    result = await registry.call_tool("server", "tool_name", {"arg": "value"})

    await registry.disconnect_all()
"""

from maos.mcp.registry import MCPRegistry, MCPServerConnection
from maos.mcp.official_client import MCPToolDefinition

__all__ = [
    "MCPRegistry",
    "MCPServerConnection",
    "MCPToolDefinition",
]
