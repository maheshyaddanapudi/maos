"""Registry for MCP server connections."""

import asyncio
from typing import Dict, List, Optional

import structlog

from maos.config.models import MCPServerConfig
from maos.mcp.connection import MCPConnection, MCPToolDefinition

logger = structlog.get_logger()


class MCPRegistry:
    """Registry of MCP server connections."""

    def __init__(self):
        """Initialize the MCP registry."""
        self._connections: Dict[str, MCPConnection] = {}

    async def connect_all(self, configs: Dict[str, MCPServerConfig]) -> None:
        """
        Connect to all configured MCP servers.

        Args:
            configs: Dictionary of server configurations.
        """
        # Connect to servers in parallel
        tasks = [
            self._connect_server(name, config)
            for name, config in configs.items()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any connection failures
        for (name, _), result in zip(configs.items(), results):
            if isinstance(result, Exception):
                logger.warning(
                    "failed_to_connect_mcp_server",
                    server=name,
                    error=str(result)
                )

    async def _connect_server(
        self,
        name: str,
        config: MCPServerConfig
    ) -> MCPConnection:
        """Connect to a single server."""
        logger.info("connecting_to_mcp_server", server=name, transport=config.transport)
        connection = await MCPConnection.create(name, config)
        self._connections[name] = connection
        logger.info(
            "connected_to_mcp_server",
            server=name,
            tools=len(connection.tools)
        )
        return connection

    async def connect(
        self,
        name: str,
        config: MCPServerConfig
    ) -> MCPConnection:
        """
        Connect to a single MCP server.

        Args:
            name: Server name.
            config: Server configuration.

        Returns:
            The connection.
        """
        return await self._connect_server(name, config)

    def get_connection(self, name: str) -> Optional[MCPConnection]:
        """
        Get a connection by server name.

        Args:
            name: Server name.

        Returns:
            The connection if found.
        """
        return self._connections.get(name)

    def get_connection_or_raise(self, name: str) -> MCPConnection:
        """
        Get a connection by name, raising if not found.

        Args:
            name: Server name.

        Returns:
            The connection.

        Raises:
            KeyError: If connection not found.
        """
        connection = self._connections.get(name)
        if connection is None:
            raise KeyError(f"MCP connection not found: {name}")
        return connection

    async def get_tools(self, server_name: str) -> List[MCPToolDefinition]:
        """
        Get tool definitions from a server.

        Args:
            server_name: Server name.

        Returns:
            List of tool definitions.
        """
        connection = self.get_connection_or_raise(server_name)
        return connection.tools

    def get_all_tools(self) -> List[MCPToolDefinition]:
        """
        Get all tools from all connected servers.

        Returns:
            List of all tool definitions.
        """
        tools = []
        for connection in self._connections.values():
            tools.extend(connection.tools)
        return tools

    async def disconnect_all(self) -> None:
        """Disconnect from all servers."""
        tasks = [
            connection.disconnect()
            for connection in self._connections.values()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        self._connections.clear()
        logger.info("disconnected_all_mcp_servers")

    def list(self) -> List[str]:
        """List all connected server names."""
        return list(self._connections.keys())

    def __contains__(self, name: str) -> bool:
        """Check if a server is connected."""
        return name in self._connections

    def __len__(self) -> int:
        """Get number of connected servers."""
        return len(self._connections)
