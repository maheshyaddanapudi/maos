"""Mock MCP components for testing."""

from typing import Any, Dict, List, Optional

from maos.mcp.transports.base import MCPTransport


class MockMCPTransport(MCPTransport):
    """Mock MCP transport for testing."""

    def __init__(
        self,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_results: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the mock transport.

        Args:
            tools: List of tool definitions to return.
            tool_results: Dict mapping tool names to results.
        """
        self._tools = tools or []
        self._tool_results = tool_results or {}
        self._connected = False
        self._call_history: List[Dict[str, Any]] = []

    async def connect(self) -> None:
        """Simulate connection."""
        self._connected = True

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    async def send_request(self, method: str, params: Dict[str, Any]) -> Any:
        """Handle mock requests."""
        self._call_history.append({
            "method": method,
            "params": params
        })

        if method == "tools/list":
            return {"tools": self._tools}

        elif method == "tools/call":
            tool_name = params.get("name", "")
            if tool_name in self._tool_results:
                return {"content": [{"text": str(self._tool_results[tool_name])}]}
            return {"content": [{"text": "Mock tool result"}]}

        return {}

    @property
    def call_history(self) -> List[Dict[str, Any]]:
        """Get call history."""
        return self._call_history

    def reset(self) -> None:
        """Reset mock state."""
        self._call_history = []


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
    def server_name(self) -> str:
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

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        return self._tools

    async def invoke_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Invoke a tool."""
        self._invoke_history.append({
            "name": name,
            "arguments": arguments
        })
        return {"result": f"Mock result from {name}"}

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

    def get(self, name: str) -> Optional[MockMCPConnection]:
        """Get a connection by name."""
        return self._connections.get(name)

    def list_servers(self) -> List[str]:
        """List all server names."""
        return list(self._connections.keys())

    def is_connected(self, name: str) -> bool:
        """Check if a server is connected."""
        conn = self._connections.get(name)
        return conn.is_connected if conn else False

    async def disconnect_all(self) -> None:
        """Disconnect all servers."""
        for conn in self._connections.values():
            await conn.disconnect()
