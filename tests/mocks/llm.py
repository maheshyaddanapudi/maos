"""Mock LLM adapter for testing."""

from typing import Any, AsyncIterator, Dict, List, Optional

from maos.llm.base import (
    LLMAdapter,
    LLMChunk,
    LLMResponse,
    Message,
    ToolCallRequest,
    ToolDefinition,
)


class MockLLMAdapter(LLMAdapter):
    """Mock LLM adapter for testing without API calls."""

    def __init__(
        self,
        responses: Optional[List[str]] = None,
        tool_calls: Optional[List[List[ToolCallRequest]]] = None,
        model_name: str = "mock-model"
    ):
        """
        Initialize the mock adapter.

        Args:
            responses: List of response contents to return in order.
            tool_calls: List of tool call lists to return in order.
            model_name: Model name to report.
        """
        self._responses = responses or ["Mock response"]
        self._tool_calls = tool_calls or []
        self._model_name = model_name
        self._call_count = 0
        self._invoke_history: List[Dict[str, Any]] = []

    async def invoke(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None
    ) -> LLMResponse:
        """Return a mock response."""
        # Record the call
        self._invoke_history.append({
            "messages": messages,
            "tools": tools
        })

        # Get response content
        response_idx = min(self._call_count, len(self._responses) - 1)
        content = self._responses[response_idx]

        # Get tool calls if any
        tool_call_list = []
        if self._call_count < len(self._tool_calls):
            tool_call_list = self._tool_calls[self._call_count]

        self._call_count += 1

        return LLMResponse(
            content=content,
            tool_calls=tool_call_list,
            finish_reason="stop" if not tool_call_list else "tool_calls"
        )

    async def stream(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None
    ) -> AsyncIterator[LLMChunk]:
        """Stream a mock response."""
        response = await self.invoke(messages, tools)

        # Yield content in chunks
        content = response.content
        chunk_size = 10

        for i in range(0, len(content), chunk_size):
            chunk = content[i:i + chunk_size]
            yield LLMChunk(
                content=chunk,
                finish_reason=None if i + chunk_size < len(content) else "stop"
            )

    def get_model_name(self) -> str:
        """Return the mock model name."""
        return self._model_name

    @property
    def call_count(self) -> int:
        """Get number of invoke calls."""
        return self._call_count

    @property
    def invoke_history(self) -> List[Dict[str, Any]]:
        """Get history of invoke calls."""
        return self._invoke_history

    def reset(self) -> None:
        """Reset the mock state."""
        self._call_count = 0
        self._invoke_history = []


class MockSupervisorLLM(MockLLMAdapter):
    """Mock LLM that returns supervisor routing decisions."""

    def __init__(
        self,
        routing_sequence: Optional[List[str]] = None,
        model_name: str = "mock-supervisor"
    ):
        """
        Initialize with routing sequence.

        Args:
            routing_sequence: List of worker names or "END" to route to.
            model_name: Model name to report.
        """
        self._routing_sequence = routing_sequence or ["END"]
        self._routing_idx = 0

        # Build response strings
        responses = []
        for route in self._routing_sequence:
            responses.append(f'{{"next": "{route}", "reasoning": "Routing to {route}"}}')

        super().__init__(responses=responses, model_name=model_name)

    def get_next_route(self) -> str:
        """Get the next route in sequence."""
        idx = min(self._routing_idx, len(self._routing_sequence) - 1)
        route = self._routing_sequence[idx]
        self._routing_idx += 1
        return route


class MockToolCallingLLM(MockLLMAdapter):
    """Mock LLM that makes tool calls."""

    def __init__(
        self,
        tool_call_sequence: List[Dict[str, Any]],
        final_response: str = "Task completed",
        model_name: str = "mock-tool-caller"
    ):
        """
        Initialize with tool call sequence.

        Args:
            tool_call_sequence: List of tool call dicts with 'name' and 'arguments'.
            final_response: Response after all tool calls.
            model_name: Model name to report.
        """
        # Build tool calls
        tool_calls = []
        for i, tc in enumerate(tool_call_sequence):
            tool_calls.append([
                ToolCallRequest(
                    id=f"call_{i}",
                    name=tc.get("name", "unknown"),
                    arguments=tc.get("arguments", {})
                )
            ])

        # Empty tool calls for final response
        tool_calls.append([])

        # Responses - empty for tool calls, final response at end
        responses = [""] * len(tool_call_sequence) + [final_response]

        super().__init__(
            responses=responses,
            tool_calls=tool_calls,
            model_name=model_name
        )
