"""
MAOS Ollama LLM Adapter.

Provides Ollama (local LLM) integration via OpenAI-compatible API.
"""

from collections.abc import AsyncIterator

import structlog

from maos.llm.adapters.openai import OpenAIAdapter
from maos.llm.base import (
    LLMChunk,
    LLMResponse,
    Message,
    ToolDefinition,
)

log = structlog.get_logger()


class OllamaAdapter(OpenAIAdapter):
    """Ollama adapter using OpenAI-compatible API."""

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434/v1",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        timeout: float = 120.0,  # Longer timeout for local inference
    ):
        # Ollama doesn't require an API key but OpenAI client needs something
        super().__init__(
            model=model,
            api_key="ollama",  # Dummy key
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        log.debug("ollama_adapter_init", model=model, base_url=base_url)

    async def invoke(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Invoke Ollama via OpenAI-compatible API."""
        log.debug("ollama_invoke", model=self._model)
        return await super().invoke(messages, tools)

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Stream Ollama response."""
        log.debug("ollama_stream", model=self._model)
        async for chunk in super().stream(messages, tools):
            yield chunk
