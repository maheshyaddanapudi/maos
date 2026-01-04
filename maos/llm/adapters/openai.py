"""
MAOS OpenAI LLM Adapter.

Uses LangChain's ChatOpenAI for OpenAI API integration.
"""

import json
from collections.abc import AsyncIterator

import structlog
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI

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
    """OpenAI LLM adapter using LangChain."""

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
        self._client = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
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
                if msg.tool_calls:
                    tool_calls = [
                        {
                            "id": tc.id,
                            "name": tc.name,
                            "args": tc.arguments,
                        }
                        for tc in msg.tool_calls
                    ]
                    result.append(AIMessage(content=content, tool_calls=tool_calls))
                else:
                    result.append(AIMessage(content=content))
            elif msg.role == "tool":
                result.append(ToolMessage(
                    content=content,
                    tool_call_id=msg.tool_call_id or "",
                ))
        return result

    def _convert_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        """Convert tools to LangChain format."""
        return [t.to_openai_format() for t in tools]

    def _parse_tool_calls(self, ai_message: AIMessage) -> list[ToolCall]:
        """Parse tool calls from AIMessage."""
        if not ai_message.tool_calls:
            return []

        result = []
        for tc in ai_message.tool_calls:
            result.append(ToolCall(
                id=tc.get("id", ""),
                name=tc.get("name", ""),
                arguments=tc.get("args", {}),
            ))
        return result

    async def invoke(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Invoke using LangChain ChatOpenAI."""
        try:
            lc_messages = self._convert_messages(messages)

            log.debug("openai_invoke", model=self._model, message_count=len(messages))

            if tools:
                lc_tools = self._convert_tools(tools)
                client_with_tools = self._client.bind_tools(lc_tools)
                response = await client_with_tools.ainvoke(lc_messages)
            else:
                response = await self._client.ainvoke(lc_messages)

            # Extract response
            content = response.content if isinstance(response.content, str) else ""
            tool_calls = self._parse_tool_calls(response) if isinstance(response, AIMessage) else []

            # Get usage if available
            usage = {}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = {
                    "prompt_tokens": response.usage_metadata.get("input_tokens", 0),
                    "completion_tokens": response.usage_metadata.get("output_tokens", 0),
                    "total_tokens": response.usage_metadata.get("total_tokens", 0),
                }

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                usage=usage,
                model=self._model,
                finish_reason="stop" if not tool_calls else "tool_calls",
            )
        except Exception as e:
            log.error("openai_error", error=str(e))
            raise LLMError(f"OpenAI API error: {e}") from e

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Stream using LangChain ChatOpenAI."""
        try:
            lc_messages = self._convert_messages(messages)

            log.debug("openai_stream", model=self._model, message_count=len(messages))

            if tools:
                lc_tools = self._convert_tools(tools)
                client_with_tools = self._client.bind_tools(lc_tools)
                stream = client_with_tools.astream(lc_messages)
            else:
                stream = self._client.astream(lc_messages)

            accumulated_tool_calls: dict[str, dict] = {}
            full_content = ""

            async for chunk in stream:
                if hasattr(chunk, "content") and chunk.content:
                    full_content += chunk.content
                    yield LLMChunk(content=chunk.content, done=False)

                # Accumulate tool calls
                if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                    for tc_chunk in chunk.tool_call_chunks:
                        tc_id = tc_chunk.get("id") or tc_chunk.get("index", 0)
                        if tc_id not in accumulated_tool_calls:
                            accumulated_tool_calls[tc_id] = {
                                "id": tc_chunk.get("id", ""),
                                "name": tc_chunk.get("name", ""),
                                "arguments": "",
                            }
                        if tc_chunk.get("args"):
                            accumulated_tool_calls[tc_id]["arguments"] += tc_chunk["args"]

            # Final chunk
            tool_calls = None
            if accumulated_tool_calls:
                tool_calls = []
                for tc in accumulated_tool_calls.values():
                    try:
                        args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    except json.JSONDecodeError:
                        args = {}
                    tool_calls.append(ToolCall(
                        id=tc["id"],
                        name=tc["name"],
                        arguments=args,
                    ))

            yield LLMChunk(
                content="",
                done=True,
                tool_calls=tool_calls,
                finish_reason="stop" if not tool_calls else "tool_calls",
            )

        except Exception as e:
            log.error("openai_stream_error", error=str(e))
            raise LLMError(f"OpenAI streaming error: {e}") from e
