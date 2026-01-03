"""
MAOS OpenAI LLM Adapter.

Provides OpenAI API integration.
"""

import json
from collections.abc import AsyncIterator

import structlog
from openai import AsyncOpenAI

from maos.errors import LLMError
from maos.llm.base import (
    BaseLLMAdapter,
    LLMChunk,
    LLMResponse,
    Message,
    ToolCall,
    ToolDefinition,
)

log = structlog.get_logger()


class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI LLM adapter."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        timeout: float = 60.0,
    ):
        super().__init__(model, temperature, max_tokens)
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    def _convert_messages(self, messages: list[Message]) -> list[dict]:
        """Convert messages to OpenAI format."""
        result = []
        for msg in messages:
            d: dict = {"role": msg.role, "content": msg.content or ""}
            if msg.name:
                d["name"] = msg.name
            if msg.tool_calls:
                d["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            if msg.tool_call_id:
                d["tool_call_id"] = msg.tool_call_id
            result.append(d)
        return result

    def _convert_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        """Convert tools to OpenAI format."""
        return [t.to_openai_format() for t in tools]

    def _parse_tool_calls(self, tool_calls: list | None) -> list[ToolCall]:
        """Parse tool calls from OpenAI response."""
        if not tool_calls:
            return []

        result = []
        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {"raw": tc.function.arguments}

            result.append(ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=args,
            ))
        return result

    async def invoke(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Invoke OpenAI API."""
        try:
            kwargs: dict = {
                "model": self._model,
                "messages": self._convert_messages(messages),
                "temperature": self._temperature,
            }

            if self._max_tokens:
                kwargs["max_tokens"] = self._max_tokens

            if tools:
                kwargs["tools"] = self._convert_tools(tools)

            log.debug("openai_invoke", model=self._model, message_count=len(messages))

            response = await self._client.chat.completions.create(**kwargs)

            choice = response.choices[0]
            message = choice.message

            return LLMResponse(
                content=message.content,
                tool_calls=self._parse_tool_calls(message.tool_calls),
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                model=response.model,
                finish_reason=choice.finish_reason,
            )
        except Exception as e:
            log.error("openai_error", error=str(e))
            raise LLMError(f"OpenAI API error: {e}")

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Stream OpenAI response."""
        try:
            kwargs: dict = {
                "model": self._model,
                "messages": self._convert_messages(messages),
                "temperature": self._temperature,
                "stream": True,
            }

            if self._max_tokens:
                kwargs["max_tokens"] = self._max_tokens

            if tools:
                kwargs["tools"] = self._convert_tools(tools)

            log.debug("openai_stream", model=self._model, message_count=len(messages))

            stream = await self._client.chat.completions.create(**kwargs)

            accumulated_tool_calls: dict[int, dict] = {}

            async for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason

                # Handle tool calls accumulation
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc.id or "",
                                "name": tc.function.name if tc.function else "",
                                "arguments": "",
                            }
                        if tc.function and tc.function.arguments:
                            accumulated_tool_calls[idx]["arguments"] += tc.function.arguments

                # Yield content chunks
                if delta.content:
                    yield LLMChunk(
                        content=delta.content,
                        done=False,
                    )

                # Final chunk with tool calls
                if finish_reason:
                    tool_calls = None
                    if accumulated_tool_calls:
                        tool_calls = [
                            ToolCall(
                                id=tc["id"],
                                name=tc["name"],
                                arguments=json.loads(tc["arguments"]) if tc["arguments"] else {},
                            )
                            for tc in accumulated_tool_calls.values()
                        ]

                    yield LLMChunk(
                        content="",
                        done=True,
                        tool_calls=tool_calls,
                        finish_reason=finish_reason,
                    )
        except Exception as e:
            log.error("openai_stream_error", error=str(e))
            raise LLMError(f"OpenAI streaming error: {e}")
