"""Unit tests for MCP registry and official client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from maos.config.models import MCPServerConfig
from maos.mcp.official_client import MCPToolDefinition, OfficialMCPConnection
from maos.mcp.registry import MCPRegistry, MCPServerConnection


@pytest.mark.unit
class TestMCPToolDefinition:
    """Tests for MCPToolDefinition."""

    def test_creation(self):
        """Test basic MCPToolDefinition creation."""
        tool = MCPToolDefinition(
            name="search",
            description="Search the web",
            input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
            server_name="web-server",
        )
        assert tool.name == "search"
        assert tool.description == "Search the web"
        assert tool.server_name == "web-server"
        assert "q" in tool.input_schema["properties"]

    def test_from_mcp_tool(self):
        """Test creating from an MCP Tool object."""
        mock_tool = MagicMock()
        mock_tool.name = "calc"
        mock_tool.description = "Calculator"
        mock_tool.inputSchema = {"type": "object", "properties": {"expr": {"type": "string"}}}

        defn = MCPToolDefinition.from_mcp_tool(mock_tool, "math-server")
        assert defn.name == "calc"
        assert defn.description == "Calculator"
        assert defn.server_name == "math-server"

    def test_from_mcp_tool_none_description(self):
        """Test creating from MCP Tool with None description."""
        mock_tool = MagicMock()
        mock_tool.name = "tool"
        mock_tool.description = None
        mock_tool.inputSchema = {}

        defn = MCPToolDefinition.from_mcp_tool(mock_tool, "server")
        assert defn.description == ""

    def test_from_mcp_tool_none_schema(self):
        """Test creating from MCP Tool with None inputSchema."""
        mock_tool = MagicMock()
        mock_tool.name = "tool"
        mock_tool.description = "desc"
        mock_tool.inputSchema = None

        defn = MCPToolDefinition.from_mcp_tool(mock_tool, "server")
        assert defn.input_schema == {}


@pytest.mark.unit
class TestMCPServerConnection:
    """Tests for MCPServerConnection."""

    def test_creation(self):
        """Test MCPServerConnection creation."""
        session = MagicMock()
        tools = [
            MCPToolDefinition(name="t1", description="d1", input_schema={}, server_name="s1"),
        ]
        conn = MCPServerConnection("s1", session, tools)
        assert conn.name == "s1"
        assert len(conn.tools) == 1
        assert conn.tools[0].name == "t1"

    async def test_call_tool_returns_text(self):
        """Test call_tool extracts text content."""
        session = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "result text"
        mock_result = MagicMock()
        mock_result.content = [mock_content]
        session.call_tool = AsyncMock(return_value=mock_result)

        conn = MCPServerConnection("s1", session, [])
        result = await conn.call_tool("tool", {"x": 1})
        assert result == "result text"
        session.call_tool.assert_called_once_with("tool", {"x": 1})

    async def test_call_tool_no_text_returns_content_list(self):
        """Test call_tool returns full content list when no text attribute."""
        session = MagicMock()
        mock_content = MagicMock(spec=[])  # No text attribute
        mock_result = MagicMock()
        mock_result.content = [mock_content]
        session.call_tool = AsyncMock(return_value=mock_result)

        conn = MCPServerConnection("s1", session, [])
        result = await conn.call_tool("tool", {})
        assert result == [mock_content]

    async def test_call_tool_empty_content_returns_none(self):
        """Test call_tool returns None when content is empty."""
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.content = []
        session.call_tool = AsyncMock(return_value=mock_result)

        conn = MCPServerConnection("s1", session, [])
        result = await conn.call_tool("tool", {})
        assert result is None


@pytest.mark.unit
class TestMCPRegistry:
    """Tests for MCPRegistry."""

    def test_init_empty(self):
        """Test empty MCPRegistry initialization."""
        registry = MCPRegistry()
        assert len(registry) == 0
        assert registry.list() == []

    async def test_register_stores_config(self):
        """Test register stores the configuration."""
        registry = MCPRegistry()
        config = MCPServerConfig(transport="stdio", command=["python", "-m", "server"])
        await registry.register("test-server", config)

        # After register, config is stored but not connected yet
        assert registry._configs["test-server"] is config

    def test_get_connection_returns_none_before_connect(self):
        """Test get_connection returns None when not connected."""
        registry = MCPRegistry()
        assert registry.get_connection("nonexistent") is None

    def test_contains_before_connect(self):
        """Test __contains__ returns False before connection."""
        registry = MCPRegistry()
        assert "test-server" not in registry

    def test_get_all_tools_empty(self):
        """Test get_all_tools returns empty list with no connections."""
        registry = MCPRegistry()
        assert registry.get_all_tools() == []

    async def test_call_tool_missing_server_raises(self):
        """Test call_tool raises KeyError for non-existent server."""
        registry = MCPRegistry()
        with pytest.raises(KeyError, match="MCP server not connected"):
            await registry.call_tool("nonexistent", "tool", {})

    async def test_disconnect_all_clears_connections(self):
        """Test disconnect_all clears all connections."""
        registry = MCPRegistry()
        # Manually inject a connection to test disconnect
        mock_session = MagicMock()
        tool = MCPToolDefinition(name="t", description="d", input_schema={}, server_name="s")
        registry._connections["s"] = MCPServerConnection("s", mock_session, [tool])

        assert len(registry) == 1
        await registry.disconnect_all()
        assert len(registry) == 0

    def test_get_all_tools_with_connections(self):
        """Test get_all_tools aggregates tools from all connections."""
        registry = MCPRegistry()
        t1 = MCPToolDefinition(name="t1", description="d1", input_schema={}, server_name="s1")
        t2 = MCPToolDefinition(name="t2", description="d2", input_schema={}, server_name="s2")
        mock_session = MagicMock()
        registry._connections["s1"] = MCPServerConnection("s1", mock_session, [t1])
        registry._connections["s2"] = MCPServerConnection("s2", mock_session, [t2])

        tools = registry.get_all_tools()
        assert len(tools) == 2
        assert {t.name for t in tools} == {"t1", "t2"}

    def test_list_returns_connection_names(self):
        """Test list returns names of connected servers."""
        registry = MCPRegistry()
        mock_session = MagicMock()
        registry._connections["s1"] = MCPServerConnection("s1", mock_session, [])
        registry._connections["s2"] = MCPServerConnection("s2", mock_session, [])

        assert set(registry.list()) == {"s1", "s2"}

    def test_contains_with_connection(self):
        """Test __contains__ returns True for connected servers."""
        registry = MCPRegistry()
        mock_session = MagicMock()
        registry._connections["s1"] = MCPServerConnection("s1", mock_session, [])

        assert "s1" in registry
        assert "s2" not in registry

    async def test_call_tool_delegates_to_connection(self):
        """Test call_tool delegates to the correct connection."""
        registry = MCPRegistry()
        mock_session = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "42"
        mock_result = MagicMock()
        mock_result.content = [mock_content]
        mock_session.call_tool = AsyncMock(return_value=mock_result)

        registry._connections["math"] = MCPServerConnection("math", mock_session, [])

        result = await registry.call_tool("math", "add", {"a": 1, "b": 2})
        assert result == "42"
        mock_session.call_tool.assert_called_once_with("add", {"a": 1, "b": 2})


@pytest.mark.unit
class TestOfficialMCPConnection:
    """Tests for OfficialMCPConnection."""

    def test_tools_property(self):
        """Test tools property returns tool list."""
        tools = [
            MCPToolDefinition(name="t1", description="d", input_schema={}, server_name="s"),
        ]
        conn = OfficialMCPConnection("s", MagicMock(), tools)
        assert conn.tools == tools

    def test_get_tool_found(self):
        """Test get_tool returns tool when found."""
        t1 = MCPToolDefinition(name="search", description="d", input_schema={}, server_name="s")
        t2 = MCPToolDefinition(name="calc", description="d", input_schema={}, server_name="s")
        conn = OfficialMCPConnection("s", MagicMock(), [t1, t2])

        result = conn.get_tool("calc")
        assert result is t2

    def test_get_tool_not_found(self):
        """Test get_tool returns None when not found."""
        conn = OfficialMCPConnection("s", MagicMock(), [])
        assert conn.get_tool("nonexistent") is None

    async def test_invoke_tool_returns_text(self):
        """Test invoke_tool returns text content."""
        session = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "hello"
        mock_result = MagicMock()
        mock_result.content = [mock_content]
        session.call_tool = AsyncMock(return_value=mock_result)

        conn = OfficialMCPConnection("s", session, [])
        result = await conn.invoke_tool("greet", {"name": "world"})
        assert result == "hello"

    async def test_invoke_tool_empty_content_returns_none(self):
        """Test invoke_tool returns None when content is empty."""
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.content = []
        session.call_tool = AsyncMock(return_value=mock_result)

        conn = OfficialMCPConnection("s", session, [])
        result = await conn.invoke_tool("tool", {})
        assert result is None

    async def test_invoke_tool_raises_on_error(self):
        """Test invoke_tool wraps exceptions in RuntimeError."""
        session = MagicMock()
        session.call_tool = AsyncMock(side_effect=Exception("connection lost"))

        conn = OfficialMCPConnection("s", session, [])
        with pytest.raises(RuntimeError, match="Tool invocation failed"):
            await conn.invoke_tool("tool", {})
