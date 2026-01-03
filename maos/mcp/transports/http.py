"""HTTP/SSE MCP transport implementation."""

import json
from typing import Any, Dict, Optional

import httpx

from maos.mcp.transports.base import MCPTransport


class HTTPTransport(MCPTransport):
    """MCP transport over HTTP."""

    def __init__(
        self,
        url: str,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialize HTTP transport.

        Args:
            url: MCP server URL.
            timeout: Request timeout in seconds.
            headers: Additional headers to send.
        """
        self._url = url.rstrip("/")
        self._timeout = timeout
        self._headers = headers or {}
        self._client: Optional[httpx.AsyncClient] = None
        self._request_id = 0

    async def connect(self) -> None:
        """Create HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self._url,
            timeout=self._timeout,
            headers={
                "Content-Type": "application/json",
                **self._headers
            }
        )

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send JSON-RPC request over HTTP."""
        if not self._client:
            raise RuntimeError("Transport not connected")

        # Assign request ID if not present
        if "id" not in message:
            self._request_id += 1
            message["id"] = self._request_id

        try:
            response = await self._client.post("/", json=message)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            raise TimeoutError(f"MCP HTTP request timed out after {self._timeout}s")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"MCP HTTP error: {e.response.status_code}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if client is available."""
        return self._client is not None


class SSETransport(MCPTransport):
    """MCP transport over Server-Sent Events."""

    def __init__(
        self,
        url: str,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialize SSE transport.

        Args:
            url: MCP server URL.
            timeout: Request timeout in seconds.
            headers: Additional headers to send.
        """
        self._url = url.rstrip("/")
        self._timeout = timeout
        self._headers = headers or {}
        self._client: Optional[httpx.AsyncClient] = None
        self._request_id = 0

    async def connect(self) -> None:
        """Create HTTP client for SSE."""
        self._client = httpx.AsyncClient(
            base_url=self._url,
            timeout=self._timeout,
            headers={
                "Accept": "text/event-stream",
                **self._headers
            }
        )

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send request and collect SSE response."""
        if not self._client:
            raise RuntimeError("Transport not connected")

        if "id" not in message:
            self._request_id += 1
            message["id"] = self._request_id

        try:
            async with self._client.stream("POST", "/", json=message) as response:
                response.raise_for_status()

                # Collect SSE events
                result = None
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        try:
                            result = json.loads(data)
                            # Check if this is the final response
                            if "result" in result or "error" in result:
                                break
                        except json.JSONDecodeError:
                            continue

                if result is None:
                    raise RuntimeError("No valid response received from SSE stream")

                return result

        except httpx.TimeoutException:
            raise TimeoutError(f"MCP SSE request timed out after {self._timeout}s")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"MCP SSE error: {e.response.status_code}")

    @property
    def is_connected(self) -> bool:
        """Check if client is available."""
        return self._client is not None
