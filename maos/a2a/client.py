"""
MAOS A2A Client.

Client for communicating with external A2A agents.
"""

import uuid
from collections.abc import AsyncIterator

import httpx
import structlog

from maos.a2a.models import (
    A2AConfiguration,
    A2AMessage,
    A2ARequest,
    A2AResponse,
    DiscoveredAgent,
    TaskStatus,
)
from maos.agents.models import ResultMetadata, WorkerResult
from maos.errors import A2AError

log = structlog.get_logger()


class A2AClient:
    """Client for A2A protocol communication."""

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        default_timeout: int = 40,
    ):
        self._http_client = http_client
        self._owns_client = http_client is None
        self._default_timeout = default_timeout

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self._default_timeout)
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client if owned."""
        if self._owns_client and self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def send_message(
        self,
        agent: DiscoveredAgent,
        message: str,
        timeout: int | None = None,
        stream: bool = False,
    ) -> WorkerResult:
        """Send message to an external agent.

        Args:
            agent: Discovered agent to send to
            message: Message content
            timeout: Request timeout in seconds
            stream: Whether to request streaming

        Returns:
            Worker result from the agent
        """
        import time
        start_time = time.time()

        try:
            log.debug(
                "a2a_send_message",
                agent=agent.card.name,
                endpoint=agent.endpoint,
            )

            request = A2ARequest(
                method="message/send",
                id=str(uuid.uuid4()),
                message=A2AMessage.from_text("user", message),
                configuration=A2AConfiguration(
                    timeout=timeout or self._default_timeout,
                    stream=stream,
                ),
            )

            client = await self._get_client()

            response = await client.post(
                agent.endpoint,
                json=request.to_dict(),
                headers={"Content-Type": "application/json"},
                timeout=timeout or self._default_timeout,
            )

            response.raise_for_status()

            a2a_response = A2AResponse.from_dict(response.json())
            duration_ms = int((time.time() - start_time) * 1000)

            if a2a_response.error:
                error_msg = a2a_response.error.get("message", "Unknown A2A error")
                return WorkerResult.error(
                    from_agent=f"ext::{agent.card.name}",
                    error_message=error_msg,
                    metadata=ResultMetadata(duration_ms=duration_ms),
                )

            if a2a_response.is_complete:
                content = a2a_response.get_content() or ""
                return WorkerResult.success(
                    from_agent=f"ext::{agent.card.name}",
                    content=content,
                    metadata=ResultMetadata(duration_ms=duration_ms),
                )

            # Task may be in progress
            if a2a_response.task:
                if a2a_response.task.status == TaskStatus.FAILED:
                    return WorkerResult.error(
                        from_agent=f"ext::{agent.card.name}",
                        error_message=a2a_response.task.error or "Task failed",
                        metadata=ResultMetadata(duration_ms=duration_ms),
                    )

                if a2a_response.task.status == TaskStatus.INPUT_REQUIRED:
                    content = a2a_response.get_content() or "Input required"
                    return WorkerResult.success(
                        from_agent=f"ext::{agent.card.name}",
                        content=f"[Input Required] {content}",
                        metadata=ResultMetadata(duration_ms=duration_ms),
                    )

            return WorkerResult.error(
                from_agent=f"ext::{agent.card.name}",
                error_message="Unexpected response state",
                metadata=ResultMetadata(duration_ms=duration_ms),
            )

        except httpx.TimeoutException:
            duration_ms = int((time.time() - start_time) * 1000)
            return WorkerResult.error(
                from_agent=f"ext::{agent.card.name}",
                error_message=f"Request timed out after {timeout or self._default_timeout}s",
                metadata=ResultMetadata(duration_ms=duration_ms),
            )
        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return WorkerResult.error(
                from_agent=f"ext::{agent.card.name}",
                error_message=f"HTTP error: {e.response.status_code}",
                metadata=ResultMetadata(duration_ms=duration_ms),
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            log.error("a2a_request_error", agent=agent.card.name, error=str(e))
            return WorkerResult.error(
                from_agent=f"ext::{agent.card.name}",
                error_message=str(e),
                metadata=ResultMetadata(duration_ms=duration_ms),
            )

    async def stream_message(
        self,
        agent: DiscoveredAgent,
        message: str,
        timeout: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream message from an external agent.

        Args:
            agent: Discovered agent to send to
            message: Message content
            timeout: Request timeout in seconds

        Yields:
            Response content chunks
        """
        try:
            log.debug(
                "a2a_stream_message",
                agent=agent.card.name,
                endpoint=agent.endpoint,
            )

            request = A2ARequest(
                method="message/stream",
                id=str(uuid.uuid4()),
                message=A2AMessage.from_text("user", message),
                configuration=A2AConfiguration(
                    timeout=timeout or self._default_timeout,
                    stream=True,
                ),
            )

            client = await self._get_client()

            async with client.stream(
                "POST",
                agent.endpoint,
                json=request.to_dict(),
                headers={"Content-Type": "application/json"},
                timeout=timeout or self._default_timeout,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data and data != "[DONE]":
                            yield data

        except Exception as e:
            log.error("a2a_stream_error", agent=agent.card.name, error=str(e))
            raise A2AError(f"Streaming error: {e}")
