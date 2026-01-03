"""
MAOS Graph State.

Defines the LangGraph state schema.
"""

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages

from maos.agents.models import WorkerResult


class GraphState(TypedDict):
    """LangGraph state schema with reducers.

    This TypedDict defines the structure of the state that flows through
    the LangGraph orchestration. The `messages` field uses the add_messages
    reducer to append new messages instead of replacing them.
    """
    # Conversation messages - uses add_messages reducer to append
    messages: Annotated[list, add_messages]

    # The current task description
    task: str

    # Additional context for the conversation
    context: dict[str, Any]

    # List of available worker names for routing
    roster: list[str]

    # Result from the last worker execution
    last_result: WorkerResult | None

    # Next node to route to (worker name or "END")
    next: str | None

    # Whether the conversation is complete
    done: bool

    # Current iteration count for loop detection
    iteration: int

    # Thread ID for conversation persistence
    thread_id: str | None

    # Execution metadata
    metadata: dict[str, Any]


def create_initial_state(
    messages: list,
    roster: list[str],
    thread_id: str | None = None,
) -> GraphState:
    """Create initial graph state.

    Args:
        messages: Initial conversation messages
        roster: List of available worker names
        thread_id: Optional thread ID for persistence

    Returns:
        Initial graph state
    """
    # Extract task from last user message
    task = ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            task = msg.get("content", "")
            break

    return GraphState(
        messages=messages,
        task=task,
        context={},
        roster=roster,
        last_result=None,
        next=None,
        done=False,
        iteration=0,
        thread_id=thread_id,
        metadata={},
    )
