"""Background task endpoints (title generation, tags, etc.).

These endpoints are OpenWebUI-compatible and route through the supervisor
for true plug-and-play agent discovery.
"""

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from maos.graph.state import create_initial_state

logger = structlog.get_logger()

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# =============================================================================
# Request/Response Models
# =============================================================================

class TitleGenerationRequest(BaseModel):
    """Request for title generation."""
    messages: list[dict[str, str]] = Field(
        ...,
        description="Conversation messages to generate title for",
        min_length=1
    )
    thread_id: str | None = Field(
        None,
        description="Thread ID for the conversation"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "messages": [
                    {"role": "user", "content": "How do I sort a list in Python?"},
                    {"role": "assistant", "content": "You can use sorted() or list.sort()..."}
                ]
            }
        }


class TitleGenerationResponse(BaseModel):
    """Response from title generation."""
    title: str
    thread_id: str
    generated_via: str = Field(
        default="supervisor",
        description="How the title was generated (always 'supervisor' for plug-and-play)"
    )


class BackgroundTasksRequest(BaseModel):
    """OpenWebUI-compatible background tasks configuration."""
    title_generation: bool = False
    tags_generation: bool = False


# =============================================================================
# Dependency Injection
# =============================================================================

def get_app_context() -> dict[str, Any]:
    """Get application context - to be overridden by dependency injection."""
    return {}


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/title", response_model=TitleGenerationResponse)
async def generate_title(
    request: TitleGenerationRequest,
    context: dict[str, Any] = Depends(get_app_context)
):
    """
    Generate a title for a conversation.

    This endpoint routes through the supervisor, which auto-discovers
    and delegates to the title_generator agent. This demonstrates
    true plug-and-play architecture:

    1. Request comes in with conversation messages
    2. We ask supervisor: "Generate a title for this conversation"
    3. Supervisor routes to title_generator (discovered via roster)
    4. title_generator returns concise title
    5. We extract and return the title

    This is OpenWebUI-compatible and can be called as a background task.
    """
    graph = context.get("graph")
    agent_registry = context.get("agent_registry")

    if not graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    thread_id = request.thread_id or str(uuid.uuid4())

    # Get roster - title_generator should be in here
    roster = []
    if agent_registry and hasattr(agent_registry, 'get_roster'):
        roster = agent_registry.get_roster()

    if "title_generator" not in roster:
        logger.warning("title_generator_not_in_roster", roster=roster)
        # Fallback: return a simple title from first message
        first_msg = request.messages[0].get("content", "")[:50]
        return TitleGenerationResponse(
            title=first_msg.strip() or "New Conversation",
            thread_id=thread_id,
            generated_via="fallback"
        )

    # Build conversation summary for title generation
    conversation_summary = _build_conversation_summary(request.messages)

    # Create the title request message
    # This goes through supervisor which will route to title_generator
    title_request = f"Generate a concise title (3-8 words) for this conversation:\n\n{conversation_summary}"

    messages = [{"role": "user", "content": title_request}]

    # Create state and invoke graph
    state = create_initial_state(
        messages=messages,
        roster=roster,
        thread_id=f"title-{thread_id}"  # Separate thread for title generation
    )

    config = {"configurable": {"thread_id": f"title-{thread_id}"}}

    try:
        result = await graph.ainvoke(state, config)

        # Extract title from response
        title = _extract_title_from_result(result)

        logger.info(
            "title_generated_via_supervisor",
            thread_id=thread_id,
            title=title,
            message_count=len(request.messages)
        )

        return TitleGenerationResponse(
            title=title,
            thread_id=thread_id,
            generated_via="supervisor"
        )

    except Exception as e:
        logger.error("title_generation_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Title generation failed: {str(e)}"
        )


@router.post("/title/async")
async def generate_title_async(
    request: TitleGenerationRequest,
    background_tasks: BackgroundTasks,
    context: dict[str, Any] = Depends(get_app_context)
):
    """
    Queue title generation as a background task.

    Returns immediately with a task ID. The title will be generated
    asynchronously and can be retrieved later.

    This matches OpenWebUI's background_tasks.title_generation pattern.
    """
    task_id = str(uuid.uuid4())
    thread_id = request.thread_id or str(uuid.uuid4())

    # Queue the background task
    background_tasks.add_task(
        _generate_title_background,
        task_id=task_id,
        thread_id=thread_id,
        messages=request.messages,
        context=context
    )

    return {
        "task_id": task_id,
        "thread_id": thread_id,
        "status": "queued",
        "message": "Title generation queued. Poll /api/tasks/status/{task_id} for result."
    }


# =============================================================================
# Helper Functions
# =============================================================================

def _build_conversation_summary(messages: list[dict[str, str]], max_chars: int = 500) -> str:
    """Build a summary of the conversation for title generation."""
    summary_parts = []
    total_chars = 0

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        # Truncate long messages
        if len(content) > 200:
            content = content[:200] + "..."

        part = f"{role.capitalize()}: {content}"

        if total_chars + len(part) > max_chars:
            break

        summary_parts.append(part)
        total_chars += len(part)

    return "\n".join(summary_parts)


def _extract_title_from_result(result: dict[str, Any]) -> str:
    """Extract the title from graph result."""
    messages = result.get("messages", [])

    # Find the last AI message with content
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "ai":
            content = getattr(msg, "content", "")
            if content and isinstance(content, str):
                # Clean up the title
                title = content.strip()
                # Remove quotes if wrapped
                if title.startswith('"') and title.endswith('"'):
                    title = title[1:-1]
                if title.startswith("'") and title.endswith("'"):
                    title = title[1:-1]
                # Limit length
                if len(title) > 100:
                    title = title[:97] + "..."
                return title

    return "New Conversation"


async def _generate_title_background(
    task_id: str,
    thread_id: str,
    messages: list[dict[str, str]],
    context: dict[str, Any]
) -> None:
    """Background task for title generation."""
    # TODO: Store result in a task store for retrieval
    # For now, just log the result
    try:
        graph = context.get("graph")
        agent_registry = context.get("agent_registry")

        if not graph:
            logger.error("background_title_no_graph", task_id=task_id)
            return

        roster = []
        if agent_registry and hasattr(agent_registry, 'get_roster'):
            roster = agent_registry.get_roster()

        conversation_summary = _build_conversation_summary(messages)
        title_request = f"Generate a concise title (3-8 words) for this conversation:\n\n{conversation_summary}"

        state = create_initial_state(
            messages=[{"role": "user", "content": title_request}],
            roster=roster,
            thread_id=f"title-{thread_id}"
        )

        config = {"configurable": {"thread_id": f"title-{thread_id}"}}
        result = await graph.ainvoke(state, config)
        title = _extract_title_from_result(result)

        logger.info(
            "background_title_generated",
            task_id=task_id,
            thread_id=thread_id,
            title=title
        )

    except Exception as e:
        logger.error(
            "background_title_failed",
            task_id=task_id,
            error=str(e)
        )
