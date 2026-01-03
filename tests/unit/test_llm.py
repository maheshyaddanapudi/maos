"""Unit tests for LLM module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from maos.llm.base import LLMAdapter, LLMResponse, Message, ToolCallRequest, ToolDefinition
from maos.llm.factory import LLMFactory
from maos.llm.registry import LLMRegistry
from maos.config.models import LLMConfig, LLMProvider

from tests.mocks.llm import MockLLMAdapter, MockSupervisorLLM


class TestMessage:
    """Tests for Message class."""

    def test_system_message(self):
        """Test creating system message."""
        msg = Message.system("You are a helpful assistant.")
        assert msg.role == "system"
        assert msg.content == "You are a helpful assistant."

    def test_user_message(self):
        """Test creating user message."""
        msg = Message.user("Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"

    def test_assistant_message(self):
        """Test creating assistant message."""
        msg = Message.assistant("Hi there!")
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"

    def test_tool_message(self):
        """Test creating tool message."""
        msg = Message.tool("Result data", tool_call_id="call_123")
        assert msg.role == "tool"
        assert msg.tool_call_id == "call_123"

    def test_model_dump(self):
        """Test converting message to dict."""
        msg = Message(role="user", content="Hello", name="user1")
        d = msg.model_dump(exclude_none=True)
        assert d["role"] == "user"
        assert d["content"] == "Hello"
        assert d["name"] == "user1"


class TestLLMResponse:
    """Tests for LLMResponse class."""

    def test_simple_response(self):
        """Test simple response without tool calls."""
        response = LLMResponse(
            content="Hello!",
            tool_calls=[],
            finish_reason="stop"
        )
        assert response.content == "Hello!"
        assert not response.has_tool_calls

    def test_response_with_tools(self):
        """Test response with tool calls."""
        tool_call = ToolCallRequest(
            id="call_1",
            name="search",
            arguments={"query": "test"}
        )
        response = LLMResponse(
            content="",
            tool_calls=[tool_call],
            finish_reason="tool_calls"
        )
        assert response.has_tool_calls
        assert len(response.tool_calls) == 1


class TestToolDefinition:
    """Tests for ToolDefinition class."""

    def test_tool_definition(self):
        """Test creating tool definition."""
        tool = ToolDefinition(
            name="search",
            description="Search for information",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                }
            }
        )
        assert tool.name == "search"
        assert "query" in tool.parameters["properties"]


class TestMockLLMAdapter:
    """Tests for MockLLMAdapter."""

    @pytest.mark.asyncio
    async def test_invoke(self):
        """Test mock invoke method."""
        adapter = MockLLMAdapter(responses=["Response 1", "Response 2"])

        response1 = await adapter.invoke([Message.user("Hello")])
        assert response1.content == "Response 1"
        assert adapter.call_count == 1

        response2 = await adapter.invoke([Message.user("Hi")])
        assert response2.content == "Response 2"
        assert adapter.call_count == 2

    @pytest.mark.asyncio
    async def test_stream(self):
        """Test mock stream method."""
        adapter = MockLLMAdapter(responses=["Hello world"])

        chunks = []
        async for chunk in adapter.stream([Message.user("Hi")]):
            chunks.append(chunk.content)

        full_response = "".join(chunks)
        assert full_response == "Hello world"

    @pytest.mark.asyncio
    async def test_invoke_history(self):
        """Test that invoke history is recorded."""
        adapter = MockLLMAdapter()

        await adapter.invoke([Message.user("Test")])

        assert len(adapter.invoke_history) == 1
        assert adapter.invoke_history[0]["messages"][0].content == "Test"


class TestMockSupervisorLLM:
    """Tests for MockSupervisorLLM."""

    @pytest.mark.asyncio
    async def test_routing_sequence(self):
        """Test routing through sequence."""
        adapter = MockSupervisorLLM(routing_sequence=["worker1", "worker2", "END"])

        response1 = await adapter.invoke([])
        assert "worker1" in response1.content

        response2 = await adapter.invoke([])
        assert "worker2" in response2.content

        response3 = await adapter.invoke([])
        assert "END" in response3.content


class TestLLMRegistry:
    """Tests for LLMRegistry."""

    def test_register_and_get(self):
        """Test registering and retrieving adapters."""
        registry = LLMRegistry()
        adapter = MockLLMAdapter()

        registry.register_adapter("test", adapter)

        retrieved = registry.get("test")
        assert retrieved is adapter

    def test_get_nonexistent(self):
        """Test getting non-existent adapter."""
        registry = LLMRegistry()
        assert registry.get("nonexistent") is None

    def test_get_or_default(self):
        """Test get_or_default method."""
        registry = LLMRegistry()
        default_adapter = MockLLMAdapter()
        other_adapter = MockLLMAdapter()

        registry.register_adapter("default", default_adapter)
        registry.register_adapter("other", other_adapter)

        # Get specific adapter
        assert registry.get_or_default("other") is other_adapter

        # Fall back to default
        assert registry.get_or_default("nonexistent") is default_adapter
        assert registry.get_or_default(None) is default_adapter

    def test_list_adapters(self):
        """Test listing registered adapters."""
        registry = LLMRegistry()
        registry.register_adapter("adapter1", MockLLMAdapter())
        registry.register_adapter("adapter2", MockLLMAdapter())

        names = registry.list()
        assert set(names) == {"adapter1", "adapter2"}


class TestLLMFactory:
    """Tests for LLMFactory."""

    def test_create_openai(self):
        """Test creating OpenAI adapter."""
        factory = LLMFactory()
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4o-mini"
        )

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            adapter = factory.create(config)
            assert adapter is not None

    def test_create_anthropic(self):
        """Test creating Anthropic adapter."""
        factory = LLMFactory()
        config = LLMConfig(
            provider=LLMProvider.ANTHROPIC,
            model="claude-3-5-sonnet-20241022"
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            adapter = factory.create(config)
            assert adapter is not None

    def test_create_with_custom_api_key_env(self):
        """Test creating adapter with custom API key env var."""
        factory = LLMFactory()
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4o-mini",
            api_key_env="CUSTOM_API_KEY"
        )

        with patch.dict("os.environ", {"CUSTOM_API_KEY": "custom-key"}):
            adapter = factory.create(config)
            assert adapter is not None
