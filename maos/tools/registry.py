"""Tool registry for materializing tools from MCP servers."""

from typing import Dict, List, Optional

import structlog

from maos.config.models import ToolConfig
from maos.mcp.registry import MCPRegistry
from maos.tools.models import Tool, JsonSchema

logger = structlog.get_logger()


class ToolRegistry:
    """Registry of materialized tools."""

    def __init__(self, mcp_registry: MCPRegistry):
        """
        Initialize the tool registry.

        Args:
            mcp_registry: MCP registry for server connections.
        """
        self._mcp_registry = mcp_registry
        self._tools: Dict[str, Tool] = {}

    async def materialize(self, tool_configs: Dict[str, ToolConfig]) -> None:
        """
        Materialize tools from configuration.

        Args:
            tool_configs: Tool configurations keyed by tool ID.
        """
        for tool_id, config in tool_configs.items():
            try:
                await self._materialize_tool(tool_id, config)
            except Exception as e:
                logger.warning(
                    "failed_to_materialize_tool",
                    tool_id=tool_id,
                    error=str(e)
                )

    async def _materialize_tool(
        self,
        tool_id: str,
        config: ToolConfig
    ) -> Tool:
        """Materialize a single tool."""
        # Get MCP connection
        connection = self._mcp_registry.get_connection(config.server)
        if connection is None:
            raise ValueError(f"MCP server not connected: {config.server}")

        # Find tool definition on server
        mcp_tool = None
        for t in connection.tools:
            if t.name == config.tool_name:
                mcp_tool = t
                break

        if mcp_tool is None:
            raise ValueError(
                f"Tool '{config.tool_name}' not found on server '{config.server}'"
            )

        # Create tool with invoke function bound to connection
        tool = Tool(
            id=tool_id,
            name=config.tool_name,
            description=config.description_override or mcp_tool.description,
            server=config.server,
            mcp_tool_name=config.tool_name,
            input_schema=JsonSchema(**mcp_tool.input_schema) if mcp_tool.input_schema else JsonSchema(),
            timeout_seconds=config.timeout_seconds or 30
        )

        # Bind the invoke function
        async def invoke(args: Dict, conn=connection, tool_name=config.tool_name):
            return await conn.call_tool(tool_name, args)

        tool.set_invoke_fn(invoke)

        self._tools[tool_id] = tool
        logger.debug("materialized_tool", tool_id=tool_id, server=config.server)

        return tool

    def register(self, tool: Tool) -> None:
        """
        Register a pre-created tool.

        Args:
            tool: Tool to register.
        """
        self._tools[tool.id] = tool

    def get(self, tool_id: str) -> Optional[Tool]:
        """
        Get a tool by ID.

        Args:
            tool_id: Tool identifier.

        Returns:
            Tool if found.
        """
        return self._tools.get(tool_id)

    def get_or_raise(self, tool_id: str) -> Tool:
        """
        Get a tool by ID, raising if not found.

        Args:
            tool_id: Tool identifier.

        Returns:
            Tool.

        Raises:
            KeyError: If tool not found.
        """
        tool = self._tools.get(tool_id)
        if tool is None:
            raise KeyError(f"Tool not found: {tool_id}")
        return tool

    def list_all(self) -> List[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

    def list_by_server(self, server: str) -> List[Tool]:
        """List tools from a specific MCP server."""
        return [t for t in self._tools.values() if t.server == server]

    def list_ids(self) -> List[str]:
        """List all tool IDs."""
        return list(self._tools.keys())

    def __contains__(self, tool_id: str) -> bool:
        """Check if a tool is registered."""
        return tool_id in self._tools

    def __len__(self) -> int:
        """Get number of registered tools."""
        return len(self._tools)
