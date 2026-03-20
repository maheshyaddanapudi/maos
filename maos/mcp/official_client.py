"""MCP client using the official mcp package.

This module provides MCP server connections using the official
Anthropic MCP SDK instead of custom transport implementations.

The official SDK handles:
- Protocol negotiation
- JSON-RPC message framing
- Session lifecycle management
- Tool invocation
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool as MCPTool

from maos.config.models import MCPServerConfig

logger = structlog.get_logger()


class MCPToolDefinition:
    """Definition of a tool from an MCP server."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        server_name: str
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.server_name = server_name

    @classmethod
    def from_mcp_tool(cls, tool: MCPTool, server_name: str) -> "MCPToolDefinition":
        """Create from an MCP Tool object."""
        return cls(
            name=tool.name,
            description=tool.description or "",
            input_schema=tool.inputSchema or {},
            server_name=server_name
        )


class OfficialMCPConnection:
    """Connection to an MCP server using the official SDK.

    This class wraps the official MCP SDK to provide a clean interface
    for connecting to MCP servers and invoking tools.

    Usage:
        async with OfficialMCPConnection.create("server", config) as conn:
            tools = conn.tools
            result = await conn.invoke_tool("tool_name", {"arg": "value"})
    """

    def __init__(
        self,
        name: str,
        session: ClientSession,
        tools: list[MCPToolDefinition]
    ):
        """
        Initialize the connection.

        Args:
            name: Server name.
            session: Active MCP client session.
            tools: List of available tools.
        """
        self.name = name
        self._session = session
        self._tools = tools

    @classmethod
    @asynccontextmanager
    async def create(
        cls,
        name: str,
        config: MCPServerConfig
    ) -> AsyncIterator["OfficialMCPConnection"]:
        """
        Create and connect to an MCP server.

        This is an async context manager that handles the full lifecycle:
        - Starts the server process (for stdio)
        - Initializes the session
        - Lists available tools
        - Cleans up on exit

        Args:
            name: Server name.
            config: Server configuration.

        Yields:
            Connected OfficialMCPConnection instance.
        """
        if config.transport == "stdio":
            if not config.command:
                raise ValueError(f"MCP server '{name}' with stdio transport requires 'command'")

            # Create server parameters
            server_params = StdioServerParameters(
                command=config.command[0],
                args=config.command[1:] if len(config.command) > 1 else [],
                env=config.env
            )

            # Use the official stdio_client context manager
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize the session
                    await session.initialize()

                    # List available tools
                    tools_result = await session.list_tools()
                    tools = [
                        MCPToolDefinition.from_mcp_tool(t, name)
                        for t in tools_result.tools
                    ]

                    logger.info(
                        "mcp_server_connected",
                        server=name,
                        tools_count=len(tools)
                    )

                    yield cls(name, session, tools)

        elif config.transport in ("http", "sse"):
            # HTTP/SSE transport support
            # The official MCP SDK also supports these via different clients
            # For now, raise an error - can be extended
            raise NotImplementedError(
                "HTTP/SSE transport not yet implemented with official SDK. "
                "Use 'stdio' transport or the legacy custom transports."
            )
        else:
            raise ValueError(f"Unknown transport type: {config.transport}")

    async def invoke_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any]
    ) -> Any:
        """
        Invoke a tool on this server.

        Args:
            tool_name: Name of the tool to invoke.
            arguments: Tool arguments.

        Returns:
            Tool result content.

        Raises:
            RuntimeError: If tool invocation fails.
        """
        try:
            result = await self._session.call_tool(tool_name, arguments)

            # Extract content from result
            if result.content:
                # Return first text content, or the full content list
                for content in result.content:
                    if hasattr(content, 'text'):
                        return content.text
                return result.content

            return None

        except Exception as e:
            logger.error(
                "mcp_tool_invocation_failed",
                server=self.name,
                tool=tool_name,
                error=str(e)
            )
            raise RuntimeError(f"Tool invocation failed: {e}") from e

    @property
    def tools(self) -> list[MCPToolDefinition]:
        """Get list of available tools."""
        return self._tools

    def get_tool(self, name: str) -> MCPToolDefinition | None:
        """Get a tool by name."""
        for tool in self._tools:
            if tool.name == name:
                return tool
        return None


class MCPConnectionManager:
    """Manager for multiple MCP server connections.

    This class manages the lifecycle of multiple MCP server connections,
    providing a unified interface for tool discovery and invocation.
    """

    def __init__(self):
        self._connections: dict[str, OfficialMCPConnection] = {}
        self._configs: dict[str, MCPServerConfig] = {}

    async def connect(self, name: str, config: MCPServerConfig) -> None:
        """
        Register a server configuration.

        Note: Actual connection happens lazily when tools are needed,
        or can be done explicitly with connect_all().

        Args:
            name: Server name.
            config: Server configuration.
        """
        self._configs[name] = config

    async def connect_all(self) -> AsyncIterator[tuple[str, OfficialMCPConnection]]:
        """
        Connect to all registered servers.

        Yields:
            Tuple of (server_name, connection) for each connected server.
        """
        for name, config in self._configs.items():
            try:
                async with OfficialMCPConnection.create(name, config) as conn:
                    self._connections[name] = conn
                    yield name, conn
            except Exception as e:
                logger.error("mcp_connection_failed", server=name, error=str(e))

    def get_all_tools(self) -> list[MCPToolDefinition]:
        """Get all tools from all connected servers."""
        tools = []
        for conn in self._connections.values():
            tools.extend(conn.tools)
        return tools

    async def invoke_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any]
    ) -> Any:
        """
        Invoke a tool on a specific server.

        Args:
            server_name: Name of the server.
            tool_name: Name of the tool.
            arguments: Tool arguments.

        Returns:
            Tool result.
        """
        conn = self._connections.get(server_name)
        if not conn:
            raise ValueError(f"No connection to server: {server_name}")
        return await conn.invoke_tool(tool_name, arguments)
