"""
MAOS Google LLM Adapter.

Provides Google Generative AI (Gemini) integration.
"""

from collections.abc import AsyncIterator

import structlog

from maos.errors import LLMError
from maos.llm.base import (
    BaseLLMAdapter,
    LLMChunk,
    LLMResponse,
    Message,
    ToolDefinition,
)

log = structlog.get_logger()


class GoogleAdapter(BaseLLMAdapter):
    """Google Generative AI (Gemini) adapter."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ):
        super().__init__(model, temperature, max_tokens)
        self._api_key = api_key
        self._client = None

    async def _get_client(self):
        """Lazy initialization of Google client."""
        if self._client is None:
            try:
                import google.generativeai as genai

                if self._api_key:
                    genai.configure(api_key=self._api_key)

                generation_config = {
                    "temperature": self._temperature,
                }
                if self._max_tokens:
                    generation_config["max_output_tokens"] = self._max_tokens

                self._client = genai.GenerativeModel(
                    model_name=self._model,
                    generation_config=generation_config,
                )
            except ImportError:
                raise LLMError("google-generativeai package not installed")
        return self._client

    def _convert_messages(self, messages: list[Message]) -> tuple[str | None, list[dict]]:
        """Convert messages to Google format."""
        system_prompt = None
        history = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
                continue

            role = "model" if msg.role == "assistant" else "user"

            # Handle tool responses as user messages
            if msg.role == "tool":
                role = "user"

            history.append({
                "role": role,
                "parts": [msg.content or ""],
            })

        return system_prompt, history

    async def invoke(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Invoke Google Generative AI."""
        try:
            client = await self._get_client()
            system_prompt, history = self._convert_messages(messages)

            log.debug("google_invoke", model=self._model, message_count=len(messages))

            # Create chat session
            chat = client.start_chat(history=history[:-1] if history else [])

            # Get last message
            last_message = history[-1]["parts"][0] if history else ""

            # Add system prompt to first message if present
            if system_prompt and last_message:
                last_message = f"{system_prompt}\n\n{last_message}"

            response = await chat.send_message_async(last_message)

            # Extract text from response
            text = response.text if response.text else ""

            return LLMResponse(
                content=text,
                tool_calls=[],  # Google function calling handled separately
                usage={},  # Usage info not readily available
                model=self._model,
                finish_reason="stop",
            )
        except Exception as e:
            log.error("google_error", error=str(e))
            raise LLMError(f"Google API error: {e}")

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Stream Google response."""
        try:
            client = await self._get_client()
            system_prompt, history = self._convert_messages(messages)

            log.debug("google_stream", model=self._model, message_count=len(messages))

            chat = client.start_chat(history=history[:-1] if history else [])
            last_message = history[-1]["parts"][0] if history else ""

            if system_prompt and last_message:
                last_message = f"{system_prompt}\n\n{last_message}"

            response = await chat.send_message_async(last_message, stream=True)

            async for chunk in response:
                if chunk.text:
                    yield LLMChunk(content=chunk.text, done=False)

            yield LLMChunk(content="", done=True)
        except Exception as e:
            log.error("google_stream_error", error=str(e))
            raise LLMError(f"Google streaming error: {e}")
