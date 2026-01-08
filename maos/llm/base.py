"""Base classes and protocols for LLM integration."""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A message in a conversation."""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List["ToolCallRequest"]] = None
    tool_call_id: Optional[str] = None

    @classmethod
    def user(cls, content: str) -> "Message":
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str, tool_calls: Optional[List["ToolCallRequest"]] = None) -> "Message":
        return cls(role="assistant", content=content, tool_calls=tool_calls)

    @classmethod
    def system(cls, content: str) -> "Message":
        return cls(role="system", content=content)

    @classmethod
    def tool(cls, content: str, tool_call_id: str, name: Optional[str] = None) -> "Message":
        return cls(role="tool", content=content, tool_call_id=tool_call_id, name=name)


class ToolCallRequest(BaseModel):
    """A request to call a tool from the LLM."""
    id: str
    name: str
    arguments: Dict[str, Any]


class ToolDefinition(BaseModel):
    """Definition of a tool available to the LLM."""
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_json_schema(
        cls,
        name: str,
        description: str,
        schema: Dict[str, Any]
    ) -> "ToolDefinition":
        """Create from JSON Schema."""
        return cls(
            name=name,
            description=description,
            parameters=schema
        )


class LLMResponse(BaseModel):
    """Response from an LLM invocation."""
    content: str
    tool_calls: List[ToolCallRequest] = Field(default_factory=list)
    finish_reason: Optional[str] = None
    usage: Dict[str, int] = Field(default_factory=dict)
    model: Optional[str] = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMChunk(BaseModel):
    """A streaming chunk from an LLM."""
    content: str = ""
    tool_calls: Optional[List[ToolCallRequest]] = None
    finish_reason: Optional[str] = None
    done: bool = False


class LLMAdapter(ABC):
    """Abstract base class for LLM adapters."""

    @abstractmethod
    async def invoke(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any
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
    async def stream(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        **kwargs: Any
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
        pass

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
