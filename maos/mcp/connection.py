"""
MAOS MCP Connection.

Uses the official MCP SDK for server communication.
"""

from enum import Enum
from typing import Any

import structlog
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client

from maos.config.models import MCPServerConfig
from maos.config.models import MCPTransport as MCPTransportType
from maos.errors import MCPConnectionError, MCPError
from maos.mcp.models import MCPToolDef, MCPToolResult

log = structlog.get_logger()


class ConnectionStatus(str, Enum):
    """MCP connection status."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class MCPConnection:
    """Connection to a single MCP server using official MCP SDK."""

    def __init__(self, name: str, config: MCPServerConfig):
        self._name = name
        self._config = config
        self._session: ClientSession | None = None
        self._status = ConnectionStatus.DISCONNECTED
        self._tools: list[MCPToolDef] = []
        self._error: str | None = None
        self._context_stack: list[Any] = []

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
        """Establish connection using official MCP SDK."""
        if self._status == ConnectionStatus.CONNECTED:
            return

        self._status = ConnectionStatus.CONNECTING

        try:
            if self._config.transport == MCPTransportType.STDIO:
                await self._connect_stdio()
            elif self._config.transport in (MCPTransportType.HTTP, MCPTransportType.SSE):
                await self._connect_sse()
            else:
                raise MCPError(f"Unsupported transport: {self._config.transport}")

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
            raise MCPConnectionError(f"Failed to connect to {self._name}: {e}") from e

    async def _connect_stdio(self) -> None:
        """Connect via stdio using official MCP SDK."""
        if not self._config.command:
            raise MCPError("Command required for stdio transport")

        log.debug("mcp_stdio_connect", command=self._config.command)

        server_params = StdioServerParameters(
            command=self._config.command[0],
            args=self._config.command[1:] if len(self._config.command) > 1 else [],
            env=self._config.env,
        )

        # Create the context manager but manage it manually
        client_cm = stdio_client(server_params)
        streams = await client_cm.__aenter__()
        self._context_stack.append(client_cm)

        # Create and initialize session
        session_cm = ClientSession(*streams)
        self._session = await session_cm.__aenter__()
        self._context_stack.append(session_cm)

        # Initialize the session
        await self._session.initialize()

    async def _connect_sse(self) -> None:
        """Connect via SSE using official MCP SDK."""
        if not self._config.url:
            raise MCPError("URL required for SSE transport")

        log.debug("mcp_sse_connect", url=self._config.url)

        # Create the context manager but manage it manually
        client_cm = sse_client(self._config.url)
        streams = await client_cm.__aenter__()
        self._context_stack.append(client_cm)

        # Create and initialize session
        session_cm = ClientSession(*streams)
        self._session = await session_cm.__aenter__()
        self._context_stack.append(session_cm)

        # Initialize the session
        await self._session.initialize()

    async def _fetch_tools(self) -> None:
        """Fetch available tools from server."""
        if not self._session:
            return

        result = await self._session.list_tools()

        self._tools = [
            MCPToolDef(
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema if hasattr(tool, "inputSchema") else {},
            )
            for tool in result.tools
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
        if not self.is_connected or not self._session:
            raise MCPError(f"Not connected to {self._name}")

        try:
            log.debug(
                "mcp_tool_invoke",
                server=self._name,
                tool=tool_name,
            )

            result = await self._session.call_tool(tool_name, arguments)

            # Extract text content from result
            text_parts = []
            for item in result.content:
                if hasattr(item, "text"):
                    text_parts.append(item.text)
                elif hasattr(item, "data"):
                    text_parts.append(str(item.data))

            output = "\n".join(text_parts) if text_parts else str(result.content)

            if result.isError:
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
        # Exit context managers in reverse order
        while self._context_stack:
            cm = self._context_stack.pop()
            try:
                await cm.__aexit__(None, None, None)
            except Exception as e:
                log.warning("mcp_disconnect_error", name=self._name, error=str(e))

        self._session = None
        self._status = ConnectionStatus.DISCONNECTED
        log.info("mcp_disconnected", name=self._name)

    def get_tool_def(self, tool_name: str) -> MCPToolDef | None:
        """Get tool definition by name."""
        for tool in self._tools:
            if tool.name == tool_name:
                return tool
        return None
