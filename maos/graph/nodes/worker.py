"""
MAOS Native Worker Node.

Wraps agent execution as a LangGraph node.
"""

import asyncio
from typing import Any

import structlog

from maos.agents.models import Agent, WorkerResult
from maos.graph.state import GraphState

log = structlog.get_logger()


class NativeWorkerNode:
    """Native worker node wrapping an agent."""

    def __init__(self, agent: Agent, timeout: int | None = None):
        self._agent = agent
        self._timeout = timeout or agent.timeout_seconds

    @property
    def name(self) -> str:
        return self._agent.name

    async def run(self, state: GraphState) -> dict[str, Any]:
        """Execute worker agent.

        1. Extract task from state
        2. Invoke agent with task
        3. Build WorkerResult
        4. Return updated state
        """
        log.debug("worker_run", name=self._agent.name)

        # Extract task - use last user message or state task
        task = state.get("task", "")
        messages = state.get("messages", [])

        # Get the most recent user message as context
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                task = msg.get("content", task)
                break

        # If we have a last result, include it as context
        last_result = state.get("last_result")
        if last_result and last_result.from_agent != self._agent.name:
            task = f"Previous result from {last_result.from_agent}:\n{last_result.content}\n\nContinue with: {task}"

        log.info("worker_execute", name=self._agent.name, task_length=len(task))

        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                self._agent.execute(task),
                timeout=self._timeout,
            )
        except TimeoutError:
            log.error("worker_timeout", name=self._agent.name, timeout=self._timeout)
            result = WorkerResult.error(
                from_agent=self._agent.name,
                error_message=f"Worker timed out after {self._timeout}s",
            )
        except Exception as e:
            log.error("worker_error", name=self._agent.name, error=str(e))
            result = WorkerResult.error(
                from_agent=self._agent.name,
                error_message=str(e),
            )

        log.info(
            "worker_complete",
            name=self._agent.name,
            is_error=result.is_error,
            content_length=len(result.content),
        )

        # Build response
        return {
            "last_result": result,
            "messages": [result.to_message()],
            "next": None,  # Return to supervisor
        }
