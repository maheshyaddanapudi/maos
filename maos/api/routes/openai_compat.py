"""
MAOS OpenAI-Compatible Routes.

OpenAI API compatible endpoint for tools like Open WebUI.
"""

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException

from maos.api.models import (
    OpenAIChatRequest,
    OpenAIChatResponse,
    OpenAIChoice,
    OpenAIMessage,
    OpenAIUsage,
)
from maos.graph.state import create_initial_state

router = APIRouter(tags=["openai-compat"])


def get_graph():
    """Dependency to get the compiled graph."""
    from maos.api.server import _app_state
    return _app_state.get("graph")


def get_roster():
    """Dependency to get the agent roster."""
    from maos.api.server import _app_state
    return _app_state.get("roster", [])


@router.post("/v1/chat/completions", response_model=OpenAIChatResponse)
async def openai_chat(
    request: OpenAIChatRequest,
    graph=Depends(get_graph),
    roster=Depends(get_roster),
):
    """OpenAI-compatible chat endpoint."""
    if graph is None:
        raise HTTPException(status_code=503, detail="System not initialized")

    thread_id = str(uuid.uuid4())

    # Convert messages
    messages = [
        {"role": m.role, "content": m.content}
        for m in request.messages
    ]

    initial_state = create_initial_state(messages, roster, thread_id)
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = await graph.ainvoke(initial_state, config)

        # Extract final response
        final_messages = result.get("messages", [])
        final_response = ""

        for msg in reversed(final_messages):
            if hasattr(msg, "content") and hasattr(msg, "type"):
                if msg.type == "ai" or msg.type == "assistant":
                    final_response = msg.content
                    break
            elif isinstance(msg, dict) and msg.get("role") == "assistant":
                final_response = msg.get("content", "")
                break

        return OpenAIChatResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            model="maos",
            choices=[
                OpenAIChoice(
                    index=0,
                    message=OpenAIMessage(role="assistant", content=final_response),
                    finish_reason="stop",
                )
            ],
            usage=OpenAIUsage(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
