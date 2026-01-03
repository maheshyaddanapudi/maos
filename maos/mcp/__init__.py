"""MCP integration module for MAOS.

This module provides two approaches for MCP server connections:

1. Official MCP SDK (Recommended):
   - OfficialMCPConnection: Uses the official Anthropic MCP SDK
   - MCPConnectionManager: Manages multiple official connections

2. Custom Transports (Legacy):
   - MCPRegistry, MCPConnection: Custom transport implementations

The official SDK approach is preferred as it handles:
- Protocol negotiation
- JSON-RPC framing
- Session lifecycle
"""

# Official MCP SDK client (recommended)
from maos.mcp.official_client import (
    OfficialMCPConnection,
    MCPConnectionManager,
    MCPToolDefinition,
)

# Custom implementation (legacy)
from maos.mcp.registry import MCPRegistry
from maos.mcp.connection import MCPConnection

__all__ = [
    # Official SDK (recommended)
    "OfficialMCPConnection",
    "MCPConnectionManager",
    "MCPToolDefinition",
    # Legacy
    "MCPRegistry",
    "MCPConnection",
]
