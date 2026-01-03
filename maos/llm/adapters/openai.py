"""OpenAI LLM adapter."""

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


class OpenAIAdapter(LLMAdapter):
    """Adapter for OpenAI and OpenAI-compatible APIs."""

    def __init__(self, config: LLMConfig):
        """
        Initialize the OpenAI adapter.

        Args:
            config: LLM configuration.
        """
        self._config = config
        self._model = config.model
        self._temperature = config.temperature
        self._max_tokens = config.max_tokens

        # Get API key from environment
        api_key_env = config.api_key_env or "OPENAI_API_KEY"
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise ValueError(f"API key not found in environment variable: {api_key_env}")

        # Import and create client
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=config.base_url,
            timeout=config.timeout_seconds
        )

    async def invoke(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Invoke OpenAI API."""
        request_params = self._build_request(messages, tools, **kwargs)
        response = await self._client.chat.completions.create(**request_params)

        # Extract response
        choice = response.choices[0]
        content = choice.message.content or ""
        tool_calls = []

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCallRequest(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args
                ))

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
            usage=usage,
            model=response.model
        )

    async def stream(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any
    ) -> AsyncIterator[LLMChunk]:
        """Stream OpenAI API response."""
        request_params = self._build_request(messages, tools, stream=True, **kwargs)
        response = await self._client.chat.completions.create(**request_params)

        current_tool_calls: Dict[int, Dict[str, Any]] = {}

        async for chunk in response:
            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            content = ""
            tool_calls = None
            finish_reason = choice.finish_reason

            if choice.delta.content:
                content = choice.delta.content

            if choice.delta.tool_calls:
                for tc in choice.delta.tool_calls:
                    idx = tc.index
                    if idx not in current_tool_calls:
                        current_tool_calls[idx] = {
                            "id": tc.id or "",
                            "name": tc.function.name if tc.function else "",
                            "arguments": ""
                        }
                    if tc.function and tc.function.arguments:
                        current_tool_calls[idx]["arguments"] += tc.function.arguments

            yield LLMChunk(
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                done=finish_reason is not None
            )

        # Yield final tool calls if any
        if current_tool_calls:
            final_tool_calls = []
            for tc_data in current_tool_calls.values():
                try:
                    args = json.loads(tc_data["arguments"])
                except json.JSONDecodeError:
                    args = {}
                final_tool_calls.append(ToolCallRequest(
                    id=tc_data["id"],
                    name=tc_data["name"],
                    arguments=args
                ))
            yield LLMChunk(
                content="",
                tool_calls=final_tool_calls,
                done=True
            )

    def _build_request(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        stream: bool = False,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Build OpenAI API request parameters."""
        # Convert messages
        api_messages = []
        for msg in messages:
            api_msg: Dict[str, Any] = {
                "role": msg.role,
                "content": msg.content
            }
            if msg.name:
                api_msg["name"] = msg.name
            if msg.tool_call_id:
                api_msg["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                api_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in msg.tool_calls
                ]
            api_messages.append(api_msg)

        params: Dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "temperature": self._temperature,
            "stream": stream
        }

        if self._max_tokens:
            params["max_tokens"] = self._max_tokens

        # Add tools
        if tools:
            params["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters
                    }
                }
                for tool in tools
            ]

        # Merge any additional kwargs
        params.update(kwargs)

        return params

    def get_model_name(self) -> str:
        return self._model
