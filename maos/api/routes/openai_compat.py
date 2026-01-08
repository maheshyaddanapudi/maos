"""OpenAI-compatible API endpoints with interrupt handling.

This module provides OpenAI-compatible endpoints that work seamlessly with
OpenWebUI and similar chat UIs. Interrupts from send_message are automatically
converted to normal assistant messages, and the next user message resumes
the conversation.
"""

import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langgraph.types import Command
import structlog

from maos.api.thread_id import resolve_thread_id, OPENWEBUI_CONFIG
from maos.api.models import (
    OpenAIChatRequest,
    OpenAIChatResponse,
    OpenAIChoice,
    OpenAIMessage,
    OpenAIUsage,
)
from maos.api.streaming import stream_openai_response_with_interrupt
from maos.graph.state import create_initial_state

logger = structlog.get_logger()

router = APIRouter(prefix="/v1", tags=["openai"])


def get_app_context() -> Dict[str, Any]:
    """Get application context - to be overridden by dependency injection."""
    return {}


def _extract_interrupt_message(state) -> Optional[str]:
    """Extract interrupt message from graph state if interrupted."""
    if not state.next:
        return None

    tasks = getattr(state, 'tasks', [])
    if tasks and hasattr(tasks[0], 'interrupts') and tasks[0].interrupts:
        interrupt_value = tasks[0].interrupts[0].value
        if isinstance(interrupt_value, dict) and interrupt_value.get("type") == "input_required":
            return interrupt_value.get("prompt", "")

    return None


def _extract_final_content(result: Dict[str, Any]) -> str:
    """Extract final assistant content from graph result."""
    for msg in reversed(result.get("messages", [])):
        # Handle AIMessage objects
        if hasattr(msg, "type") and msg.type == "ai":
            content = getattr(msg, "content", "")
            if content:
                return str(content)
        # Handle dict messages
        elif isinstance(msg, dict) and msg.get("role") == "assistant":
            content = msg.get("content", "")
            if content:
                return str(content)

    return ""


@router.post("/chat/completions", response_model=OpenAIChatResponse)
async def create_chat_completion(
    request: OpenAIChatRequest,
    http_request: Request,
    context: Dict[str, Any] = Depends(get_app_context)
):
    """
    OpenAI-compatible chat completions endpoint with interrupt handling.

    This endpoint provides seamless integration with OpenWebUI and similar UIs:

    1. **Normal flow**: User sends message → MAOS processes → Response returned
    2. **Interrupt flow** (when send_message is used):
       - MAOS needs user input → Returns message as normal response
       - Response includes `input_pending: true` and `thread_id`
       - User sends next message with same `thread_id` → Conversation resumes

    Thread ID resolution (in priority order):
    - Explicit thread_id in request body
    - X-OpenWebUI-Chat-Id header (when ENABLE_FORWARD_USER_INFO_HEADERS is set)
    - X-Thread-Id or X-Session-Id headers
    - Auto-generated UUID

    This makes MAOS work as a drop-in replacement for OpenAI's API while
    supporting human-in-the-loop interactions transparently.
    """
    graph = context.get("graph")
    agent_registry = context.get("agent_registry")

    if not graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    # Resolve thread_id using unified strategy (checks headers, body, etc.)
    thread_id = resolve_thread_id(
        request=http_request,
        body={"thread_id": request.thread_id},
        explicit_id=request.thread_id,
        config=OPENWEBUI_CONFIG
    )
    config = {"configurable": {"thread_id": thread_id}}

    # Get roster
    roster = []
    if agent_registry and hasattr(agent_registry, 'get_roster'):
        roster = agent_registry.get_roster()

    # Get the latest user message
    latest_user_message = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            latest_user_message = msg.content
            break

    # Check if there's a paused conversation to resume
    state = await graph.aget_state(config)
    is_resuming = state.next is not None

    # Handle streaming
    if request.stream:
        return StreamingResponse(
            stream_openai_response_with_interrupt(
                graph=graph,
                config=config,
                roster=roster,
                messages=request.messages,
                is_resuming=is_resuming,
                latest_user_message=latest_user_message,
                model=request.model,
                thread_id=thread_id
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )

    # Non-streaming execution
    try:
        if is_resuming:
            # Resume paused conversation with user's response
            logger.info("openai_chat_resume", thread_id=thread_id)
            result = await graph.ainvoke(
                Command(resume=latest_user_message),
                config=config
            )
        else:
            # Start new conversation
            logger.info("openai_chat_start", thread_id=thread_id)

            # Convert messages
            messages = [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "name": msg.name
                }
                for msg in request.messages
            ]

            initial_state = create_initial_state(
                messages=messages,
                roster=roster,
                thread_id=thread_id
            )

            result = await graph.ainvoke(initial_state, config=config)

        # Check if graph is now interrupted
        state = await graph.aget_state(config)
        interrupt_message = _extract_interrupt_message(state)

        if interrupt_message:
            # Graph is waiting for input - return interrupt as normal message
            logger.info(
                "openai_chat_interrupted",
                thread_id=thread_id,
                prompt=interrupt_message[:50]
            )

            return OpenAIChatResponse(
                id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
                created=int(time.time()),
                model=request.model,
                choices=[
                    OpenAIChoice(
                        index=0,
                        message=OpenAIMessage(
                            role="assistant",
                            content=interrupt_message
                        ),
                        finish_reason="stop"  # Appears normal to UI
                    )
                ],
                usage=OpenAIUsage(),
                thread_id=thread_id,
                input_pending=True  # Signals that we're waiting for input
            )

        # Normal completion
        final_content = _extract_final_content(result)

        logger.info("openai_chat_complete", thread_id=thread_id)

        return OpenAIChatResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
            created=int(time.time()),
            model=request.model,
            choices=[
                OpenAIChoice(
                    index=0,
                    message=OpenAIMessage(
                        role="assistant",
                        content=final_content
                    ),
                    finish_reason="stop"
                )
            ],
            usage=OpenAIUsage(),
            thread_id=thread_id,
            input_pending=False
        )

    except Exception as e:
        logger.error("openai_chat_error", error=str(e), thread_id=thread_id)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/models")
async def list_models() -> Dict[str, Any]:
    """
    List available models.

    Returns a single "maos" model that represents the orchestration system.
    """
    return {
        "object": "list",
        "data": [
            {
                "id": "maos",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "maos",
                "permission": [],
                "root": "maos",
                "parent": None
            }
        ]
    }


@router.get("/models/{model_id}")
async def get_model(model_id: str) -> Dict[str, Any]:
    """
    Get model information.

    Always returns "maos" model info regardless of model_id.
    """
    return {
        "id": "maos",
        "object": "model",
        "created": int(time.time()),
        "owned_by": "maos",
        "permission": [],
        "root": "maos",
        "parent": None
    }
