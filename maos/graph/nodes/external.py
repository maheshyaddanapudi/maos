"""External agent node implementation using A2A protocol."""

import time
from typing import Any, Dict

import structlog

from maos.graph.state import (
    GraphState,
    ResultMetadata,
    ResultOutput,
    ResultType,
    WorkerResult,
)
from maos.agents.models import ExternalAgent
from maos.a2a.client import A2AClient
from maos.a2a.models import DiscoveredAgent

logger = structlog.get_logger()


class ExternalAgentNode:
    """External agent node using A2A protocol."""

    def __init__(
        self,
        agent: ExternalAgent,
        a2a_client: A2AClient,
        timeout: int = 40
    ):
        """
        Initialize the external agent node.

        Args:
            agent: External agent configuration.
            a2a_client: A2A client for communication.
            timeout: Request timeout in seconds.
        """
        self._agent = agent
        self._client = a2a_client
        self._timeout = timeout

    async def run(self, state: GraphState) -> Dict[str, Any]:
        """
        Execute the external agent via A2A.

        Args:
            state: Current graph state.

        Returns:
            State updates with worker result.
        """
        start_time = time.time()

        logger.info(
            "external_agent_executing",
            agent=self._agent.name,
            endpoint=self._agent.endpoint
        )

        try:
            # Build the task message from state
            task = state.get("task", "")
            if not task:
                # Fall back to last user message
                for msg in reversed(state.get("messages", [])):
                    if isinstance(msg, dict) and msg.get("role") == "user":
                        task = msg.get("content", "")
                        break

            # Create discovered agent for client
            discovered = DiscoveredAgent(
                card={"name": self._agent.name},  # Minimal card
                source_url=self._agent.source_url,
                endpoint=self._agent.endpoint,
                import_mode="node"
            )
            # Fix: create proper card
            from maos.a2a.models import AgentCard
            discovered.card = AgentCard(
                name=self._agent.name,
                description=self._agent.description
            )

            # Send request
            response = await self._client.send_message(
                discovered,
                task,
                timeout=self._timeout
            )

            duration_ms = int((time.time() - start_time) * 1000)

            if response.is_success:
                content = response.get_content() or ""

                worker_result = WorkerResult(
                    from_agent=self._agent.name,
                    output=ResultOutput(
                        type=ResultType.TEXT,
                        content=content
                    ),
                    metadata=ResultMetadata(duration_ms=duration_ms)
                )

                logger.info(
                    "external_agent_completed",
                    agent=self._agent.name,
                    duration_ms=duration_ms
                )

            else:
                error_msg = response.error.message if response.error else "Unknown error"

                worker_result = WorkerResult(
                    from_agent=self._agent.name,
                    output=ResultOutput(
                        type=ResultType.ERROR,
                        content=f"A2A error: {error_msg}"
                    ),
                    metadata=ResultMetadata(duration_ms=duration_ms)
                )

                logger.warning(
                    "external_agent_error",
                    agent=self._agent.name,
                    error=error_msg
                )

            return {
                "last_result": worker_result,
                "messages": [worker_result.to_message()]
            }

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "external_agent_exception",
                agent=self._agent.name,
                error=str(e)
            )

            worker_result = WorkerResult(
                from_agent=self._agent.name,
                output=ResultOutput(
                    type=ResultType.ERROR,
                    content=f"External agent error: {str(e)}"
                ),
                metadata=ResultMetadata(duration_ms=duration_ms)
            )

            return {
                "last_result": worker_result,
                "messages": [worker_result.to_message()]
            }

    @property
    def name(self) -> str:
        """Get agent name."""
        return self._agent.name

    @property
    def node_id(self) -> str:
        """Get LangGraph node ID."""
        return self._agent.node_id
