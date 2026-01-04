"""
Unit tests for LLM module.
"""

from unittest.mock import patch

import pytest

from maos.config.models import LLMConfig, LLMProvider
from maos.errors import ConfigError
from maos.llm.base import (
    LLMResponse,
    Message,
    ToolCall,
    ToolDefinition,
)
from maos.llm.factory import LLMFactory
from maos.llm.registry import LLMRegistry
from tests.mocks.llm import MockLLMAdapter


class TestMessage:
    """Tests for Message dataclass."""

    def test_user_message(self):
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_calls is None
        assert msg.tool_call_id is None

    def test_assistant_message_with_tool_calls(self):
        tool_calls = [
            ToolCall(id="tc1", name="search", arguments={"q": "test"})
        ]
        msg = Message(role="assistant", content=None, tool_calls=tool_calls)
        assert msg.role == "assistant"
        assert msg.tool_calls == tool_calls

    def test_tool_result_message(self):
        msg = Message(role="tool", content="Result", tool_call_id="tc1")
        assert msg.role == "tool"
        assert msg.tool_call_id == "tc1"


class TestToolDefinition:
    """Tests for ToolDefinition."""

    def test_tool_definition(self):
        tool = ToolDefinition(
            name="search",
            description="Search the web",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                }
            }
        )
        assert tool.name == "search"
        assert "query" in tool.parameters["properties"]


class TestLLMResponse:
    """Tests for LLMResponse."""

    def test_text_response(self):
        response = LLMResponse(
            content="Hello, world!",
            tool_calls=[],
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            model="gpt-4",
            finish_reason="stop",
        )
        assert response.content == "Hello, world!"
        assert response.finish_reason == "stop"

    def test_tool_call_response(self):
        response = LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(id="tc1", name="search", arguments={"q": "test"})
            ],
            usage={},
            model="gpt-4",
            finish_reason="tool_calls",
        )
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "search"


class TestMockLLMAdapter:
    """Tests for MockLLMAdapter."""

    @pytest.mark.asyncio
    async def test_invoke_returns_response(self):
        adapter = MockLLMAdapter(responses=["Hello!"])
        messages = [Message(role="user", content="Hi")]

        response = await adapter.invoke(messages)

        assert response.content == "Hello!"
        assert response.model == "mock-model"

    @pytest.mark.asyncio
    async def test_invoke_cycles_responses(self):
        adapter = MockLLMAdapter(responses=["First", "Second"])
        messages = [Message(role="user", content="Hi")]

        r1 = await adapter.invoke(messages)
        r2 = await adapter.invoke(messages)

        assert r1.content == "First"
        assert r2.content == "Second"

    @pytest.mark.asyncio
    async def test_invoke_with_tool_calls(self):
        tool_calls = [ToolCall(id="tc1", name="search", arguments={})]
        adapter = MockLLMAdapter(responses=["Done"], tool_calls=tool_calls)
        messages = [Message(role="user", content="Search")]

        response = await adapter.invoke(messages)

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "search"

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self):
        adapter = MockLLMAdapter(responses=["Hello world"])
        messages = [Message(role="user", content="Hi")]

        chunks = []
        async for chunk in adapter.stream(messages):
            chunks.append(chunk)

        assert len(chunks) > 1  # Multiple chunks
        assert chunks[-1].done  # Last chunk is done

    def test_call_recording(self):
        adapter = MockLLMAdapter()
        adapter.reset()

        assert adapter.get_calls() == []

    @pytest.mark.asyncio
    async def test_assert_called(self):
        adapter = MockLLMAdapter()

        with pytest.raises(AssertionError):
            adapter.assert_called()

        await adapter.invoke([Message(role="user", content="Hi")])
        adapter.assert_called()

    @pytest.mark.asyncio
    async def test_assert_called_times(self):
        adapter = MockLLMAdapter()

        await adapter.invoke([Message(role="user", content="Hi")])
        await adapter.invoke([Message(role="user", content="Hi")])

        adapter.assert_called_times(2)


class TestLLMFactory:
    """Tests for LLMFactory."""

    def test_create_openai_adapter(self):
        factory = LLMFactory()
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4o-mini",
        )

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            adapter = factory.create(config)

        from maos.llm.adapters.openai import OpenAIAdapter
        assert isinstance(adapter, OpenAIAdapter)

    def test_create_anthropic_adapter(self):
        factory = LLMFactory()
        config = LLMConfig(
            provider=LLMProvider.ANTHROPIC,
            model="claude-3-sonnet-20240229",
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            adapter = factory.create(config)

        from maos.llm.adapters.anthropic import AnthropicAdapter
        assert isinstance(adapter, AnthropicAdapter)

    def test_create_ollama_adapter(self):
        factory = LLMFactory()
        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="llama3:8b",
        )

        adapter = factory.create(config)

        from maos.llm.adapters.ollama import OllamaAdapter
        assert isinstance(adapter, OllamaAdapter)


class TestLLMRegistry:
    """Tests for LLMRegistry."""

    def test_register_and_get(self):
        registry = LLMRegistry()
        adapter = MockLLMAdapter()

        registry.register_adapter("test", adapter)

        assert registry.get("test") is adapter

    def test_get_nonexistent(self):
        registry = LLMRegistry()
        assert registry.get("nonexistent") is None

    def test_get_or_default_with_existing(self):
        registry = LLMRegistry()
        adapter = MockLLMAdapter()
        default = MockLLMAdapter()

        registry.register_adapter("test", adapter)
        registry.register_adapter("default", default)

        assert registry.get_or_default("test") is adapter

    def test_get_or_default_fallback(self):
        registry = LLMRegistry()
        default = MockLLMAdapter()

        registry.register_adapter("default", default)

        assert registry.get_or_default("nonexistent") is default
        assert registry.get_or_default(None) is default

    def test_get_or_default_no_default(self):
        registry = LLMRegistry()

        with pytest.raises(ConfigError):
            registry.get_or_default("test")

    def test_list_names(self):
        registry = LLMRegistry()
        registry.register_adapter("a", MockLLMAdapter())
        registry.register_adapter("b", MockLLMAdapter())

        names = registry.list_names()

        assert "a" in names
        assert "b" in names

    def test_build_from_configs(self):
        registry = LLMRegistry()
        configs = {
            "ollama": LLMConfig(
                provider=LLMProvider.OLLAMA,
                model="llama3:8b",
            )
        }

        registry.build(configs)

        assert registry.get("ollama") is not None
