"""
Mock LLM Adapter for Testing.
"""

from collections.abc import AsyncIterator

from maos.llm.base import (
    LLMAdapter,
    LLMChunk,
    LLMResponse,
    Message,
    ToolCall,
    ToolDefinition,
)


class MockLLMAdapter(LLMAdapter):
    """Mock LLM adapter for testing."""

    def __init__(
        self,
        responses: list[str] | None = None,
        tool_calls: list[ToolCall] | None = None,
        model: str = "mock-model",
    ):
        self._responses = responses or ["Mock response"]
        self._tool_calls = tool_calls or []
        self._model = model
        self._call_count = 0
        self._calls: list[dict] = []

    @property
    def model_name(self) -> str:
        return self._model

    def set_responses(self, responses: list[str]) -> None:
        """Set responses for upcoming calls."""
        self._responses = responses
        self._call_count = 0

    def set_tool_calls(self, tool_calls: list[ToolCall]) -> None:
        """Set tool calls for upcoming calls."""
        self._tool_calls = tool_calls

    async def invoke(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Mock invoke."""
        self._calls.append({
            "messages": messages,
            "tools": tools,
        })

        response_idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1

        return LLMResponse(
            content=self._responses[response_idx],
            tool_calls=self._tool_calls if self._call_count == 1 else [],
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            model=self._model,
            finish_reason="stop",
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Mock stream."""
        response = await self.invoke(messages, tools)

        if response.content:
            words = response.content.split()
            for _i, word in enumerate(words):
                yield LLMChunk(
                    content=word + " ",
                    done=False,
                )

        yield LLMChunk(
            content="",
            done=True,
            tool_calls=response.tool_calls if response.tool_calls else None,
            finish_reason="stop",
        )

    def get_calls(self) -> list[dict]:
        """Get all recorded calls."""
        return self._calls

    def get_last_call(self) -> dict | None:
        """Get the last recorded call."""
        return self._calls[-1] if self._calls else None

    def assert_called(self) -> None:
        """Assert that the adapter was called."""
        assert self._calls, "LLM adapter was not called"

    def assert_called_times(self, n: int) -> None:
        """Assert call count."""
        assert len(self._calls) == n, f"Expected {n} calls, got {len(self._calls)}"

    def reset(self) -> None:
        """Reset call history."""
        self._calls = []
        self._call_count = 0
