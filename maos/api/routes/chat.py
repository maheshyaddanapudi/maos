"""
MAOS Chat Routes.

Main chat endpoint for the orchestration system.
"""

import json
import time
import uuid
from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.types import Command

from maos.api.models import (
    ChatMetadata,
    ChatRequest,
    ChatResponse,
    MessageModel,
    ResumeRequest,
)
from maos.graph.state import create_initial_state

log = structlog.get_logger()

router = APIRouter(tags=["chat"])


def get_graph():
    """Dependency to get the compiled graph."""
    from maos.api.server import _app_state
    return _app_state.get("graph")


def get_roster():
    """Dependency to get the agent roster."""
    from maos.api.server import _app_state
    return _app_state.get("roster", [])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    graph=Depends(get_graph),
    roster=Depends(get_roster),
):
    """Send chat message to the orchestration system."""
    if graph is None:
        raise HTTPException(status_code=503, detail="System not initialized")

    start_time = time.time()

    # Generate thread ID if not provided
    thread_id = request.thread_id or str(uuid.uuid4())

    log.info("chat_request", thread_id=thread_id, message_count=len(request.messages))

    if request.stream:
        return StreamingResponse(
            stream_response(graph, request, roster, thread_id),
            media_type="text/event-stream",
        )

    # Convert messages to dict format
    messages = [
        {"role": m.role, "content": m.content, "name": m.name}
        for m in request.messages
    ]

    # Create initial state
    initial_state = create_initial_state(messages, roster, thread_id)

    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Invoke the graph
        result = await graph.ainvoke(initial_state, config)

        duration_ms = int((time.time() - start_time) * 1000)

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

        # Build response messages
        response_messages = []
        for msg in final_messages:
            if hasattr(msg, "content"):
                response_messages.append(MessageModel(
                    role=getattr(msg, "type", "assistant"),
                    content=msg.content,
                ))
            elif isinstance(msg, dict):
                response_messages.append(MessageModel(**msg))

        # Extract metadata
        workers_used = []
        last_result = result.get("last_result")
        if last_result:
            workers_used.append(last_result.from_agent)

        return ChatResponse(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            messages=response_messages,
            final_response=final_response,
            metadata=ChatMetadata(
                duration_ms=duration_ms,
                workers_used=workers_used,
                iterations=result.get("iteration", 0),
            ),
        )

    except Exception as e:
        log.error("chat_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


async def stream_response(
    graph,
    request: ChatRequest,
    roster: list[str],
    thread_id: str,
) -> AsyncIterator[str]:
    """Stream graph execution events."""
    messages = [
        {"role": m.role, "content": m.content, "name": m.name}
        for m in request.messages
    ]

    initial_state = create_initial_state(messages, roster, thread_id)
    config = {"configurable": {"thread_id": thread_id}}

    try:
        async for event in graph.astream_events(initial_state, config, version="v2"):
            event_type = event.get("event", "")

            if event_type == "on_chain_stream":
                data = event.get("data", {})
                chunk = data.get("chunk", {})
                if isinstance(chunk, dict):
                    yield f"event: chunk\ndata: {json.dumps(chunk)}\n\n"

            elif event_type == "on_chat_model_stream":
                data = event.get("data", {})
                chunk = data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield f"event: chunk\ndata: {json.dumps({'content': chunk.content})}\n\n"

            elif event_type == "on_tool_start":
                data = event.get("data", {})
                yield f"event: tool_call\ndata: {json.dumps(data)}\n\n"

            elif event_type == "on_tool_end":
                data = event.get("data", {})
                yield f"event: tool_result\ndata: {json.dumps({'output': str(data.get('output', ''))})}\n\n"

        # Check if graph is interrupted
        state = await graph.aget_state(config)
        if state.next:  # Graph is waiting
            tasks = getattr(state, "tasks", [])
            if tasks and hasattr(tasks[0], "interrupts") and tasks[0].interrupts:
                interrupt_value = tasks[0].interrupts[0].value
                if isinstance(interrupt_value, dict) and interrupt_value.get("type") == "input_required":
                    yield f"event: input_required\ndata: {json.dumps(interrupt_value)}\n\n"
                    return

        yield f"event: done\ndata: {json.dumps({'thread_id': thread_id})}\n\n"

    except Exception as e:
        log.error("stream_error", error=str(e))
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


@router.post("/chat/resume", response_model=ChatResponse)
async def resume_chat(
    request: ResumeRequest,
    graph=Depends(get_graph),
):
    """Resume a paused conversation with user input."""
    if graph is None:
        raise HTTPException(status_code=503, detail="System not initialized")

    start_time = time.time()

    log.info("resume_chat", thread_id=request.thread_id)

    config = {"configurable": {"thread_id": request.thread_id}}

    try:
        # Resume the graph with user input
        result = await graph.ainvoke(
            Command(resume=request.input),
            config=config,
        )

        duration_ms = int((time.time() - start_time) * 1000)

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

        response_messages = []
        for msg in final_messages:
            if hasattr(msg, "content"):
                response_messages.append(MessageModel(
                    role=getattr(msg, "type", "assistant"),
                    content=msg.content,
                ))
            elif isinstance(msg, dict):
                response_messages.append(MessageModel(**msg))

        return ChatResponse(
            id=str(uuid.uuid4()),
            thread_id=request.thread_id,
            messages=response_messages,
            final_response=final_response,
            metadata=ChatMetadata(duration_ms=duration_ms),
        )

    except Exception as e:
        log.error("resume_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
