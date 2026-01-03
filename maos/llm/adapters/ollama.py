"""Ollama LLM adapter (OpenAI-compatible)."""

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


class OllamaAdapter(LLMAdapter):
    """Adapter for Ollama (uses OpenAI-compatible API)."""

    def __init__(self, config: LLMConfig):
        """
        Initialize the Ollama adapter.

        Args:
            config: LLM configuration.
        """
        self._config = config
        self._model = config.model
        self._temperature = config.temperature
        self._max_tokens = config.max_tokens

        # Ollama default base URL
        base_url = config.base_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

        # Ensure we use the /v1 endpoint for OpenAI compatibility
        if not base_url.endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1"

        # Import and create client (uses OpenAI client)
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(
            api_key="ollama",  # Ollama doesn't require an API key
            base_url=base_url,
            timeout=config.timeout_seconds
        )

    async def invoke(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Invoke Ollama API."""
        request_params = self._build_request(messages, tools, **kwargs)
        response = await self._client.chat.completions.create(**request_params)

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
        """Stream Ollama API response."""
        request_params = self._build_request(messages, tools, stream=True, **kwargs)
        response = await self._client.chat.completions.create(**request_params)

        async for chunk in response:
            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            content = ""

            if choice.delta.content:
                content = choice.delta.content

            yield LLMChunk(
                content=content,
                finish_reason=choice.finish_reason,
                done=choice.finish_reason is not None
            )

    def _build_request(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        stream: bool = False,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Build API request parameters."""
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
            api_messages.append(api_msg)

        params: Dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "temperature": self._temperature,
            "stream": stream
        }

        if self._max_tokens:
            params["max_tokens"] = self._max_tokens

        # Add tools if supported
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

        params.update(kwargs)
        return params

    def get_model_name(self) -> str:
        return self._model

    def supports_tools(self) -> bool:
        # Only some Ollama models support tools
        tool_capable_models = [
            "llama3.1", "llama3.2", "mistral", "mixtral",
            "command-r", "qwen2.5"
        ]
        return any(m in self._model.lower() for m in tool_capable_models)
