"""LangGraph state schema and related models."""

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages


class ResultType(str, Enum):
    """Type of result output."""
    TEXT = "text"
    ERROR = "error"
    PARTIAL = "partial"
    STRUCTURED = "structured"


class ToolCallRecord(BaseModel):
    """Record of a tool invocation during worker execution."""
    tool_id: str
    tool_name: str
    input_args: Dict[str, Any]
    output: Any
    success: bool = True
    error_message: Optional[str] = None
    duration_ms: int = 0


class ResultOutput(BaseModel):
    """Structured output from worker execution."""
    type: ResultType = ResultType.TEXT
    content: str
    sources: List[str] = Field(default_factory=list)
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    structured_data: Optional[Dict[str, Any]] = None


class ResultMetadata(BaseModel):
    """Metadata about the worker execution."""
    tokens_used: int = 0
    duration_ms: int = 0
    tools_invoked: List[str] = Field(default_factory=list)
    model_used: Optional[str] = None
    retry_count: int = 0


class WorkerResult(BaseModel):
    """Complete result from a worker agent execution."""
    from_agent: str
    output: ResultOutput
    metadata: ResultMetadata = Field(default_factory=ResultMetadata)

    @property
    def is_error(self) -> bool:
        """Check if result represents an error."""
        return self.output.type == ResultType.ERROR

    @property
    def is_partial(self) -> bool:
        """Check if result is partial (incomplete)."""
        return self.output.type == ResultType.PARTIAL

    @property
    def content(self) -> str:
        """Shortcut to output content."""
        return self.output.content

    def to_message(self) -> Dict[str, Any]:
        """Convert to message format for graph state."""
        return {
            "role": "assistant",
            "name": self.from_agent,
            "content": self.output.content
        }


class Message(BaseModel):
    """A message in the conversation."""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        d = {"role": self.role, "content": self.content}
        if self.name:
            d["name"] = self.name
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d


# GraphState as a TypedDict for LangGraph
from typing_extensions import TypedDict


class GraphState(TypedDict):
    """LangGraph state schema with reducers."""
    messages: Annotated[list, add_messages]
    task: str
    context: Dict[str, Any]
    roster: List[str]
    last_result: Optional[WorkerResult]
    next: Optional[str]
    done: bool
    iteration: int
    metadata: Dict[str, Any]
    thread_id: Optional[str]


def create_initial_state(
    messages: List[Dict[str, Any]],
    roster: List[str],
    thread_id: Optional[str] = None
) -> GraphState:
    """
    Create initial graph state.

    Args:
        messages: Initial messages.
        roster: List of available worker names.
        thread_id: Optional thread ID for persistence.

    Returns:
        Initial graph state.
    """
    # Extract task from last user message
    task = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            task = msg.get("content", "")
            break

    return {
        "messages": messages,
        "task": task,
        "context": {},
        "roster": roster,
        "last_result": None,
        "next": None,
        "done": False,
        "iteration": 0,
        "metadata": {},
        "thread_id": thread_id
    }
