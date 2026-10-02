#!/usr/bin/env python3
"""
Simple MCP server for testing MAOS tool integration.

Provides:
- get_current_time: Get current date/time
- calculate: Perform math calculations
- read_file: Read a file (mock)
- echo: Echo back a message

Run with: python -m tests.mcp_servers.test_tools_server
"""

import asyncio
import json
from datetime import datetime
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Create server instance
server = Server("test-tools-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="get_current_time",
            description="Get the current date and time",
            inputSchema={
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Timezone (default: UTC)",
                        "default": "UTC",
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="calculate",
            description="Perform a mathematical calculation. Supports +, -, *, /, ** operators.",
            inputSchema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression to evaluate (e.g., '2 + 3 * 4')",
                    }
                },
                "required": ["expression"],
            },
        ),
        Tool(
            name="read_test_file",
            description="Read contents of a test file",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Name of the test file to read"}
                },
                "required": ["filename"],
            },
        ),
        Tool(
            name="echo",
            description="Echo back a message (for testing)",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message to echo back"}
                },
                "required": ["message"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""

    if name == "get_current_time":
        tz = arguments.get("timezone", "UTC")
        now = datetime.now()
        result = {
            "datetime": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "timezone": tz,
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "calculate":
        expression = arguments.get("expression", "")
        try:
            # Safe evaluation - only allow basic math
            allowed = set("0123456789+-*/.(). ")
            if not all(c in allowed or c.isspace() for c in expression):
                # Check for ** (power)
                clean = expression.replace("**", "")
                if not all(c in allowed or c.isspace() for c in clean):
                    return [
                        TextContent(type="text", text="Error: Invalid characters in expression")
                    ]

            result = eval(expression)  # Safe for math only
            return [TextContent(type="text", text=f"Result: {expression} = {result}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    elif name == "read_test_file":
        filename = arguments.get("filename", "")
        # Mock file contents for testing
        mock_files = {
            "test.txt": "This is a test file content.",
            "data.json": '{"key": "value", "numbers": [1, 2, 3]}',
            "readme.md": "# Test README\n\nThis is a test readme file.",
        }
        content = mock_files.get(filename, f"File '{filename}' not found")
        return [TextContent(type="text", text=content)]

    elif name == "echo":
        message = arguments.get("message", "")
        return [TextContent(type="text", text=f"Echo: {message}")]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
