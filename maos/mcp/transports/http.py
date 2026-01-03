"""
MAOS MCP HTTP Transport.

Transport implementation using HTTP/SSE communication.
"""

import json
from typing import Any

import httpx
import structlog

from maos.errors import MCPConnectionError, MCPError
from maos.mcp.transports.base import BaseMCPTransport

log = structlog.get_logger()


class HTTPTransport(BaseMCPTransport):
    """MCP transport over HTTP."""

    def __init__(
        self,
        url: str,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(timeout)
        self._url = url.rstrip("/")
        self._headers = headers or {}
        self._client: httpx.AsyncClient | None = None
        self._request_id = 0

    async def connect(self) -> None:
        """Initialize HTTP client."""
        if self._connected:
            return

        try:
            log.debug("http_connect", url=self._url)

            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers=self._headers,
            )

            # Verify connection by making a ping request
            # Some MCP servers support this
            try:
                await self._client.get(f"{self._url}/health")
            except httpx.HTTPError:
                pass  # Health endpoint may not exist

            self._connected = True
            log.info("http_connected", url=self._url)

        except Exception as e:
            log.error("http_connect_failed", error=str(e))
            raise MCPConnectionError(f"Failed to connect to MCP server: {e}")

    async def send(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send JSON-RPC message over HTTP."""
        if not self._connected or not self._client:
            raise MCPError("Transport not connected")

        try:
            # Add request ID if not present
            if "id" not in message:
                self._request_id += 1
                message["id"] = self._request_id

            if "jsonrpc" not in message:
                message["jsonrpc"] = "2.0"

            log.debug("http_send", method=message.get("method"))

            response = await self._client.post(
                self._url,
                json=message,
                headers={"Content-Type": "application/json"},
            )

            response.raise_for_status()

            result = response.json()

            # Check for error
            if "error" in result:
                error = result["error"]
                raise MCPError(f"MCP error: {error.get('message', 'Unknown error')}")

            return result

        except httpx.TimeoutException:
            raise MCPError(f"MCP request timed out after {self._timeout}s")
        except httpx.HTTPStatusError as e:
            raise MCPError(f"HTTP error: {e.response.status_code}")
        except json.JSONDecodeError as e:
            raise MCPError(f"Invalid JSON response: {e}")

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            try:
                await self._client.aclose()
            except Exception as e:
                log.warning("http_disconnect_error", error=str(e))
            finally:
                self._client = None
                self._connected = False
                log.info("http_disconnected")
