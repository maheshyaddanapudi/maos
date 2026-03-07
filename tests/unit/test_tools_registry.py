"""Unit tests for tools registry and models."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from maos.config.models import ToolConfig
from maos.tools.models import JsonSchema, Tool, ToolCall, ToolResult
from maos.tools.registry import ToolRegistry


@pytest.mark.unit
class TestJsonSchema:
    """Tests for JsonSchema model."""

    def test_default_schema(self):
        """Test default JSON schema has object type."""
        schema = JsonSchema()
        assert schema.type == "object"
        assert schema.properties == {}
        assert schema.required == []
        assert schema.description is None

    def test_custom_schema(self):
        """Test JSON schema with custom properties."""
        schema = JsonSchema(
            type="object",
            properties={"name": {"type": "string"}, "age": {"type": "integer"}},
            required=["name"],
            description="A person schema",
        )
        assert len(schema.properties) == 2
        assert schema.required == ["name"]
        assert schema.description == "A person schema"


@pytest.mark.unit
class TestTool:
    """Tests for Tool model."""

    def _make_tool(self, **kwargs) -> Tool:
        """Create a tool with sensible defaults."""
        defaults = {
            "id": "test_tool",
            "name": "test_tool",
            "description": "A test tool",
            "server": "test-server",
            "mcp_tool_name": "test_tool",
        }
        defaults.update(kwargs)
        return Tool(**defaults)

    def test_tool_creation(self):
        """Test basic tool creation."""
        tool = self._make_tool()
        assert tool.id == "test_tool"
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.server == "test-server"
        assert tool.timeout_seconds == 30

    def test_tool_default_schema(self):
        """Test tool has default empty JSON schema."""
        tool = self._make_tool()
        assert tool.input_schema.type == "object"
        assert tool.input_schema.properties == {}

    def test_tool_custom_timeout(self):
        """Test tool with custom timeout."""
        tool = self._make_tool(timeout_seconds=120)
        assert tool.timeout_seconds == 120

    async def test_tool_call_with_invoke_fn(self):
        """Test calling a tool with a bound invoke function."""
        tool = self._make_tool()
        mock_fn = AsyncMock(return_value={"result": "success"})
        tool.set_invoke_fn(mock_fn)

        result = await tool.call({"input": "test"})

        assert result == {"result": "success"}
        mock_fn.assert_called_once_with({"input": "test"})

    async def test_tool_call_without_invoke_fn_raises(self):
        """Test calling a tool without an invoke function raises RuntimeError."""
        tool = self._make_tool()

        with pytest.raises(RuntimeError, match="not connected"):
            await tool.call({"input": "test"})

    def test_tool_to_llm_definition(self):
        """Test converting tool to LLM definition format."""
        schema = JsonSchema(
            type="object",
            properties={"query": {"type": "string"}},
            required=["query"],
        )
        tool = self._make_tool(input_schema=schema)

        defn = tool.to_llm_definition()

        assert defn["name"] == "test_tool"
        assert defn["description"] == "A test tool"
        assert defn["parameters"]["type"] == "object"
        assert "query" in defn["parameters"]["properties"]
        assert defn["parameters"]["required"] == ["query"]


@pytest.mark.unit
class TestToolCallAndResult:
    """Tests for ToolCall and ToolResult models."""

    def test_tool_call_creation(self):
        """Test ToolCall model creation."""
        tc = ToolCall(id="call_1", tool_id="my_tool", arguments={"x": 1})
        assert tc.id == "call_1"
        assert tc.tool_id == "my_tool"
        assert tc.arguments == {"x": 1}

    def test_tool_result_success(self):
        """Test successful ToolResult."""
        result = ToolResult(
            tool_id="my_tool",
            tool_name="My Tool",
            input_args={"x": 1},
            output="done",
            success=True,
            duration_ms=42,
        )
        assert result.success is True
        assert result.error_message is None
        assert result.duration_ms == 42

    def test_tool_result_failure(self):
        """Test failed ToolResult."""
        result = ToolResult(
            tool_id="my_tool",
            tool_name="My Tool",
            input_args={},
            output=None,
            success=False,
            error_message="Timeout",
        )
        assert result.success is False
        assert result.error_message == "Timeout"


@pytest.mark.unit
class TestToolRegistry:
    """Tests for ToolRegistry."""

    def _make_mcp_tool(self, name="remote_tool", description="A remote tool", input_schema=None):
        """Create a mock MCP tool. Uses a SimpleNamespace to avoid MagicMock's name issue."""
        from types import SimpleNamespace

        return SimpleNamespace(
            name=name,
            description=description,
            input_schema=input_schema
            or {"type": "object", "properties": {"q": {"type": "string"}}},
        )

    def _make_mcp_registry(self, tools=None):
        """Create a mock MCP registry with tool definitions."""
        mcp_registry = MagicMock()
        connection = MagicMock()
        mock_tools = tools if tools is not None else [self._make_mcp_tool()]
        connection.tools = mock_tools
        connection.call_tool = AsyncMock(return_value="tool result")
        mcp_registry.get_connection.return_value = connection
        return mcp_registry

    def test_init_empty(self):
        """Test empty registry initialization."""
        mcp_registry = MagicMock()
        registry = ToolRegistry(mcp_registry)
        assert len(registry) == 0
        assert registry.list_all() == []
        assert registry.list_ids() == []

    def test_register_tool(self):
        """Test registering a pre-created tool."""
        mcp_registry = MagicMock()
        registry = ToolRegistry(mcp_registry)

        tool = Tool(
            id="t1",
            name="tool_one",
            description="Tool one",
            server="s1",
            mcp_tool_name="tool_one",
        )
        registry.register(tool)

        assert len(registry) == 1
        assert "t1" in registry
        assert registry.get("t1") is tool

    def test_get_returns_none_for_missing(self):
        """Test get returns None for non-existent tool."""
        registry = ToolRegistry(MagicMock())
        assert registry.get("nonexistent") is None

    def test_get_or_raise_raises_for_missing(self):
        """Test get_or_raise raises KeyError for non-existent tool."""
        registry = ToolRegistry(MagicMock())
        with pytest.raises(KeyError, match="Tool not found"):
            registry.get_or_raise("nonexistent")

    def test_get_or_raise_returns_tool(self):
        """Test get_or_raise returns tool when it exists."""
        registry = ToolRegistry(MagicMock())
        tool = Tool(id="t1", name="t1", description="d", server="s", mcp_tool_name="t1")
        registry.register(tool)
        assert registry.get_or_raise("t1") is tool

    def test_list_all(self):
        """Test listing all tools."""
        registry = ToolRegistry(MagicMock())
        for i in range(3):
            tool = Tool(
                id=f"t{i}",
                name=f"tool_{i}",
                description="d",
                server="s",
                mcp_tool_name=f"tool_{i}",
            )
            registry.register(tool)

        assert len(registry.list_all()) == 3
        assert set(registry.list_ids()) == {"t0", "t1", "t2"}

    def test_list_by_server(self):
        """Test listing tools by server name."""
        registry = ToolRegistry(MagicMock())
        for i, server in enumerate(["s1", "s1", "s2"]):
            tool = Tool(
                id=f"t{i}",
                name=f"tool_{i}",
                description="d",
                server=server,
                mcp_tool_name=f"tool_{i}",
            )
            registry.register(tool)

        s1_tools = registry.list_by_server("s1")
        assert len(s1_tools) == 2
        s2_tools = registry.list_by_server("s2")
        assert len(s2_tools) == 1
        assert registry.list_by_server("nonexistent") == []

    def test_contains(self):
        """Test __contains__ operator."""
        registry = ToolRegistry(MagicMock())
        tool = Tool(id="t1", name="t1", description="d", server="s", mcp_tool_name="t1")
        registry.register(tool)
        assert "t1" in registry
        assert "t999" not in registry

    async def test_materialize_with_mcp(self):
        """Test materializing tools from MCP server."""
        mcp_registry = self._make_mcp_registry()
        registry = ToolRegistry(mcp_registry)

        tool_configs = {
            "my_tool": ToolConfig(server="test-server", tool_name="remote_tool"),
        }
        await registry.materialize(tool_configs)

        assert len(registry) == 1
        assert "my_tool" in registry
        tool = registry.get("my_tool")
        assert tool.name == "remote_tool"
        assert tool.server == "test-server"

    async def test_materialize_missing_server_warns(self):
        """Test materializing a tool from a missing server warns and continues."""
        mcp_registry = MagicMock()
        mcp_registry.get_connection.return_value = None
        registry = ToolRegistry(mcp_registry)

        tool_configs = {
            "my_tool": ToolConfig(server="no-server", tool_name="remote_tool"),
        }
        await registry.materialize(tool_configs)

        # Tool should not be registered since server is missing
        assert len(registry) == 0

    async def test_materialize_missing_tool_on_server_warns(self):
        """Test materializing a tool that doesn't exist on the server warns."""
        mcp_registry = self._make_mcp_registry(tools=[])
        registry = ToolRegistry(mcp_registry)

        tool_configs = {
            "my_tool": ToolConfig(server="test-server", tool_name="nonexistent"),
        }
        await registry.materialize(tool_configs)

        assert len(registry) == 0

    async def test_materialize_uses_description_override(self):
        """Test that description_override takes precedence over MCP description."""
        mcp_registry = self._make_mcp_registry()
        registry = ToolRegistry(mcp_registry)

        tool_configs = {
            "my_tool": ToolConfig(
                server="test-server",
                tool_name="remote_tool",
                description_override="Custom description",
            ),
        }
        await registry.materialize(tool_configs)

        tool = registry.get("my_tool")
        assert tool.description == "Custom description"

    async def test_materialized_tool_is_callable(self):
        """Test that a materialized tool can be called."""
        mcp_registry = self._make_mcp_registry()
        registry = ToolRegistry(mcp_registry)

        tool_configs = {
            "my_tool": ToolConfig(server="test-server", tool_name="remote_tool"),
        }
        await registry.materialize(tool_configs)

        tool = registry.get("my_tool")
        result = await tool.call({"q": "test"})
        assert result == "tool result"
