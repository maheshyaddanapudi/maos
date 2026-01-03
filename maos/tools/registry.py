"""
MAOS Tool Registry.

Manages tool materialization from MCP servers.
"""

import asyncio
from typing import Any

import structlog

from maos.config.models import ToolConfig
from maos.errors import ToolError
from maos.mcp.registry import MCPRegistry
from maos.tools.models import Tool, ToolResult

log = structlog.get_logger()


class ToolRegistry:
    """Registry of materialized tools."""

    def __init__(self, mcp_registry: MCPRegistry):
        self._mcp_registry = mcp_registry
        self._tools: dict[str, Tool] = {}

    async def materialize(self, tool_configs: dict[str, ToolConfig]) -> None:
        """Materialize tools from configuration.

        For each tool config:
        1. Get connection from MCP registry
        2. Verify tool exists on server
        3. Create Tool object with invocation handle

        Args:
            tool_configs: Dictionary of tool configurations keyed by ID
        """
        if not tool_configs:
            log.info("no_tools_configured")
            return

        log.info("materializing_tools", count=len(tool_configs))

        for tool_id, config in tool_configs.items():
            await self._materialize_tool(tool_id, config)

        log.info("tools_materialized", count=len(self._tools))

    async def _materialize_tool(self, tool_id: str, config: ToolConfig) -> None:
        """Materialize a single tool."""
        try:
            # Get MCP connection
            connection = self._mcp_registry.get_connection(config.server)
            if connection is None:
                log.warning(
                    "tool_server_not_found",
                    tool_id=tool_id,
                    server=config.server,
                )
                return

            if not connection.is_connected:
                log.warning(
                    "tool_server_not_connected",
                    tool_id=tool_id,
                    server=config.server,
                )
                return

            # Get tool definition from server
            tool_def = connection.get_tool_def(config.tool_name)
            if tool_def is None:
                log.warning(
                    "tool_not_found_on_server",
                    tool_id=tool_id,
                    tool_name=config.tool_name,
                    server=config.server,
                )
                return

            # Create tool with invocation handle
            timeout = config.timeout_seconds or 30

            # Create invoke function bound to this connection
            async def invoke(args: dict[str, Any], conn=connection, name=config.tool_name) -> Any:
                result = await conn.invoke_tool(name, args)
                if result.is_error:
                    raise ToolError(result.error_message or "Tool execution failed")
                return result.content

            tool = Tool(
                id=tool_id,
                name=tool_def.name,
                description=config.description_override or tool_def.description,
                server=config.server,
                mcp_tool_name=config.tool_name,
                input_schema=tool_def.input_schema,
                timeout_seconds=timeout,
                invoke_func=invoke,
            )

            self._tools[tool_id] = tool
            log.debug("tool_materialized", tool_id=tool_id, server=config.server)

        except Exception as e:
            log.error(
                "tool_materialization_failed",
                tool_id=tool_id,
                error=str(e),
            )

    async def invoke_tool(
        self,
        tool_id: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Invoke a tool by ID.

        Args:
            tool_id: Tool ID
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        import time

        tool = self.get(tool_id)
        if tool is None:
            return ToolResult.error_result(tool_id, tool_id, f"Tool not found: {tool_id}")

        start_time = time.time()

        try:
            # Execute with timeout
            output = await asyncio.wait_for(
                tool.call(arguments),
                timeout=tool.timeout_seconds,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            return ToolResult.success_result(
                tool_id=tool_id,
                tool_name=tool.name,
                output=output,
                duration_ms=duration_ms,
            )

        except TimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolResult.error_result(
                tool_id=tool_id,
                tool_name=tool.name,
                error=f"Tool execution timed out after {tool.timeout_seconds}s",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolResult.error_result(
                tool_id=tool_id,
                tool_name=tool.name,
                error=str(e),
                duration_ms=duration_ms,
            )

    def get(self, tool_id: str) -> Tool | None:
        """Get tool by ID.

        Args:
            tool_id: Tool ID

        Returns:
            Tool or None if not found
        """
        return self._tools.get(tool_id)

    def get_or_raise(self, tool_id: str) -> Tool:
        """Get tool by ID or raise error.

        Args:
            tool_id: Tool ID

        Returns:
            Tool

        Raises:
            ToolError: If tool not found
        """
        tool = self.get(tool_id)
        if tool is None:
            raise ToolError(f"Tool not found: {tool_id}")
        return tool

    def list_all(self) -> list[Tool]:
        """List all registered tools.

        Returns:
            List of tools
        """
        return list(self._tools.values())

    def list_ids(self) -> list[str]:
        """List all tool IDs.

        Returns:
            List of tool IDs
        """
        return list(self._tools.keys())

    def list_by_server(self, server: str) -> list[Tool]:
        """List tools from specific server.

        Args:
            server: Server name

        Returns:
            List of tools from that server
        """
        return [t for t in self._tools.values() if t.server == server]

    def get_tools_by_ids(self, tool_ids: list[str]) -> list[Tool]:
        """Get multiple tools by IDs.

        Args:
            tool_ids: List of tool IDs

        Returns:
            List of found tools
        """
        return [self._tools[tid] for tid in tool_ids if tid in self._tools]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, tool_id: str) -> bool:
        return tool_id in self._tools
