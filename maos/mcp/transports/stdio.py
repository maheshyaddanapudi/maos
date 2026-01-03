"""Stdio MCP transport implementation."""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from maos.mcp.transports.base import MCPTransport


class StdioTransport(MCPTransport):
    """MCP transport over stdin/stdout with subprocess."""

    def __init__(
        self,
        command: List[str],
        env: Optional[Dict[str, str]] = None,
        timeout: float = 30.0
    ):
        """
        Initialize stdio transport.

        Args:
            command: Command and arguments to spawn.
            env: Additional environment variables.
            timeout: Request timeout in seconds.
        """
        self._command = command
        self._env = env or {}
        self._timeout = timeout
        self._process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Spawn the MCP server subprocess."""
        # Merge environment
        full_env = os.environ.copy()
        full_env.update(self._env)

        self._process = await asyncio.create_subprocess_exec(
            *self._command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env
        )

        # Wait briefly to ensure process started
        await asyncio.sleep(0.1)

        if self._process.returncode is not None:
            stderr = await self._process.stderr.read() if self._process.stderr else b""
            raise RuntimeError(
                f"MCP server process exited immediately: {stderr.decode()}"
            )

    async def disconnect(self) -> None:
        """Terminate the subprocess."""
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None

    async def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message via stdin and read response from stdout."""
        if not self._process or not self._process.stdin or not self._process.stdout:
            raise RuntimeError("Transport not connected")

        async with self._lock:
            # Assign request ID if not present
            if "id" not in message:
                self._request_id += 1
                message["id"] = self._request_id

            # Send message
            line = json.dumps(message) + "\n"
            self._process.stdin.write(line.encode())
            await self._process.stdin.drain()

            # Read response
            try:
                response_line = await asyncio.wait_for(
                    self._process.stdout.readline(),
                    timeout=self._timeout
                )
            except asyncio.TimeoutError:
                raise TimeoutError(f"MCP request timed out after {self._timeout}s")

            if not response_line:
                raise RuntimeError("MCP server closed connection")

            try:
                return json.loads(response_line.decode())
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Invalid JSON response: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if process is running."""
        return self._process is not None and self._process.returncode is None
