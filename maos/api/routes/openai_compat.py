"""OpenAI-compatible API endpoints."""

import time
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import structlog

from maos.api.models import (
    OpenAIChatRequest,
    OpenAIChatResponse,
    OpenAIChoice,
    OpenAIMessage,
    OpenAIUsage,
)
from maos.api.streaming import stream_openai_response
from maos.graph.state import create_initial_state

logger = structlog.get_logger()

router = APIRouter(prefix="/v1", tags=["openai"])


def get_app_context() -> Dict[str, Any]:
    """Get application context - to be overridden by dependency injection."""
    return {}


@router.post("/chat/completions", response_model=OpenAIChatResponse)
async def create_chat_completion(
    request: OpenAIChatRequest,
    context: Dict[str, Any] = Depends(get_app_context)
):
    """
    OpenAI-compatible chat completions endpoint.

    This allows MAOS to be used as a drop-in replacement for OpenAI's API
    in applications that use the OpenAI client library.
    """
    graph = context.get("graph")
    agent_registry = context.get("agent_registry")

    if not graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    # Generate thread ID
    thread_id = str(uuid.uuid4())

    # Get roster
    roster = []
    if agent_registry and hasattr(agent_registry, 'get_roster'):
        roster = agent_registry.get_roster()

    # Convert messages
    messages = [
        {
            "role": msg.role,
            "content": msg.content,
            "name": msg.name
        }
        for msg in request.messages
    ]

    # Create initial state
    initial_state = create_initial_state(
        messages=messages,
        roster=roster,
        thread_id=thread_id
    )

    config = {"configurable": {"thread_id": thread_id}}

    # Handle streaming
    if request.stream:
        return StreamingResponse(
            stream_openai_response(graph, initial_state, config, request.model),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )

    # Non-streaming execution
    try:
        logger.info("openai_chat_start", thread_id=thread_id)

        result = await graph.ainvoke(initial_state, config=config)

        # Get final assistant message
        final_content = ""
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                final_content = msg.get("content", "")
                break

        # Build response
        response_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())

        logger.info("openai_chat_complete", thread_id=thread_id)

        return OpenAIChatResponse(
            id=response_id,
            created=created,
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
            usage=OpenAIUsage(
                prompt_tokens=0,  # We don't track tokens
                completion_tokens=0,
                total_tokens=0
            )
        )

    except Exception as e:
        logger.error("openai_chat_error", error=str(e))
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
