"""
MAOS Google LLM Adapter.

Uses LangChain's ChatGoogleGenerativeAI for Google Gemini API integration.
"""

from collections.abc import AsyncIterator

import structlog
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_google_genai import ChatGoogleGenerativeAI

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


class GoogleAdapter(BaseLLMAdapter):
    """Google Gemini LLM adapter using LangChain."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ):
        super().__init__(model, temperature, max_tokens)
        self._client = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

    def _convert_messages(self, messages: list[Message]) -> list[BaseMessage]:
        """Convert messages to LangChain format."""
        result: list[BaseMessage] = []
        for msg in messages:
            content = msg.content or ""
            if msg.role == "system":
                result.append(SystemMessage(content=content))
            elif msg.role == "user":
                result.append(HumanMessage(content=content))
            elif msg.role == "assistant":
                result.append(AIMessage(content=content))
        return result

    async def invoke(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Invoke using LangChain ChatGoogleGenerativeAI."""
        try:
            lc_messages = self._convert_messages(messages)

            log.debug("google_invoke", model=self._model, message_count=len(messages))

            # Note: Tool calling support varies by model
            client = self._client
            if tools:
                lc_tools = [t.to_openai_format() for t in tools]
                client = client.bind_tools(lc_tools)

            response = await client.ainvoke(lc_messages)

            content = response.content if isinstance(response.content, str) else ""

            # Parse tool calls if present
            tool_calls = []
            if isinstance(response, AIMessage) and response.tool_calls:
                for tc in response.tool_calls:
                    tool_calls.append(ToolCall(
                        id=tc.get("id", ""),
                        name=tc.get("name", ""),
                        arguments=tc.get("args", {}),
                    ))

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                usage={},
                model=self._model,
                finish_reason="stop" if not tool_calls else "tool_calls",
            )
        except Exception as e:
            log.error("google_error", error=str(e))
            raise LLMError(f"Google API error: {e}") from e

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Stream using LangChain ChatGoogleGenerativeAI."""
        try:
            lc_messages = self._convert_messages(messages)

            log.debug("google_stream", model=self._model, message_count=len(messages))

            client = self._client
            if tools:
                lc_tools = [t.to_openai_format() for t in tools]
                client = client.bind_tools(lc_tools)

            stream = client.astream(lc_messages)

            async for chunk in stream:
                if hasattr(chunk, "content") and chunk.content:
                    yield LLMChunk(content=chunk.content, done=False)

            yield LLMChunk(content="", done=True, finish_reason="stop")

        except Exception as e:
            log.error("google_stream_error", error=str(e))
            raise LLMError(f"Google streaming error: {e}") from e
