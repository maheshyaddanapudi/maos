"""MCP connection management."""

from typing import Any, Dict, List, Optional

from maos.config.models import MCPServerConfig
from maos.mcp.transports.base import MCPTransport
from maos.mcp.transports.stdio import StdioTransport
from maos.mcp.transports.http import HTTPTransport, SSETransport


class MCPToolDefinition:
    """Definition of a tool from an MCP server."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        server_name: str
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.server_name = server_name


class MCPConnection:
    """Connection to a single MCP server."""

    def __init__(self, name: str, transport: MCPTransport):
        """
        Initialize MCP connection.

        Args:
            name: Server name.
            transport: Transport to use.
        """
        self.name = name
        self._transport = transport
        self._tools: List[MCPToolDefinition] = []
        self._connected = False

    @classmethod
    async def create(cls, name: str, config: MCPServerConfig) -> "MCPConnection":
        """
        Create and connect to an MCP server.

        Args:
            name: Server name.
            config: Server configuration.

        Returns:
            Connected MCPConnection.
        """
        # Create appropriate transport
        if config.transport == "stdio":
            if not config.command:
                raise ValueError(f"MCP server '{name}' with stdio transport requires 'command'")
            transport = StdioTransport(
                command=config.command,
                env=config.env,
                timeout=config.timeout_seconds
            )
        elif config.transport == "http":
            if not config.url:
                raise ValueError(f"MCP server '{name}' with http transport requires 'url'")
            transport = HTTPTransport(
                url=config.url,
                timeout=config.timeout_seconds
            )
        elif config.transport == "sse":
            if not config.url:
                raise ValueError(f"MCP server '{name}' with sse transport requires 'url'")
            transport = SSETransport(
                url=config.url,
                timeout=config.timeout_seconds
            )
        else:
            raise ValueError(f"Unknown transport type: {config.transport}")

        connection = cls(name, transport)
        await connection.connect()
        return connection

    async def connect(self) -> None:
        """Establish connection and fetch tools."""
        await self._transport.connect()
        self._connected = True

        # Fetch available tools
        await self._refresh_tools()

    async def disconnect(self) -> None:
        """Disconnect from the server."""
        await self._transport.disconnect()
        self._connected = False
        self._tools = []

    async def _refresh_tools(self) -> None:
        """Fetch tool list from server."""
        response = await self._send_request("tools/list", {})

        if "error" in response:
            raise RuntimeError(f"Failed to list tools: {response['error']}")

        tools_data = response.get("result", {}).get("tools", [])
        self._tools = [
            MCPToolDefinition(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
                server_name=self.name
            )
            for t in tools_data
        ]

    async def invoke_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """
        Invoke a tool on this server.

        Args:
            tool_name: Name of the tool.
            arguments: Tool arguments.

        Returns:
            Tool result.
        """
        response = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })

        if "error" in response:
            error = response["error"]
            raise RuntimeError(f"Tool call failed: {error.get('message', error)}")

        result = response.get("result", {})

        # Extract content from MCP response format
        content = result.get("content", [])
        if content and len(content) > 0:
            first_content = content[0]
            if first_content.get("type") == "text":
                return first_content.get("text", "")
            return first_content

        return result

    async def _send_request(
        self,
        method: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send a JSON-RPC request."""
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        return await self._transport.send(message)

    @property
    def tools(self) -> List[MCPToolDefinition]:
        """Get list of available tools."""
        return self._tools

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected and self._transport.is_connected

    def get_tool(self, name: str) -> Optional[MCPToolDefinition]:
        """Get a tool by name."""
        for tool in self._tools:
            if tool.name == name:
                return tool
        return None
