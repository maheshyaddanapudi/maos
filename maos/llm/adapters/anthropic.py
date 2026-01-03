"""Anthropic Claude LLM adapter."""

import json
import os
from typing import Any, AsyncIterator, Dict, List, Optional

from maos.config.models import LLMConfig
from maos.llm.base import (
    LLMAdapter,
    LLMChunk,
    LLMResponse,
    Message,
    ToolCallRequest,
    ToolDefinition,
)


class AnthropicAdapter(LLMAdapter):
    """Adapter for Anthropic Claude API."""

    def __init__(self, config: LLMConfig):
        """
        Initialize the Anthropic adapter.

        Args:
            config: LLM configuration.
        """
        self._config = config
        self._model = config.model
        self._temperature = config.temperature
        self._max_tokens = config.max_tokens or 4096

        # Get API key from environment
        api_key_env = config.api_key_env or "ANTHROPIC_API_KEY"
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise ValueError(f"API key not found in environment variable: {api_key_env}")

        # Import and create client
        from anthropic import AsyncAnthropic
        self._client = AsyncAnthropic(
            api_key=api_key,
            timeout=config.timeout_seconds
        )

    async def invoke(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Invoke Anthropic API."""
        request_params = self._build_request(messages, tools, **kwargs)
        response = await self._client.messages.create(**request_params)

        # Extract content and tool calls
        content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCallRequest(
                    id=block.id,
                    name=block.name,
                    arguments=block.input if isinstance(block.input, dict) else {}
                ))

        usage = {
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.input_tokens + response.usage.output_tokens
        }

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=response.stop_reason,
            usage=usage,
            model=response.model
        )

    async def stream(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any
    ) -> AsyncIterator[LLMChunk]:
        """Stream Anthropic API response."""
        request_params = self._build_request(messages, tools, **kwargs)

        async with self._client.messages.stream(**request_params) as stream:
            current_tool: Optional[Dict[str, Any]] = None

            async for event in stream:
                if event.type == "content_block_start":
                    if hasattr(event.content_block, "type"):
                        if event.content_block.type == "tool_use":
                            current_tool = {
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input": ""
                            }
                elif event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        yield LLMChunk(content=event.delta.text)
                    elif hasattr(event.delta, "partial_json") and current_tool:
                        current_tool["input"] += event.delta.partial_json
                elif event.type == "content_block_stop":
                    if current_tool:
                        try:
                            args = json.loads(current_tool["input"])
                        except json.JSONDecodeError:
                            args = {}
                        yield LLMChunk(
                            content="",
                            tool_calls=[ToolCallRequest(
                                id=current_tool["id"],
                                name=current_tool["name"],
                                arguments=args
                            )]
                        )
                        current_tool = None
                elif event.type == "message_stop":
                    yield LLMChunk(content="", done=True)

    def _build_request(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Build Anthropic API request parameters."""
        # Separate system message from other messages
        system_content = ""
        api_messages = []

        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
            elif msg.role == "tool":
                # Anthropic uses tool_result in user messages
                api_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content
                    }]
                })
            elif msg.role == "assistant" and msg.tool_calls:
                # Add assistant message with tool use
                content_blocks = []
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments
                    })
                api_messages.append({
                    "role": "assistant",
                    "content": content_blocks
                })
            else:
                api_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        params: Dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature
        }

        if system_content:
            params["system"] = system_content

        # Add tools
        if tools:
            params["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters
                }
                for tool in tools
            ]

        params.update(kwargs)
        return params

    def get_model_name(self) -> str:
        return self._model
