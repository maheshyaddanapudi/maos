"""
MAOS LLM Base Types and Protocol.

Defines the unified interface for LLM adapters.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class ToolCall:
    """A tool call made by the LLM."""
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class Message:
    """A message in the conversation."""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    name: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name:
            d["name"] = self.name
        if self.tool_calls:
            d["tool_calls"] = [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Message":
        """Create from dictionary."""
        tool_calls = None
        if "tool_calls" in d and d["tool_calls"]:
            tool_calls = [
                ToolCall(
                    id=tc.get("id", ""),
                    name=tc.get("name", ""),
                    arguments=tc.get("arguments", {})
                )
                for tc in d["tool_calls"]
            ]
        return cls(
            role=d["role"],
            content=d.get("content", ""),
            name=d.get("name"),
            tool_calls=tool_calls,
            tool_call_id=d.get("tool_call_id"),
        )


@dataclass
class ToolDefinition:
    """Tool definition for LLM function calling."""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI function format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    def to_anthropic_format(self) -> dict[str, Any]:
        """Convert to Anthropic tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }


@dataclass
class LLMResponse:
    """Response from an LLM invocation."""
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    model: str | None = None
    finish_reason: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return bool(self.tool_calls)


@dataclass
class LLMChunk:
    """A chunk from streaming LLM response."""
    content: str = ""
    done: bool = False
    tool_calls: list[ToolCall] | None = None
    finish_reason: str | None = None


@runtime_checkable
class LLMAdapter(Protocol):
    """Protocol for LLM adapters."""

    @property
    def model_name(self) -> str:
        """Get the model name."""
        ...

    async def invoke(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Invoke LLM with messages.

        Args:
            messages: Conversation messages
            tools: Optional tools for function calling

        Returns:
            LLM response
        """
        ...

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Stream LLM response.

        Args:
            messages: Conversation messages
            tools: Optional tools for function calling

        Yields:
            Response chunks
        """
        ...


class BaseLLMAdapter(ABC):
    """Base class for LLM adapters with common functionality."""

    def __init__(self, model: str, temperature: float = 0.7, max_tokens: int | None = None):
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    @property
    def model_name(self) -> str:
        return self._model

    @abstractmethod
    async def invoke(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """Invoke LLM with messages."""
        pass

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """Stream LLM response. Default implementation uses invoke."""
        response = await self.invoke(messages, tools)
        yield LLMChunk(
            content=response.content or "",
            done=True,
            tool_calls=response.tool_calls if response.tool_calls else None,
        )
