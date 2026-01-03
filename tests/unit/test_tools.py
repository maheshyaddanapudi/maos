"""
Unit tests for tools module.
"""


import pytest

from maos.mcp.registry import MCPRegistry
from maos.tools.models import Tool, ToolCall, ToolResult
from maos.tools.registry import ToolRegistry
from tests.mocks.mcp import MockMCPConnection, MockMCPServer


class TestToolModels:
    """Tests for tool models."""

    def test_tool_call(self):
        tc = ToolCall(
            id="tc1",
            name="search",
            arguments={"query": "test"},
        )
        assert tc.id == "tc1"
        assert tc.name == "search"
        assert tc.arguments["query"] == "test"

    def test_tool_result_success(self):
        result = ToolResult.success_result(
            tool_id="tc1",
            tool_name="search",
            output="Search results...",
        )
        assert result.tool_id == "tc1"
        assert result.success
        assert result.output == "Search results..."
        assert result.error is None

    def test_tool_result_error(self):
        result = ToolResult.error_result(
            tool_id="tc1",
            tool_name="search",
            error="Tool failed",
        )
        assert result.tool_id == "tc1"
        assert not result.success
        assert result.error == "Tool failed"

    def test_tool_definition(self):
        tool = Tool(
            id="search_web",
            name="search.web",
            description="Search the web",
            server="tools",
            mcp_tool_name="search.web",
            input_schema={"type": "object"},
            timeout_seconds=30,
        )
        assert tool.id == "search_web"
        assert tool.server == "tools"


class TestMockMCPServer:
    """Tests for MockMCPServer."""

    def test_add_tool(self):
        server = MockMCPServer()
        server.add_tool("search", "Search the web", {"type": "object"})

        tools = server.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "search"

    @pytest.mark.asyncio
    async def test_call_tool_default(self):
        server = MockMCPServer()
        server.add_tool("search", "Search")

        result = await server.call_tool("search", {"q": "test"})

        assert not result.is_error
        assert "search" in str(result.content)

    @pytest.mark.asyncio
    async def test_call_tool_with_set_result(self):
        server = MockMCPServer()
        server.add_tool("search", "Search")
        server.set_tool_result("search", "Custom result")

        result = await server.call_tool("search", {})

        assert result.content == "Custom result"

    @pytest.mark.asyncio
    async def test_call_tool_with_callable(self):
        server = MockMCPServer()
        server.add_tool("echo", "Echo input")
        server.set_tool_result("echo", lambda args: args.get("text", ""))

        result = await server.call_tool("echo", {"text": "hello"})

        assert result.content == "hello"

    def test_assert_tool_called(self):
        server = MockMCPServer()

        with pytest.raises(AssertionError):
            server.assert_tool_called("search")


class TestMockMCPConnection:
    """Tests for MockMCPConnection."""

    def test_properties(self):
        conn = MockMCPConnection(name="test")
        assert conn.name == "test"
        assert conn.is_connected

    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        conn = MockMCPConnection()

        await conn.disconnect()
        assert not conn.is_connected

        await conn.connect()
        assert conn.is_connected

    @pytest.mark.asyncio
    async def test_invoke_tool(self):
        server = MockMCPServer()
        server.add_tool("test", "Test tool")
        server.set_tool_result("test", "Result")

        conn = MockMCPConnection(name="mock", server=server)
        result = await conn.invoke_tool("test", {})

        assert result.content == "Result"

    def test_get_tool_def(self):
        server = MockMCPServer()
        server.add_tool("search", "Search", {"type": "object"})

        conn = MockMCPConnection(server=server)
        tool_def = conn.get_tool_def("search")

        assert tool_def is not None
        assert tool_def.name == "search"

    def test_get_tool_def_not_found(self):
        conn = MockMCPConnection()
        assert conn.get_tool_def("nonexistent") is None


class TestToolRegistry:
    """Tests for ToolRegistry."""

    @pytest.fixture
    def mcp_registry(self):
        """Create an MCP registry (empty)."""
        return MCPRegistry()

    def test_list_tools_empty(self, mcp_registry):
        registry = ToolRegistry(mcp_registry)
        # Empty registry initially
        assert registry.list_all() == []

    def test_get_nonexistent(self, mcp_registry):
        registry = ToolRegistry(mcp_registry)
        assert registry.get("nonexistent") is None
