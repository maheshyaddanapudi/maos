"""
MAOS Anthropic LLM Adapter.

Provides Anthropic Claude API integration.
"""

import json
from collections.abc import AsyncIterator

import structlog
from anthropic import AsyncAnthropic

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


class AnthropicAdapter(BaseLLMAdapter):
    """Anthropic Claude LLM adapter."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        timeout: float = 60.0,
    ):
        super().__init__(model, temperature, max_tokens)
        self._client = AsyncAnthropic(
            api_key=api_key,
            timeout=timeout,
        )
        # Anthropic requires max_tokens
        if not self._max_tokens:
            self._max_tokens = 4096

    def _convert_messages(self, messages: list[Message]) -> tuple[str | None, list[dict]]:
        """Convert messages to Anthropic format.

        Returns:
            Tuple of (system_prompt, messages)
        """
        system_prompt = None
        result = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
                continue

            role = "assistant" if msg.role == "assistant" else "user"

            # Handle tool results
            if msg.role == "tool" and msg.tool_call_id:
                result.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content,
                        }
                    ],
                })
                continue

            # Handle assistant messages with tool calls
            if msg.tool_calls:
                content = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                result.append({"role": role, "content": content})
            else:
                result.append({"role": role, "content": msg.content or ""})

        return system_prompt, result

    def _convert_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        """Convert tools to Anthropic format."""
        return [t.to_anthropic_format() for t in tools]

    def _parse_response(self, content: list) -> tuple[str | None, list[ToolCall]]:
        """Parse Anthropic response content."""
        text_parts = []
        tool_calls = []

        for block in content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input if isinstance(block.input, dict) else {},
                ))

        text_content = "\n".join(text_parts) if text_parts else None
        return text_content, tool_calls

    async def invoke(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Invoke Anthropic API."""
        try:
            system_prompt, converted_messages = self._convert_messages(messages)

            kwargs: dict = {
                "model": self._model,
                "messages": converted_messages,
                "max_tokens": self._max_tokens,
            }

            if system_prompt:
                kwargs["system"] = system_prompt

            if self._temperature != 1.0:
                kwargs["temperature"] = self._temperature

            if tools:
                kwargs["tools"] = self._convert_tools(tools)

            log.debug("anthropic_invoke", model=self._model, message_count=len(messages))

            response = await self._client.messages.create(**kwargs)

            text_content, tool_calls = self._parse_response(response.content)

            return LLMResponse(
                content=text_content,
                tool_calls=tool_calls,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                },
                model=response.model,
                finish_reason=response.stop_reason,
            )
        except Exception as e:
            log.error("anthropic_error", error=str(e))
            raise LLMError(f"Anthropic API error: {e}")

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Stream Anthropic response."""
        try:
            system_prompt, converted_messages = self._convert_messages(messages)

            kwargs: dict = {
                "model": self._model,
                "messages": converted_messages,
                "max_tokens": self._max_tokens,
            }

            if system_prompt:
                kwargs["system"] = system_prompt

            if self._temperature != 1.0:
                kwargs["temperature"] = self._temperature

            if tools:
                kwargs["tools"] = self._convert_tools(tools)

            log.debug("anthropic_stream", model=self._model, message_count=len(messages))

            accumulated_tool_uses: dict[str, dict] = {}
            current_tool_id = None

            async with self._client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if event.type == "content_block_start":
                        if hasattr(event.content_block, "type"):
                            if event.content_block.type == "tool_use":
                                current_tool_id = event.content_block.id
                                accumulated_tool_uses[current_tool_id] = {
                                    "id": current_tool_id,
                                    "name": event.content_block.name,
                                    "arguments": "",
                                }

                    elif event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            yield LLMChunk(content=event.delta.text, done=False)
                        elif hasattr(event.delta, "partial_json"):
                            if current_tool_id and current_tool_id in accumulated_tool_uses:
                                accumulated_tool_uses[current_tool_id]["arguments"] += event.delta.partial_json

                    elif event.type == "message_stop":
                        tool_calls = None
                        if accumulated_tool_uses:
                            tool_calls = [
                                ToolCall(
                                    id=tc["id"],
                                    name=tc["name"],
                                    arguments=json.loads(tc["arguments"]) if tc["arguments"] else {},
                                )
                                for tc in accumulated_tool_uses.values()
                            ]
                        yield LLMChunk(
                            content="",
                            done=True,
                            tool_calls=tool_calls,
                        )
                        return
        except Exception as e:
            log.error("anthropic_stream_error", error=str(e))
            raise LLMError(f"Anthropic streaming error: {e}")
