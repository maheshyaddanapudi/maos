"""Registry for MCP server connections using the official MCP SDK.

This module uses the official Anthropic MCP SDK for server connections,
providing proper protocol handling and session management.
"""

from contextlib import AsyncExitStack
from typing import Any

import structlog
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from maos.config.models import MCPServerConfig
from maos.mcp.official_client import MCPToolDefinition

logger = structlog.get_logger()


class MCPServerConnection:
    """A managed connection to an MCP server."""

    def __init__(self, name: str, session: ClientSession, tools: list[MCPToolDefinition]):
        self.name = name
        self._session = session
        self._tools = tools

    @property
    def tools(self) -> list[MCPToolDefinition]:
        """Get available tools."""
        return self._tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """
        Call a tool on this server.

        Args:
            tool_name: Name of the tool.
            arguments: Tool arguments.

        Returns:
            Tool result.
        """
        result = await self._session.call_tool(tool_name, arguments)

        # Extract content from result
        if result.content:
            for content in result.content:
                if hasattr(content, "text"):
                    return content.text
            return result.content

        return None


class MCPRegistry:
    """Registry of MCP server connections using the official SDK.

    This registry manages the lifecycle of MCP server connections,
    using the official Anthropic MCP SDK for proper protocol handling.

    Usage:
        registry = MCPRegistry()
        async with registry.connect_all(configs):
            tools = registry.get_all_tools()
            result = await registry.call_tool("server", "tool", {"arg": "value"})
    """

    def __init__(self):
        """Initialize the MCP registry."""
        self._connections: dict[str, MCPServerConnection] = {}
        self._exit_stack: AsyncExitStack | None = None
        self._configs: dict[str, MCPServerConfig] = {}

    async def register(self, name: str, config: MCPServerConfig) -> None:
        """
        Register a server configuration for later connection.

        Args:
            name: Server name.
            config: Server configuration.
        """
        self._configs[name] = config

    async def connect_all(self) -> None:
        """Connect to all registered MCP servers."""
        if self._exit_stack is not None:
            await self.disconnect_all()

        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        for name, config in self._configs.items():
            try:
                await self._connect_server(name, config)
            except Exception as e:
                logger.warning("failed_to_connect_mcp_server", server=name, error=str(e))

    async def _connect_server(self, name: str, config: MCPServerConfig) -> None:
        """Connect to a single MCP server."""
        if config.transport != "stdio":
            raise NotImplementedError(
                f"Transport '{config.transport}' not supported. "
                f"Only 'stdio' is currently supported with the official MCP SDK."
            )

        if not config.command:
            raise ValueError(f"MCP server '{name}' requires 'command' for stdio transport")

        logger.info("connecting_to_mcp_server", server=name)

        # Create server parameters
        server_params = StdioServerParameters(
            command=config.command[0],
            args=config.command[1:] if len(config.command) > 1 else [],
            env=config.env,
        )

        # Enter the stdio_client context
        read, write = await self._exit_stack.enter_async_context(stdio_client(server_params))

        # Create and initialize session
        session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()

        # List available tools
        tools_result = await session.list_tools()
        tools = [
            MCPToolDefinition(
                name=t.name,
                description=t.description or "",
                input_schema=t.inputSchema or {},
                server_name=name,
            )
            for t in tools_result.tools
        ]

        # Store connection
        self._connections[name] = MCPServerConnection(name, session, tools)

        logger.info("connected_to_mcp_server", server=name, tools_count=len(tools))

    def get_connection(self, name: str) -> MCPServerConnection | None:
        """Get a connection by server name."""
        return self._connections.get(name)

    def get_all_tools(self) -> list[MCPToolDefinition]:
        """Get all tools from all connected servers."""
        tools = []
        for connection in self._connections.values():
            tools.extend(connection.tools)
        return tools

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> Any:
        """
        Call a tool on a specific server.

        Args:
            server_name: Name of the server.
            tool_name: Name of the tool.
            arguments: Tool arguments.

        Returns:
            Tool result.

        Raises:
            KeyError: If server not found.
        """
        connection = self._connections.get(server_name)
        if not connection:
            raise KeyError(f"MCP server not connected: {server_name}")
        return await connection.call_tool(tool_name, arguments)

    async def disconnect_all(self) -> None:
        """Disconnect from all servers."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
        self._connections.clear()
        logger.info("disconnected_all_mcp_servers")

    def list(self) -> list[str]:
        """List all connected server names."""
        return list(self._connections.keys())

    def __contains__(self, name: str) -> bool:
        """Check if a server is connected."""
        return name in self._connections

    def __len__(self) -> int:
        """Get number of connected servers."""
        return len(self._connections)
