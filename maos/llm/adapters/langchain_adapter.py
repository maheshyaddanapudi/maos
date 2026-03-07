"""LangChain-based LLM adapters using official provider packages."""

import os
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from maos.config.models import LLMConfig, LLMProvider
from maos.llm.base import (
    LLMAdapter,
    LLMChunk,
    LLMResponse,
    Message,
    ToolCallRequest,
    ToolDefinition,
)
from maos.resilience import retry_with_backoff


def _to_langchain_messages(messages: list[Message]) -> list[BaseMessage]:
    """Convert our Message format to LangChain messages."""
    result = []
    for msg in messages:
        if msg.role == "system":
            result.append(SystemMessage(content=msg.content))
        elif msg.role == "user":
            result.append(HumanMessage(content=msg.content, name=msg.name))
        elif msg.role == "assistant":
            # Handle tool calls in assistant messages
            if msg.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "name": tc.name,
                        "args": tc.arguments,
                    }
                    for tc in msg.tool_calls
                ]
                result.append(AIMessage(content=msg.content or "", tool_calls=tool_calls))
            else:
                result.append(AIMessage(content=msg.content, name=msg.name))
        elif msg.role == "tool":
            result.append(
                ToolMessage(content=msg.content, tool_call_id=msg.tool_call_id or "", name=msg.name)
            )
    return result


def _to_langchain_tools(tools: list[ToolDefinition]) -> list[dict]:
    """Convert our ToolDefinition format to LangChain tool format."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]


class LangChainAdapter(LLMAdapter):
    """Adapter that wraps LangChain chat models."""

    def __init__(self, chat_model: BaseChatModel, config: LLMConfig):
        """
        Initialize with a LangChain chat model.

        Args:
            chat_model: The LangChain chat model instance.
            config: LLM configuration.
        """
        self._chat_model = chat_model
        self._config = config

    async def invoke(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None, **kwargs: Any
    ) -> LLMResponse:
        """Invoke the LangChain model."""
        lc_messages = _to_langchain_messages(messages)

        # Bind tools if provided
        model = self._chat_model
        if tools:
            model = model.bind_tools(_to_langchain_tools(tools))

        # Invoke with retry
        response = await retry_with_backoff(
            model.ainvoke,
            lc_messages,
            max_retries=3,
            base_delay=1.0,
            **kwargs,
        )

        # Extract tool calls
        tool_calls = []
        if hasattr(response, "tool_calls") and response.tool_calls:
            for tc in response.tool_calls:
                tool_calls.append(
                    ToolCallRequest(
                        id=tc.get("id", ""), name=tc.get("name", ""), arguments=tc.get("args", {})
                    )
                )

        # Extract usage if available
        usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = {
                "prompt_tokens": response.usage_metadata.get("input_tokens", 0),
                "completion_tokens": response.usage_metadata.get("output_tokens", 0),
                "total_tokens": response.usage_metadata.get("total_tokens", 0),
            }

        return LLMResponse(
            content=response.content if isinstance(response.content, str) else "",
            tool_calls=tool_calls,
            finish_reason="stop" if not tool_calls else "tool_calls",
            usage=usage,
            model=self._config.model,
        )

    async def stream(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None, **kwargs: Any
    ) -> AsyncIterator[LLMChunk]:
        """Stream the LangChain model response."""
        lc_messages = _to_langchain_messages(messages)

        # Bind tools if provided
        model = self._chat_model
        if tools:
            model = model.bind_tools(_to_langchain_tools(tools))

        # Stream with retry on initial connection
        async def _start_stream():
            return model.astream(lc_messages, **kwargs)

        astream = await retry_with_backoff(
            _start_stream,
            max_retries=3,
            base_delay=1.0,
        )

        async for chunk in astream:
            content = (
                chunk.content
                if isinstance(chunk.content, str)
                else ""
            )
            yield LLMChunk(
                content=content,
                tool_calls=None,
                finish_reason=None,
                done=False,
            )

        yield LLMChunk(
            content="",
            tool_calls=None,
            finish_reason="stop",
            done=True,
        )

    def get_model_name(self) -> str:
        """Get the model name."""
        return self._config.model

    @property
    def chat_model(self) -> BaseChatModel:
        """Get the underlying LangChain chat model for direct use with LangGraph."""
        return self._chat_model


def create_langchain_model(config: LLMConfig) -> BaseChatModel:
    """
    Create a LangChain chat model from configuration.

    This uses the official LangChain provider packages:
    - langchain-openai for OpenAI
    - langchain-anthropic for Anthropic
    - langchain-google-genai for Google
    - langchain-community for Ollama

    Args:
        config: LLM configuration.

    Returns:
        A LangChain BaseChatModel instance.
    """
    # Get API key
    api_key_env = config.api_key_env
    api_key = os.environ.get(api_key_env) if api_key_env else None

    common_kwargs = {
        "temperature": config.temperature,
    }
    if config.max_tokens:
        common_kwargs["max_tokens"] = config.max_tokens

    if config.provider == LLMProvider.OPENAI:
        from langchain_openai import ChatOpenAI

        if not api_key_env:
            api_key = os.environ.get("OPENAI_API_KEY")

        return ChatOpenAI(
            model=config.model,
            api_key=api_key,
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            **common_kwargs,
        )

    elif config.provider == LLMProvider.ANTHROPIC:
        from langchain_anthropic import ChatAnthropic

        if not api_key_env:
            api_key = os.environ.get("ANTHROPIC_API_KEY")

        return ChatAnthropic(
            model=config.model, api_key=api_key, timeout=config.timeout_seconds, **common_kwargs
        )

    elif config.provider == LLMProvider.GOOGLE:
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not api_key_env:
            api_key = os.environ.get("GOOGLE_API_KEY")

        return ChatGoogleGenerativeAI(model=config.model, google_api_key=api_key, **common_kwargs)

    elif config.provider == LLMProvider.OLLAMA:
        from langchain_community.chat_models import ChatOllama

        return ChatOllama(
            model=config.model,
            base_url=config.base_url or "http://localhost:11434",
            **common_kwargs,
        )

    elif config.provider == LLMProvider.OPENAI_COMPATIBLE:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=config.model,
            api_key=api_key or "not-needed",
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            **common_kwargs,
        )

    elif config.provider == LLMProvider.AZURE_OPENAI:
        from langchain_openai import AzureChatOpenAI

        if not api_key_env:
            api_key = os.environ.get("AZURE_OPENAI_API_KEY")

        azure_endpoint = config.base_url or os.environ.get("AZURE_OPENAI_ENDPOINT", "")

        return AzureChatOpenAI(
            azure_deployment=config.model,
            api_key=api_key,
            azure_endpoint=azure_endpoint,
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            timeout=config.timeout_seconds,
            **common_kwargs,
        )

    else:
        raise ValueError(f"Unsupported LLM provider: {config.provider}")


def create_adapter_from_config(config: LLMConfig) -> LangChainAdapter:
    """
    Create a LangChainAdapter from configuration.

    Args:
        config: LLM configuration.

    Returns:
        A LangChainAdapter wrapping the appropriate chat model.
    """
    chat_model = create_langchain_model(config)
    return LangChainAdapter(chat_model, config)
