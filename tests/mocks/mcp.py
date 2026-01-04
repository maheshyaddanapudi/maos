"""
Mock MCP Server and Connection for Testing.
"""

from collections.abc import Callable
from typing import Any

from maos.mcp.connection import ConnectionStatus
from maos.mcp.models import MCPToolDef, MCPToolResult


class MockMCPServer:
    """Mock MCP server for testing."""

    def __init__(self, tools: list[dict[str, Any]] | None = None):
        self._tools = [
            MCPToolDef(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("input_schema", {}),
            )
            for t in (tools or [])
        ]
        self._tool_results: dict[str, Any] = {}
        self._calls: list[dict] = []

    def add_tool(
        self,
        name: str,
        description: str = "",
        input_schema: dict | None = None,
    ) -> None:
        """Add a tool to the server."""
        self._tools.append(MCPToolDef(
            name=name,
            description=description,
            input_schema=input_schema or {},
        ))

    def set_tool_result(
        self,
        tool_name: str,
        result: Any | Callable[[dict], Any],
    ) -> None:
        """Set result for a tool call."""
        self._tool_results[tool_name] = result

    def get_tools(self) -> list[MCPToolDef]:
        """Return tool definitions."""
        return self._tools

    async def call_tool(self, name: str, arguments: dict) -> MCPToolResult:
        """Call a tool and return result."""
        self._calls.append({"name": name, "arguments": arguments})

        if name in self._tool_results:
            result = self._tool_results[name]
            if callable(result):
                return MCPToolResult.success(result(arguments))
            return MCPToolResult.success(result)

        return MCPToolResult.success(f"Mock result for {name}")

    def get_calls(self) -> list[dict]:
        """Get recorded tool calls."""
        return self._calls

    def assert_tool_called(self, name: str, **expected_args) -> None:
        """Assert tool was called with expected arguments."""
        matching = [c for c in self._calls if c["name"] == name]
        assert matching, f"Tool {name} was not called"
        if expected_args:
            assert matching[-1]["arguments"] == expected_args


class MockMCPConnection:
    """Mock MCP connection for testing."""

    def __init__(
        self,
        name: str = "mock",
        server: MockMCPServer | None = None,
    ):
        self._name = name
        self._server = server or MockMCPServer()
        self._status = ConnectionStatus.CONNECTED

    @property
    def name(self) -> str:
        return self._name

    @property
    def status(self) -> ConnectionStatus:
        return self._status

    @property
    def tools(self) -> list[MCPToolDef]:
        return self._server.get_tools()

    @property
    def is_connected(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    async def connect(self) -> None:
        """Mock connect."""
        self._status = ConnectionStatus.CONNECTED

    async def disconnect(self) -> None:
        """Mock disconnect."""
        self._status = ConnectionStatus.DISCONNECTED

    async def invoke_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> MCPToolResult:
        """Invoke tool on mock server."""
        return await self._server.call_tool(tool_name, arguments)

    def get_tool_def(self, tool_name: str) -> MCPToolDef | None:
        """Get tool definition by name."""
        for tool in self._server.get_tools():
            if tool.name == tool_name:
                return tool
        return None
