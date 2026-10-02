"""Base classes and protocols for LLM integration."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A message in a conversation."""

    role: str  # "user", "assistant", "system", "tool"
    content: str
    name: str | None = None
    tool_calls: list["ToolCallRequest"] | None = None
    tool_call_id: str | None = None

    @classmethod
    def user(cls, content: str) -> "Message":
        return cls(role="user", content=content)

    @classmethod
    def assistant(
        cls, content: str, tool_calls: list["ToolCallRequest"] | None = None
    ) -> "Message":
        return cls(role="assistant", content=content, tool_calls=tool_calls)

    @classmethod
    def system(cls, content: str) -> "Message":
        return cls(role="system", content=content)

    @classmethod
    def tool(cls, content: str, tool_call_id: str, name: str | None = None) -> "Message":
        return cls(role="tool", content=content, tool_call_id=tool_call_id, name=name)


class ToolCallRequest(BaseModel):
    """A request to call a tool from the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


class ToolDefinition(BaseModel):
    """Definition of a tool available to the LLM."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_json_schema(
        cls, name: str, description: str, schema: dict[str, Any]
    ) -> "ToolDefinition":
        """Create from JSON Schema."""
        return cls(name=name, description=description, parameters=schema)


class LLMResponse(BaseModel):
    """Response from an LLM invocation."""

    content: str
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    model: str | None = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMChunk(BaseModel):
    """A streaming chunk from an LLM."""

    content: str = ""
    tool_calls: list[ToolCallRequest] | None = None
    finish_reason: str | None = None
    done: bool = False


class LLMAdapter(ABC):
    """Abstract base class for LLM adapters."""

    @abstractmethod
    async def invoke(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None, **kwargs: Any
    ) -> LLMResponse:
        """
        Invoke the LLM with messages.

        Args:
            messages: List of conversation messages.
            tools: Optional list of available tools.
            **kwargs: Additional provider-specific options.

        Returns:
            LLM response with content and optional tool calls.
        """
        pass

    @abstractmethod
    def stream(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None, **kwargs: Any
    ) -> AsyncIterator[LLMChunk]:
        """
        Stream the LLM response.

        Args:
            messages: List of conversation messages.
            tools: Optional list of available tools.
            **kwargs: Additional provider-specific options.

        Yields:
            LLM chunks as they are generated.
        """
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the model name."""
        pass

    def supports_tools(self) -> bool:
        """Check if this adapter supports tool calling."""
        return True

    def supports_streaming(self) -> bool:
        """Check if this adapter supports streaming."""
        return True
