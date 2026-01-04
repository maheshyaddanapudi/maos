"""
MAOS External Agent Node.

Wraps A2A client calls as a LangGraph node.
"""

import asyncio
from typing import Any

import structlog

from maos.a2a.client import A2AClient
from maos.a2a.models import DiscoveredAgent
from maos.agents.models import WorkerResult
from maos.graph.state import GraphState

log = structlog.get_logger()


class ExternalAgentNode:
    """External agent node using A2A protocol."""

    def __init__(
        self,
        agent: DiscoveredAgent,
        client: A2AClient,
        timeout: int = 40,
    ):
        self._agent = agent
        self._client = client
        self._timeout = timeout

    @property
    def name(self) -> str:
        return f"ext::{self._agent.card.name}"

    async def run(self, state: GraphState) -> dict[str, Any]:
        """Execute external agent via A2A.

        1. Build A2A request from state
        2. Send to external agent endpoint
        3. Convert to WorkerResult
        4. Return updated state
        """
        log.debug("external_run", name=self._agent.card.name)

        # Extract task
        task = state.get("task", "")
        messages = state.get("messages", [])

        # Get the most recent user message
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                task = msg.get("content", task)
                break

        # Include last result as context if available
        last_result = state.get("last_result")
        if last_result:
            task = f"Previous result:\n{last_result.content}\n\nTask: {task}"

        log.info(
            "external_execute",
            name=self._agent.card.name,
            endpoint=self._agent.endpoint,
        )

        try:
            result = await asyncio.wait_for(
                self._client.send_message(
                    self._agent,
                    task,
                    timeout=self._timeout,
                ),
                timeout=self._timeout + 5,  # Extra buffer
            )
        except TimeoutError:
            log.error("external_timeout", name=self._agent.card.name)
            result = WorkerResult.error(
                from_agent=self.name,
                error_message=f"External agent timed out after {self._timeout}s",
            )
        except Exception as e:
            log.error("external_error", name=self._agent.card.name, error=str(e))
            result = WorkerResult.error(
                from_agent=self.name,
                error_message=str(e),
            )

        log.info(
            "external_complete",
            name=self._agent.card.name,
            is_error=result.is_error,
        )

        # Build response
        return {
            "last_result": result,
            "messages": [result.to_message()],
            "next": None,  # Return to supervisor
        }
