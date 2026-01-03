"""Native worker node implementation."""

import asyncio
import time
from typing import Any, Dict, List

import structlog

from maos.graph.state import (
    GraphState,
    ResultMetadata,
    ResultOutput,
    ResultType,
    ToolCallRecord,
    WorkerResult,
)
from maos.agents.models import WorkerAgent
from maos.llm.base import LLMAdapter, Message, ToolDefinition
from maos.tools.models import Tool

logger = structlog.get_logger()


class NativeWorkerNode:
    """Native worker node wrapping an agent."""

    def __init__(
        self,
        agent: WorkerAgent,
        llm: LLMAdapter,
        tools: List[Tool],
        timeout: int = 60
    ):
        """
        Initialize the worker node.

        Args:
            agent: The worker agent configuration.
            llm: LLM adapter for the worker.
            tools: Tools available to the worker.
            timeout: Execution timeout in seconds.
        """
        self._agent = agent
        self._llm = llm
        self._tools = tools
        self._timeout = timeout

    async def run(self, state: GraphState) -> Dict[str, Any]:
        """
        Execute the worker agent.

        Args:
            state: Current graph state.

        Returns:
            State updates with worker result.
        """
        start_time = time.time()
        tool_call_records = []

        logger.info(
            "worker_executing",
            worker=self._agent.name,
            task=state.get("task", "")[:100]
        )

        try:
            # Build messages for the worker
            messages = self._build_messages(state)

            # Build tool definitions
            tool_defs = [
                ToolDefinition(
                    name=tool.id,
                    description=tool.description,
                    parameters=tool.input_schema.model_dump()
                )
                for tool in self._tools
            ]

            # Execute with timeout
            result_content = await asyncio.wait_for(
                self._execute_with_tools(messages, tool_defs, tool_call_records),
                timeout=self._timeout
            )

            duration_ms = int((time.time() - start_time) * 1000)

            worker_result = WorkerResult(
                from_agent=self._agent.name,
                output=ResultOutput(
                    type=ResultType.TEXT,
                    content=result_content,
                    tool_calls=tool_call_records
                ),
                metadata=ResultMetadata(
                    duration_ms=duration_ms,
                    tools_invoked=[tc.tool_name for tc in tool_call_records],
                    model_used=self._llm.get_model_name()
                )
            )

            logger.info(
                "worker_completed",
                worker=self._agent.name,
                duration_ms=duration_ms,
                tools_used=len(tool_call_records)
            )

            return {
                "last_result": worker_result,
                "messages": [worker_result.to_message()]
            }

        except asyncio.TimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                "worker_timeout",
                worker=self._agent.name,
                timeout=self._timeout
            )

            worker_result = WorkerResult(
                from_agent=self._agent.name,
                output=ResultOutput(
                    type=ResultType.ERROR,
                    content=f"Worker timed out after {self._timeout}s"
                ),
                metadata=ResultMetadata(duration_ms=duration_ms)
            )

            return {
                "last_result": worker_result,
                "messages": [worker_result.to_message()]
            }

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "worker_error",
                worker=self._agent.name,
                error=str(e)
            )

            worker_result = WorkerResult(
                from_agent=self._agent.name,
                output=ResultOutput(
                    type=ResultType.ERROR,
                    content=f"Worker error: {str(e)}"
                ),
                metadata=ResultMetadata(duration_ms=duration_ms)
            )

            return {
                "last_result": worker_result,
                "messages": [worker_result.to_message()]
            }

    async def _execute_with_tools(
        self,
        messages: List[Message],
        tool_defs: List[ToolDefinition],
        tool_records: List[ToolCallRecord]
    ) -> str:
        """Execute LLM with tool loop."""
        max_tool_calls = 10
        current_messages = messages.copy()

        for _ in range(max_tool_calls):
            response = await self._llm.invoke(current_messages, tools=tool_defs)

            if not response.has_tool_calls:
                return response.content

            # Execute tool calls
            tool_results = []
            for tc in response.tool_calls:
                tool_result = await self._execute_tool(tc.name, tc.arguments)
                tool_records.append(tool_result)
                tool_results.append((tc.id, tool_result))

            # Add assistant message with tool calls
            current_messages.append(Message(
                role="assistant",
                content=response.content or "",
                tool_calls=[{
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments
                } for tc in response.tool_calls]
            ))

            # Add tool results
            for tc_id, result in tool_results:
                current_messages.append(Message(
                    role="tool",
                    content=str(result.output) if result.success else f"Error: {result.error_message}",
                    tool_call_id=tc_id
                ))

        # Max tool calls reached
        return "Maximum tool calls reached"

    async def _execute_tool(
        self,
        tool_id: str,
        arguments: Dict[str, Any]
    ) -> ToolCallRecord:
        """Execute a single tool call."""
        start_time = time.time()

        tool = None
        for t in self._tools:
            if t.id == tool_id:
                tool = t
                break

        if tool is None:
            return ToolCallRecord(
                tool_id=tool_id,
                tool_name=tool_id,
                input_args=arguments,
                output=None,
                success=False,
                error_message=f"Tool not found: {tool_id}"
            )

        try:
            result = await tool.call(arguments)
            duration_ms = int((time.time() - start_time) * 1000)

            return ToolCallRecord(
                tool_id=tool_id,
                tool_name=tool.name,
                input_args=arguments,
                output=result,
                success=True,
                duration_ms=duration_ms
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolCallRecord(
                tool_id=tool_id,
                tool_name=tool.name if tool else tool_id,
                input_args=arguments,
                output=None,
                success=False,
                error_message=str(e),
                duration_ms=duration_ms
            )

    def _build_messages(self, state: GraphState) -> List[Message]:
        """Build message list for the worker."""
        messages = [Message.system(self._agent.system_prompt)]

        # Add relevant conversation history
        for msg in state.get("messages", []):
            if isinstance(msg, dict):
                messages.append(Message(
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                    name=msg.get("name")
                ))

        return messages

    @property
    def name(self) -> str:
        """Get worker name."""
        return self._agent.name
