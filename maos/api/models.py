"""
MAOS API Models.

Request and response models for the API.
"""

from typing import Any

from pydantic import BaseModel, Field


class MessageModel(BaseModel):
    """A message in the conversation."""
    role: str = Field(..., description="Message role (user, assistant, system, tool)")
    content: str = Field(..., description="Message content")
    name: str | None = Field(None, description="Optional name for the message")
    tool_calls: list[dict[str, Any]] | None = Field(None, description="Tool calls if any")
    tool_call_id: str | None = Field(None, description="Tool call ID for tool responses")


class ChatRequest(BaseModel):
    """Chat request model."""
    messages: list[MessageModel] = Field(..., min_length=1, description="Conversation messages")
    stream: bool = Field(False, description="Whether to stream the response")
    thread_id: str | None = Field(None, description="Thread ID for conversation persistence")
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context")


class ResumeRequest(BaseModel):
    """Resume request for human-in-the-loop."""
    thread_id: str = Field(..., description="Thread ID to resume")
    input: str = Field(..., description="User input to resume with")


class ChatMetadata(BaseModel):
    """Metadata about chat execution."""
    total_tokens: int = Field(0, description="Total tokens used")
    duration_ms: int = Field(0, description="Total duration in milliseconds")
    workers_used: list[str] = Field(default_factory=list, description="Workers that were invoked")
    iterations: int = Field(0, description="Number of supervisor iterations")


class ChatResponse(BaseModel):
    """Chat response model."""
    id: str = Field(..., description="Response ID")
    thread_id: str | None = Field(None, description="Thread ID for continuation")
    messages: list[MessageModel] = Field(default_factory=list, description="All messages")
    final_response: str = Field("", description="Final assistant response")
    metadata: ChatMetadata = Field(default_factory=ChatMetadata)


class AgentInfo(BaseModel):
    """Information about an agent."""
    name: str = Field(..., description="Agent name")
    description: str = Field("", description="Agent description")
    kind: str = Field(..., description="Agent type (supervisor, native_worker, external)")
    skills: list[str] = Field(default_factory=list, description="Agent skills/tools")
    framework: str | None = Field(None, description="Agent framework")
    status: str = Field("active", description="Agent status")


class AgentsResponse(BaseModel):
    """Response listing all agents."""
    supervisor: AgentInfo | None = Field(None, description="Supervisor agent")
    native_workers: list[AgentInfo] = Field(default_factory=list, description="Native worker agents")
    external_agents: list[AgentInfo] = Field(default_factory=list, description="External A2A agents")


class ComponentHealth(BaseModel):
    """Health status of a component."""
    status: str = Field(..., description="Component status")
    message: str | None = Field(None, description="Optional status message")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Overall status (healthy, degraded, unhealthy)")
    version: str = Field(..., description="System version")
    uptime_seconds: int = Field(..., description="Uptime in seconds")
    components: dict[str, ComponentHealth] = Field(default_factory=dict)


# OpenAI-compatible models
class OpenAIMessage(BaseModel):
    """OpenAI-compatible message."""
    role: str
    content: str


class OpenAIChatRequest(BaseModel):
    """OpenAI-compatible chat request."""
    model: str = Field(default="maos", description="Model name (ignored)")
    messages: list[OpenAIMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


class OpenAIChoice(BaseModel):
    """OpenAI-compatible choice."""
    index: int = 0
    message: OpenAIMessage
    finish_reason: str = "stop"


class OpenAIUsage(BaseModel):
    """OpenAI-compatible usage."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class OpenAIChatResponse(BaseModel):
    """OpenAI-compatible chat response."""
    id: str
    object: str = "chat.completion"
    created: int
    model: str = "maos"
    choices: list[OpenAIChoice]
    usage: OpenAIUsage = Field(default_factory=OpenAIUsage)
