"""Google Gemini LLM adapter."""

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


class GoogleAdapter(LLMAdapter):
    """Adapter for Google Gemini API."""

    def __init__(self, config: LLMConfig):
        """
        Initialize the Google adapter.

        Args:
            config: LLM configuration.
        """
        self._config = config
        self._model = config.model
        self._temperature = config.temperature
        self._max_tokens = config.max_tokens

        # Get API key from environment
        api_key_env = config.api_key_env or "GOOGLE_API_KEY"
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise ValueError(f"API key not found in environment variable: {api_key_env}")

        # Import and configure
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._genai = genai
        self._model_instance = genai.GenerativeModel(self._model)

    async def invoke(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Invoke Google Gemini API."""
        # Convert messages to Gemini format
        history, latest_message = self._prepare_messages(messages)

        # Set up generation config
        generation_config = self._genai.GenerationConfig(
            temperature=self._temperature,
            max_output_tokens=self._max_tokens
        )

        # Start chat
        chat = self._model_instance.start_chat(history=history)

        # Convert tools
        gemini_tools = self._convert_tools(tools) if tools else None

        # Send message
        response = await chat.send_message_async(
            latest_message,
            generation_config=generation_config,
            tools=gemini_tools
        )

        # Extract content and tool calls
        content = ""
        tool_calls = []

        for part in response.parts:
            if hasattr(part, "text"):
                content += part.text
            elif hasattr(part, "function_call"):
                fc = part.function_call
                tool_calls.append(ToolCallRequest(
                    id=f"call_{fc.name}_{len(tool_calls)}",
                    name=fc.name,
                    arguments=dict(fc.args) if fc.args else {}
                ))

        # Usage info
        usage = {}
        if hasattr(response, "usage_metadata"):
            usage = {
                "prompt_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
                "completion_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
                "total_tokens": getattr(response.usage_metadata, "total_token_count", 0)
            }

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason="stop",
            usage=usage,
            model=self._model
        )

    async def stream(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any
    ) -> AsyncIterator[LLMChunk]:
        """Stream Google Gemini API response."""
        history, latest_message = self._prepare_messages(messages)

        generation_config = self._genai.GenerationConfig(
            temperature=self._temperature,
            max_output_tokens=self._max_tokens
        )

        chat = self._model_instance.start_chat(history=history)
        gemini_tools = self._convert_tools(tools) if tools else None

        response = await chat.send_message_async(
            latest_message,
            generation_config=generation_config,
            tools=gemini_tools,
            stream=True
        )

        async for chunk in response:
            for part in chunk.parts:
                if hasattr(part, "text"):
                    yield LLMChunk(content=part.text)
                elif hasattr(part, "function_call"):
                    fc = part.function_call
                    yield LLMChunk(
                        content="",
                        tool_calls=[ToolCallRequest(
                            id=f"call_{fc.name}",
                            name=fc.name,
                            arguments=dict(fc.args) if fc.args else {}
                        )]
                    )

        yield LLMChunk(content="", done=True)

    def _prepare_messages(self, messages: List[Message]) -> tuple:
        """Convert messages to Gemini format."""
        history = []
        latest_message = ""
        system_instruction = ""

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "user":
                if msg == messages[-1]:
                    latest_message = msg.content
                else:
                    history.append({
                        "role": "user",
                        "parts": [msg.content]
                    })
            elif msg.role == "assistant":
                history.append({
                    "role": "model",
                    "parts": [msg.content]
                })

        return history, latest_message

    def _convert_tools(self, tools: List[ToolDefinition]) -> List[Any]:
        """Convert tool definitions to Gemini format."""
        gemini_tools = []
        for tool in tools:
            gemini_tools.append(
                self._genai.protos.Tool(
                    function_declarations=[
                        self._genai.protos.FunctionDeclaration(
                            name=tool.name,
                            description=tool.description,
                            parameters=self._genai.protos.Schema(
                                type=self._genai.protos.Type.OBJECT,
                                properties={
                                    k: self._genai.protos.Schema(type=self._genai.protos.Type.STRING)
                                    for k in tool.parameters.get("properties", {}).keys()
                                }
                            )
                        )
                    ]
                )
            )
        return gemini_tools

    def get_model_name(self) -> str:
        return self._model
