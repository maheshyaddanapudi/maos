"""A2A client for communicating with external agents."""

import uuid
from collections.abc import AsyncIterator

import httpx
import structlog

from maos.a2a.models import (
    A2AConfiguration,
    A2AMessage,
    A2AParams,
    A2ARequest,
    A2AResponse,
    DiscoveredAgent,
    TaskStatus,
)
from maos.resilience import retry_with_backoff

logger = structlog.get_logger()


class A2AClient:
    """Client for A2A protocol communication."""

    def __init__(self, http_client: httpx.AsyncClient | None = None, timeout: float = 40.0):
        """
        Initialize A2A client.

        Args:
            http_client: HTTP client to use.
            timeout: Default request timeout.
        """
        self._http_client = http_client
        self._owns_client = http_client is None
        self._timeout = timeout

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is available."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self._timeout)
        return self._http_client

    async def send_message(
        self, agent: DiscoveredAgent, message: str, timeout: int | None = None
    ) -> A2AResponse:
        """
        Send a message to an external agent.

        Args:
            agent: The agent to send to.
            message: Message content.
            timeout: Request timeout.

        Returns:
            A2A response.
        """
        client = await self._ensure_client()

        request_id = str(uuid.uuid4())
        request = A2ARequest(
            method="message/send",
            id=request_id,
            params=A2AParams(
                message=A2AMessage.from_text("user", message),
                configuration=A2AConfiguration(timeout=timeout or int(self._timeout), stream=False),
            ),
        )

        logger.debug("sending_a2a_message", agent=agent.card.name, endpoint=agent.endpoint)

        try:

            async def _do_post() -> httpx.Response:
                resp = await client.post(
                    agent.endpoint,
                    json=request.model_dump(by_alias=True),
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                return resp

            response = await retry_with_backoff(
                _do_post,
                max_retries=2,
                base_delay=0.5,
                retryable_exceptions=(
                    httpx.TransportError,
                    httpx.HTTPStatusError,
                ),
            )

            a2a_response = A2AResponse.model_validate(response.json())

            logger.debug(
                "received_a2a_response",
                agent=agent.card.name,
                status=a2a_response.result.task.status if a2a_response.result else "error",
            )

            return a2a_response

        except httpx.TimeoutException:
            return A2AResponse(
                id=request_id, error={"code": -32000, "message": f"Timeout after {self._timeout}s"}
            )
        except Exception as e:
            logger.error("a2a_request_failed", agent=agent.card.name, error=str(e))
            return A2AResponse(
                id=request_id, error={"code": -32000, "message": "A2A request failed"}
            )

    async def stream_message(
        self, agent: DiscoveredAgent, message: str, timeout: int | None = None
    ) -> AsyncIterator[str]:
        """
        Stream a message to an external agent.

        Args:
            agent: The agent to send to.
            message: Message content.
            timeout: Request timeout.

        Yields:
            Response chunks.
        """
        if not agent.card.capabilities.streaming:
            # Fall back to non-streaming
            response = await self.send_message(agent, message, timeout)
            if response.is_success:
                content = response.get_content()
                if content:
                    yield content
            return

        client = await self._ensure_client()

        request_id = str(uuid.uuid4())
        request = A2ARequest(
            method="message/stream",
            id=request_id,
            params=A2AParams(
                message=A2AMessage.from_text("user", message),
                configuration=A2AConfiguration(timeout=timeout or int(self._timeout), stream=True),
            ),
        )

        try:
            async with client.stream(
                "POST",
                agent.endpoint,
                json=request.model_dump(by_alias=True),
                headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        # Try to parse as JSON
                        try:
                            import json

                            chunk = json.loads(data)
                            # Extract content based on format
                            if "content" in chunk:
                                yield chunk["content"]
                            elif "text" in chunk:
                                yield chunk["text"]
                        except json.JSONDecodeError:
                            # Plain text chunk
                            yield data

        except Exception as e:
            logger.error("a2a_stream_failed", agent=agent.card.name, error=str(e))

    async def get_task_status(self, agent: DiscoveredAgent, task_id: str) -> TaskStatus | None:
        """
        Get the status of a task.

        Args:
            agent: The agent that owns the task.
            task_id: Task ID.

        Returns:
            Task status if found.
        """
        client = await self._ensure_client()

        request = {
            "jsonrpc": "2.0",
            "method": "tasks/get",
            "id": str(uuid.uuid4()),
            "params": {"taskId": task_id},
        }

        try:
            response = await client.post(
                agent.endpoint, json=request, headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            data = response.json()
            if "result" in data and "task" in data["result"]:
                return TaskStatus(data["result"]["task"]["status"])

        except Exception as e:
            logger.warning("failed_to_get_task_status", error=str(e))

        return None

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._owns_client and self._http_client:
            await self._http_client.aclose()
            self._http_client = None
