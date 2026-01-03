"""
MAOS MCP Stdio Transport.

Transport implementation using stdin/stdout subprocess communication.
"""

import asyncio
import json
from typing import Any

import structlog

from maos.errors import MCPConnectionError, MCPError
from maos.mcp.transports.base import BaseMCPTransport

log = structlog.get_logger()


class StdioTransport(BaseMCPTransport):
    """MCP transport over stdin/stdout subprocess."""

    def __init__(
        self,
        command: list[str],
        env: dict[str, str] | None = None,
        timeout: float = 30.0,
    ):
        super().__init__(timeout)
        self._command = command
        self._env = env
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Spawn subprocess and connect."""
        if self._connected:
            return

        try:
            log.debug("stdio_spawn", command=self._command)

            # Merge environment
            import os
            env = os.environ.copy()
            if self._env:
                env.update(self._env)

            self._process = await asyncio.create_subprocess_exec(
                *self._command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            self._connected = True
            log.info("stdio_connected", pid=self._process.pid)

        except Exception as e:
            log.error("stdio_spawn_failed", error=str(e))
            raise MCPConnectionError(f"Failed to spawn MCP server: {e}")

    async def send(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send JSON-RPC message and receive response."""
        if not self._connected or not self._process:
            raise MCPError("Transport not connected")

        async with self._lock:
            try:
                # Add request ID if not present
                if "id" not in message:
                    self._request_id += 1
                    message["id"] = self._request_id

                if "jsonrpc" not in message:
                    message["jsonrpc"] = "2.0"

                # Encode and send
                data = json.dumps(message) + "\n"
                self._process.stdin.write(data.encode())
                await self._process.stdin.drain()

                # Read response
                response_line = await asyncio.wait_for(
                    self._process.stdout.readline(),
                    timeout=self._timeout,
                )

                if not response_line:
                    raise MCPError("No response from MCP server")

                response = json.loads(response_line.decode())

                # Check for error
                if "error" in response:
                    error = response["error"]
                    raise MCPError(f"MCP error: {error.get('message', 'Unknown error')}")

                return response

            except TimeoutError:
                raise MCPError(f"MCP request timed out after {self._timeout}s")
            except json.JSONDecodeError as e:
                raise MCPError(f"Invalid JSON response: {e}")

    async def disconnect(self) -> None:
        """Terminate subprocess."""
        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except TimeoutError:
                self._process.kill()
            except Exception as e:
                log.warning("stdio_disconnect_error", error=str(e))
            finally:
                self._process = None
                self._connected = False
                log.info("stdio_disconnected")
