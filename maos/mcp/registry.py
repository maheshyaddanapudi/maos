"""
MAOS MCP Registry.

Manages connections to multiple MCP servers.
"""

import asyncio
from typing import Any

import structlog

from maos.config.models import MCPServerConfig
from maos.errors import MCPError
from maos.mcp.connection import ConnectionStatus, MCPConnection
from maos.mcp.models import MCPToolDef, MCPToolResult

log = structlog.get_logger()


class MCPRegistry:
    """Registry of MCP server connections."""

    def __init__(self):
        self._connections: dict[str, MCPConnection] = {}

    async def connect_all(self, configs: dict[str, MCPServerConfig]) -> None:
        """Connect to all configured MCP servers.

        Args:
            configs: Dictionary of server configurations keyed by name
        """
        if not configs:
            log.info("no_mcp_servers_configured")
            return

        log.info("connecting_mcp_servers", count=len(configs))

        # Connect to servers concurrently
        tasks = []
        for name, config in configs.items():
            connection = MCPConnection(name, config)
            self._connections[name] = connection
            tasks.append(self._connect_with_error_handling(connection))

        await asyncio.gather(*tasks)

        connected = sum(1 for c in self._connections.values() if c.is_connected)
        log.info("mcp_servers_connected", connected=connected, total=len(configs))

    async def _connect_with_error_handling(self, connection: MCPConnection) -> None:
        """Connect with error handling - don't fail on individual connection errors."""
        try:
            await connection.connect()
        except Exception as e:
            log.warning(
                "mcp_server_connection_failed",
                name=connection.name,
                error=str(e),
            )

    async def connect(self, name: str, config: MCPServerConfig) -> MCPConnection:
        """Connect to a single MCP server.

        Args:
            name: Server name
            config: Server configuration

        Returns:
            MCP connection
        """
        connection = MCPConnection(name, config)
        await connection.connect()
        self._connections[name] = connection
        return connection

    def get_connection(self, name: str) -> MCPConnection | None:
        """Get connection by server name.

        Args:
            name: Server name

        Returns:
            MCP connection or None if not found
        """
        return self._connections.get(name)

    def get_connection_or_raise(self, name: str) -> MCPConnection:
        """Get connection by name or raise error.

        Args:
            name: Server name

        Returns:
            MCP connection

        Raises:
            MCPError: If connection not found
        """
        connection = self.get_connection(name)
        if connection is None:
            raise MCPError(f"MCP server not found: {name}")
        return connection

    async def get_tools(self, server_name: str) -> list[MCPToolDef]:
        """Get tool definitions from a server.

        Args:
            server_name: Server name

        Returns:
            List of tool definitions
        """
        connection = self.get_connection(server_name)
        if connection is None or not connection.is_connected:
            return []
        return connection.tools

    async def get_all_tools(self) -> dict[str, list[MCPToolDef]]:
        """Get all tools from all connected servers.

        Returns:
            Dictionary of tools keyed by server name
        """
        result = {}
        for name, connection in self._connections.items():
            if connection.is_connected:
                result[name] = connection.tools
        return result

    async def invoke_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> MCPToolResult:
        """Invoke a tool on a specific server.

        Args:
            server_name: Server name
            tool_name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result
        """
        connection = self.get_connection_or_raise(server_name)

        if not connection.is_connected:
            return MCPToolResult.error(f"Server {server_name} not connected")

        return await connection.invoke_tool(tool_name, arguments)

    async def disconnect_all(self) -> None:
        """Disconnect all servers."""
        log.info("disconnecting_mcp_servers", count=len(self._connections))

        tasks = [conn.disconnect() for conn in self._connections.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

        self._connections.clear()
        log.info("mcp_servers_disconnected")

    async def disconnect(self, name: str) -> None:
        """Disconnect a specific server.

        Args:
            name: Server name
        """
        connection = self._connections.pop(name, None)
        if connection:
            await connection.disconnect()

    def list_servers(self) -> list[str]:
        """List all server names.

        Returns:
            List of server names
        """
        return list(self._connections.keys())

    def list_connected_servers(self) -> list[str]:
        """List connected server names.

        Returns:
            List of connected server names
        """
        return [
            name for name, conn in self._connections.items()
            if conn.is_connected
        ]

    def get_status(self) -> dict[str, ConnectionStatus]:
        """Get status of all servers.

        Returns:
            Dictionary of statuses keyed by server name
        """
        return {name: conn.status for name, conn in self._connections.items()}

    def __len__(self) -> int:
        return len(self._connections)

    def __contains__(self, name: str) -> bool:
        return name in self._connections
