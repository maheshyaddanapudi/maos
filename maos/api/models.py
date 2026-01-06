"""API request and response models."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class MessageRole(str, Enum):
    """Message role types."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Message(BaseModel):
    """A message in the conversation."""
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class ChatRequest(BaseModel):
    """Request for /chat endpoint."""
    messages: List[Message] = Field(..., min_length=1)
    thread_id: Optional[str] = None
    stream: bool = False
    max_iterations: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "messages": [{"role": "user", "content": "Hello, how can you help me?"}],
                "stream": True
            }
        }


class ResumeRequest(BaseModel):
    """Request for /chat/resume endpoint."""
    thread_id: str = Field(..., description="Thread ID from the interrupted conversation")
    input: str = Field(..., description="User input to resume with")


class ToolCallInfo(BaseModel):
    """Information about a tool call."""
    tool_id: str
    tool_name: str
    input_args: Dict[str, Any]
    output: Any = None
    success: bool = True
    error_message: Optional[str] = None
    duration_ms: int = 0


class WorkerResultInfo(BaseModel):
    """Information about a worker result."""
    from_agent: str
    content: str
    result_type: str = "text"
    tool_calls: List[ToolCallInfo] = Field(default_factory=list)
    duration_ms: int = 0


class ChatResponse(BaseModel):
    """Response from /chat endpoint."""
    thread_id: str
    messages: List[Message]
    final_response: str
    worker_results: List[WorkerResultInfo] = Field(default_factory=list)
    iterations: int = 0
    done: bool = True


class InputRequiredResponse(BaseModel):
    """Response when user input is required."""
    thread_id: str
    input_required: bool = True
    prompt: str
    context: Optional[Dict[str, Any]] = None


class StreamEventType(str, Enum):
    """Types of streaming events."""
    CHUNK = "chunk"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    WORKER_START = "worker_start"
    WORKER_END = "worker_end"
    SUPERVISOR_DECISION = "supervisor_decision"
    INPUT_REQUIRED = "input_required"
    ERROR = "error"
    DONE = "done"


class StreamEvent(BaseModel):
    """A streaming event."""
    event: StreamEventType
    data: Dict[str, Any]
    timestamp: Optional[datetime] = None


class AgentInfo(BaseModel):
    """Information about an available agent."""
    name: str
    kind: str
    description: Optional[str] = None
    llm: Optional[str] = None
    framework: Optional[str] = None
    tools: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)


class AgentListResponse(BaseModel):
    """Response from /agents endpoint."""
    agents: List[AgentInfo]
    supervisor: Optional[AgentInfo] = None
    external_agents: List[AgentInfo] = Field(default_factory=list)


class HealthStatus(str, Enum):
    """Health status values."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    """Health status of a component."""
    name: str
    status: HealthStatus
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Response from /health endpoint."""
    status: HealthStatus
    version: str = "0.1.0"
    components: List[ComponentHealth] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    thread_id: Optional[str] = None


# OpenAI-compatible models
class OpenAIMessage(BaseModel):
    """OpenAI-compatible message format."""
    role: str
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class OpenAIChatRequest(BaseModel):
    """OpenAI-compatible chat completion request.

    Extended with thread_id for conversation continuity and interrupt handling.
    """
    model: str = "maos"
    messages: List[OpenAIMessage]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[str] = None
    # MAOS extension: thread_id for conversation continuity
    thread_id: Optional[str] = Field(
        None,
        description="Thread ID for conversation continuity. If provided and a paused "
                    "conversation exists, the last user message will resume the conversation."
    )


class OpenAIChoice(BaseModel):
    """OpenAI-compatible choice."""
    index: int = 0
    message: OpenAIMessage
    finish_reason: str = "stop"


class OpenAIUsage(BaseModel):
    """OpenAI-compatible usage info."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class OpenAIChatResponse(BaseModel):
    """OpenAI-compatible chat completion response.

    Extended with thread_id and input_pending for interrupt handling.
    """
    id: str
    object: str = "chat.completion"
    created: int
    model: str = "maos"
    choices: List[OpenAIChoice]
    usage: OpenAIUsage = Field(default_factory=OpenAIUsage)
    # MAOS extensions for conversation continuity
    thread_id: Optional[str] = Field(
        None,
        description="Thread ID for continuing this conversation"
    )
    input_pending: bool = Field(
        default=False,
        description="If true, the assistant is waiting for user input to continue. "
                    "Send the next message with the same thread_id to resume."
    )


class OpenAIStreamDelta(BaseModel):
    """OpenAI-compatible stream delta."""
    role: Optional[str] = None
    content: Optional[str] = None


class OpenAIStreamChoice(BaseModel):
    """OpenAI-compatible stream choice."""
    index: int = 0
    delta: OpenAIStreamDelta
    finish_reason: Optional[str] = None


class OpenAIStreamChunk(BaseModel):
    """OpenAI-compatible stream chunk."""
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str = "maos"
    choices: List[OpenAIStreamChoice]
