"""Mock MCP components for testing."""

from typing import Any, Dict, List, Optional


class MockMCPConnection:
    """Mock MCP connection for testing."""

    def __init__(
        self,
        server_name: str = "mock-server",
        tools: Optional[List[Dict[str, Any]]] = None
    ):
        """
        Initialize mock connection.

        Args:
            server_name: Name of the mock server.
            tools: List of tools to expose.
        """
        self._server_name = server_name
        self._tools = tools or [
            {
                "name": "mock_tool",
                "description": "A mock tool",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string"}
                    }
                }
            }
        ]
        self._connected = False
        self._invoke_history: List[Dict[str, Any]] = []

    @property
    def name(self) -> str:
        """Get server name."""
        return self._server_name

    @property
    def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected

    async def connect(self) -> None:
        """Connect to mock server."""
        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from mock server."""
        self._connected = False

    def get_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        return self._tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool."""
        self._invoke_history.append({
            "name": name,
            "arguments": arguments
        })
        return f"Mock result from {name}"

    @property
    def invoke_history(self) -> List[Dict[str, Any]]:
        """Get tool invocation history."""
        return self._invoke_history

    def reset(self) -> None:
        """Reset mock state."""
        self._invoke_history = []


class MockMCPRegistry:
    """Mock MCP registry for testing."""

    def __init__(self):
        """Initialize mock registry."""
        self._connections: Dict[str, MockMCPConnection] = {}

    async def register(self, name: str, config: Any) -> None:
        """Register a mock connection."""
        self._connections[name] = MockMCPConnection(server_name=name)
        await self._connections[name].connect()

    def get_connection(self, name: str) -> Optional[MockMCPConnection]:
        """Get a connection by name."""
        return self._connections.get(name)

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all tools from all servers."""
        tools = []
        for conn in self._connections.values():
            tools.extend(conn.get_tools())
        return tools

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """Call a tool on a server."""
        conn = self._connections.get(server_name)
        if not conn:
            raise KeyError(f"Server not found: {server_name}")
        return await conn.call_tool(tool_name, arguments)

    def list(self) -> List[str]:
        """List all server names."""
        return list(self._connections.keys())

    async def disconnect_all(self) -> None:
        """Disconnect all servers."""
        for conn in self._connections.values():
            await conn.disconnect()
        self._connections.clear()

    def __contains__(self, name: str) -> bool:
        """Check if a server is registered."""
        return name in self._connections

    def __len__(self) -> int:
        """Get number of registered servers."""
        return len(self._connections)
