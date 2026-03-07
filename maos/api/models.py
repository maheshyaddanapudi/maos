"""API request and response models."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageRole(StrEnum):
    """Message role types."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Message(BaseModel):
    """A message in the conversation."""

    role: MessageRole
    content: str
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


class ChatRequest(BaseModel):
    """Request for /chat endpoint."""

    messages: list[Message] = Field(..., min_length=1, max_length=100)
    thread_id: str | None = None
    stream: bool = False
    max_iterations: int | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "messages": [{"role": "user", "content": "Hello, how can you help me?"}],
                "stream": True,
            }
        }
    )


class ResumeRequest(BaseModel):
    """Request for /chat/resume endpoint."""

    thread_id: str = Field(..., description="Thread ID from the interrupted conversation")
    input: str = Field(..., description="User input to resume with")


class ToolCallInfo(BaseModel):
    """Information about a tool call."""

    tool_id: str
    tool_name: str
    input_args: dict[str, Any]
    output: Any = None
    success: bool = True
    error_message: str | None = None
    duration_ms: int = 0


class WorkerResultInfo(BaseModel):
    """Information about a worker result."""

    from_agent: str
    content: str
    result_type: str = "text"
    tool_calls: list[ToolCallInfo] = Field(default_factory=list)
    duration_ms: int = 0


class ChatResponse(BaseModel):
    """Response from /chat endpoint."""

    thread_id: str
    messages: list[Message]
    final_response: str
    worker_results: list[WorkerResultInfo] = Field(default_factory=list, max_length=50)
    iterations: int = 0
    done: bool = True


class InputRequiredResponse(BaseModel):
    """Response when user input is required."""

    thread_id: str
    input_required: bool = True
    prompt: str
    context: dict[str, Any] | None = None


class StreamEventType(StrEnum):
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
    data: dict[str, Any]
    timestamp: datetime | None = None


class AgentInfo(BaseModel):
    """Information about an available agent."""

    name: str
    kind: str
    description: str | None = None
    llm: str | None = None
    framework: str | None = None
    tools: list[str] = Field(default_factory=list, max_length=50)
    skills: list[str] = Field(default_factory=list, max_length=50)


class AgentListResponse(BaseModel):
    """Response from /agents endpoint."""

    agents: list[AgentInfo] = Field(default_factory=list)
    supervisor: AgentInfo | None = None
    external_agents: list[AgentInfo] = Field(default_factory=list, max_length=50)


class HealthStatus(StrEnum):
    """Health status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    """Health status of a component."""

    name: str
    status: HealthStatus
    message: str | None = None
    details: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    """Response from /health endpoint."""

    status: HealthStatus
    version: str = "0.1.0"
    components: list[ComponentHealth] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    message: str
    details: dict[str, Any] | None = None
    thread_id: str | None = None


# OpenAI-compatible models
class OpenAIMessage(BaseModel):
    """OpenAI-compatible message format."""

    role: str
    content: str
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


class OpenAIChatRequest(BaseModel):
    """OpenAI-compatible chat completion request.

    Extended with thread_id for conversation continuity and interrupt handling.
    """

    model: str = "maos"
    messages: list[OpenAIMessage] = Field(..., min_length=1, max_length=100)
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | None = None
    # MAOS extension: thread_id for conversation continuity
    thread_id: str | None = Field(
        None,
        description="Thread ID for conversation continuity. If provided and a paused "
        "conversation exists, the last user message will resume the conversation.",
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
    choices: list[OpenAIChoice]
    usage: OpenAIUsage = Field(default_factory=OpenAIUsage)
    # MAOS extensions for conversation continuity
    thread_id: str | None = Field(None, description="Thread ID for continuing this conversation")
    input_pending: bool = Field(
        default=False,
        description="If true, the assistant is waiting for user input to continue. "
        "Send the next message with the same thread_id to resume.",
    )


class OpenAIStreamDelta(BaseModel):
    """OpenAI-compatible stream delta."""

    role: str | None = None
    content: str | None = None


class OpenAIStreamChoice(BaseModel):
    """OpenAI-compatible stream choice."""

    index: int = 0
    delta: OpenAIStreamDelta
    finish_reason: str | None = None


class OpenAIStreamChunk(BaseModel):
    """OpenAI-compatible stream chunk."""

    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str = "maos"
    choices: list[OpenAIStreamChoice]


# =============================================================================
# LangGraph Studio API Models
# =============================================================================


class AssistantConfig(BaseModel):
    """Configuration for an assistant."""

    configurable: dict[str, Any] = Field(default_factory=dict)


class Assistant(BaseModel):
    """LangGraph Studio assistant."""

    assistant_id: str
    graph_id: str
    name: str
    description: str | None = None
    config: AssistantConfig = Field(default_factory=AssistantConfig)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class AssistantCreate(BaseModel):
    """Request to create an assistant."""

    graph_id: str = "maos"
    name: str | None = None
    description: str | None = None
    config: AssistantConfig | None = None
    metadata: dict[str, Any] | None = None


class AssistantSearch(BaseModel):
    """Request to search assistants."""

    graph_id: str | None = None
    name: str | None = None
    metadata: dict[str, Any] | None = None
    limit: int = 100
    offset: int = 0


class Thread(BaseModel):
    """LangGraph Studio thread."""

    thread_id: str
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: str = "idle"  # idle, busy, interrupted, error


class ThreadCreate(BaseModel):
    """Request to create a thread."""

    thread_id: str | None = None
    metadata: dict[str, Any] | None = None


class ThreadState(BaseModel):
    """State of a thread."""

    values: dict[str, Any] = Field(default_factory=dict)
    next: list[str] = Field(default_factory=list)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    parent_config: dict[str, Any] | None = None


class ThreadStateUpdate(BaseModel):
    """Request to update thread state."""

    values: dict[str, Any]
    as_node: str | None = None


class RunConfig(BaseModel):
    """Configuration for a run."""

    configurable: dict[str, Any] = Field(default_factory=dict)


class RunCreate(BaseModel):
    """Request to create a run."""

    assistant_id: str
    input: dict[str, Any] | None = None
    config: RunConfig | None = None
    metadata: dict[str, Any] | None = None
    stream_mode: list[str] | None = None  # ["values", "messages", "updates", "events"]
    interrupt_before: list[str] | None = None
    interrupt_after: list[str] | None = None
    multitask_strategy: str | None = None  # "reject", "rollback", "interrupt", "enqueue"


class RunStatus(StrEnum):
    """Status of a run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    INTERRUPTED = "interrupted"
    TIMEOUT = "timeout"


class Run(BaseModel):
    """LangGraph Studio run."""

    run_id: str
    thread_id: str
    assistant_id: str
    status: RunStatus
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunOutput(BaseModel):
    """Output from a completed run."""

    run_id: str
    thread_id: str
    assistant_id: str
    status: RunStatus
    result: dict[str, Any] | None = None
    error: str | None = None
