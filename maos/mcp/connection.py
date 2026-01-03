"""
MAOS MCP Connection.

Manages connection to a single MCP server and provides tool invocation.
"""

from enum import Enum
from typing import Any

import structlog

from maos.config.models import MCPServerConfig
from maos.config.models import MCPTransport as MCPTransportType
from maos.errors import MCPConnectionError, MCPError
from maos.mcp.models import MCPToolDef, MCPToolResult
from maos.mcp.transports.base import MCPTransport
from maos.mcp.transports.http import HTTPTransport
from maos.mcp.transports.stdio import StdioTransport

log = structlog.get_logger()


class ConnectionStatus(str, Enum):
    """MCP connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class MCPConnection:
    """Connection to a single MCP server."""

    def __init__(self, name: str, config: MCPServerConfig):
        self._name = name
        self._config = config
        self._transport: MCPTransport | None = None
        self._status = ConnectionStatus.DISCONNECTED
        self._tools: list[MCPToolDef] = []
        self._error: str | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def status(self) -> ConnectionStatus:
        return self._status

    @property
    def tools(self) -> list[MCPToolDef]:
        return self._tools

    @property
    def is_connected(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    async def connect(self) -> None:
        """Establish connection and fetch tools."""
        if self._status == ConnectionStatus.CONNECTED:
            return

        self._status = ConnectionStatus.CONNECTING

        try:
            # Create transport based on config
            self._transport = self._create_transport()

            # Connect transport
            await self._transport.connect()

            # Initialize MCP session
            await self._initialize()

            # Fetch available tools
            await self._fetch_tools()

            self._status = ConnectionStatus.CONNECTED
            log.info(
                "mcp_connected",
                name=self._name,
                tool_count=len(self._tools),
            )

        except Exception as e:
            self._status = ConnectionStatus.ERROR
            self._error = str(e)
            log.error("mcp_connection_failed", name=self._name, error=str(e))
            raise MCPConnectionError(f"Failed to connect to {self._name}: {e}")

    def _create_transport(self) -> MCPTransport:
        """Create transport based on configuration."""
        timeout = float(self._config.timeout_seconds)

        if self._config.transport == MCPTransportType.STDIO:
            if not self._config.command:
                raise MCPError("Command required for stdio transport")
            return StdioTransport(
                command=self._config.command,
                env=self._config.env,
                timeout=timeout,
            )

        elif self._config.transport in (MCPTransportType.HTTP, MCPTransportType.SSE):
            if not self._config.url:
                raise MCPError("URL required for HTTP transport")
            return HTTPTransport(
                url=self._config.url,
                timeout=timeout,
            )

        else:
            raise MCPError(f"Unsupported transport: {self._config.transport}")

    async def _initialize(self) -> None:
        """Initialize MCP session."""
        if not self._transport:
            return

        # Send initialize request
        response = await self._transport.send({
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "maos",
                    "version": "0.1.0",
                },
            },
        })

        log.debug("mcp_initialized", name=self._name, response=response)

    async def _fetch_tools(self) -> None:
        """Fetch available tools from server."""
        if not self._transport:
            return

        response = await self._transport.send({
            "method": "tools/list",
            "params": {},
        })

        result = response.get("result", {})
        tools_data = result.get("tools", [])

        self._tools = [
            MCPToolDef(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            )
            for t in tools_data
        ]

        log.debug(
            "mcp_tools_fetched",
            name=self._name,
            tools=[t.name for t in self._tools],
        )

    async def invoke_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> MCPToolResult:
        """Invoke a tool on this server.

        Args:
            tool_name: Name of the tool to invoke
            arguments: Tool arguments

        Returns:
            Tool invocation result
        """
        if not self.is_connected or not self._transport:
            raise MCPError(f"Not connected to {self._name}")

        try:
            log.debug(
                "mcp_tool_invoke",
                server=self._name,
                tool=tool_name,
            )

            response = await self._transport.send({
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                },
            })

            result = response.get("result", {})
            content = result.get("content", [])
            is_error = result.get("isError", False)

            # Extract text content
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)

            output = "\n".join(text_parts) if text_parts else str(content)

            if is_error:
                return MCPToolResult.error(output)

            return MCPToolResult.success(output)

        except Exception as e:
            log.error(
                "mcp_tool_error",
                server=self._name,
                tool=tool_name,
                error=str(e),
            )
            return MCPToolResult.error(str(e))

    async def disconnect(self) -> None:
        """Disconnect from server."""
        if self._transport:
            try:
                await self._transport.disconnect()
            except Exception as e:
                log.warning("mcp_disconnect_error", name=self._name, error=str(e))
            finally:
                self._transport = None
                self._status = ConnectionStatus.DISCONNECTED
                log.info("mcp_disconnected", name=self._name)

    def get_tool_def(self, tool_name: str) -> MCPToolDef | None:
        """Get tool definition by name."""
        for tool in self._tools:
            if tool.name == tool_name:
                return tool
        return None
