"""Chat endpoints for conversation handling."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langgraph.types import Command

from maos.api.models import (
    ChatRequest,
    ChatResponse,
    InputRequiredResponse,
    Message,
    ResumeRequest,
    ToolCallInfo,
    WorkerResultInfo,
)
from maos.api.streaming import stream_graph_events
from maos.api.thread_id import resolve_thread_id
from maos.graph.state import WorkerResult, create_initial_state

logger = structlog.get_logger()

router = APIRouter(tags=["chat"])


def get_app_context() -> dict[str, Any]:
    """Get application context - to be overridden by dependency injection."""
    return {}


def get_graph():
    """Get the compiled graph - to be overridden by dependency injection."""
    return None


def get_checkpointer():
    """Get the checkpointer - to be overridden by dependency injection."""
    return None


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    http_request: Request,
    context: dict[str, Any] = Depends(get_app_context)
):
    """
    Start or continue a chat conversation.

    If stream=True, returns Server-Sent Events stream.
    Otherwise, returns the complete response.

    Thread ID resolution (in priority order):
    - Explicit thread_id in request body
    - X-OpenWebUI-Chat-Id header
    - X-Thread-Id, X-Session-Id headers
    - Auto-generated UUID
    """
    graph = context.get("graph")
    agent_registry = context.get("agent_registry")

    if not graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    # Resolve thread_id using unified strategy
    thread_id = resolve_thread_id(
        request=http_request,
        body={"thread_id": request.thread_id},
        explicit_id=request.thread_id
    )

    # Get roster from agent registry
    roster = []
    if agent_registry and hasattr(agent_registry, 'get_roster'):
        roster = agent_registry.get_roster()

    # Convert messages to dict format
    messages = [
        {
            "role": msg.role.value if hasattr(msg.role, 'value') else msg.role,
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

    # Config for graph execution
    config = {"configurable": {"thread_id": thread_id}}

    # Handle streaming response
    if request.stream:
        return StreamingResponse(
            stream_graph_events(graph, initial_state, config),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Thread-Id": thread_id
            }
        )

    # Non-streaming execution
    try:
        logger.info("chat_start", thread_id=thread_id, message_count=len(messages))

        result = await graph.ainvoke(initial_state, config=config)

        # Check if interrupted for user input
        state = await graph.aget_state(config)
        if state.next:
            tasks = getattr(state, 'tasks', [])
            if tasks and hasattr(tasks[0], 'interrupts') and tasks[0].interrupts:
                interrupt_value = tasks[0].interrupts[0].value
                if isinstance(interrupt_value, dict) and interrupt_value.get("type") == "input_required":
                    return InputRequiredResponse(
                        thread_id=thread_id,
                        input_required=True,
                        prompt=interrupt_value.get("prompt", ""),
                        context=interrupt_value
                    )

        # Build response
        response_messages = []
        for msg in result.get("messages", []):
            if isinstance(msg, dict):
                response_messages.append(Message(
                    role=msg.get("role", "assistant"),
                    content=msg.get("content", ""),
                    name=msg.get("name")
                ))

        # Get final response
        final_response = ""
        if response_messages:
            final_response = response_messages[-1].content

        # Get worker results
        worker_results = _extract_worker_results(result)

        logger.info(
            "chat_complete",
            thread_id=thread_id,
            iterations=result.get("iteration", 0),
            done=result.get("done", True)
        )

        return ChatResponse(
            thread_id=thread_id,
            messages=response_messages,
            final_response=final_response,
            worker_results=worker_results,
            iterations=result.get("iteration", 0),
            done=result.get("done", True)
        )

    except Exception as e:
        logger.error("chat_error", thread_id=thread_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Chat execution error: {str(e)}"
        )


@router.post("/chat/resume", response_model=ChatResponse)
async def resume_chat(
    request: ResumeRequest,
    context: dict[str, Any] = Depends(get_app_context)
):
    """
    Resume a paused conversation with user input.

    Used when the graph was interrupted for user input via the send_message tool.
    """
    graph = context.get("graph")

    if not graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    thread_id = request.thread_id
    config = {"configurable": {"thread_id": thread_id}}

    try:
        logger.info("chat_resume", thread_id=thread_id)

        # Check if there's a state to resume
        state = await graph.aget_state(config)
        if not state.next:
            raise HTTPException(
                status_code=400,
                detail="No paused conversation found for this thread"
            )

        # Resume with user input
        result = await graph.ainvoke(
            Command(resume=request.input),
            config=config
        )

        # Check if interrupted again
        state = await graph.aget_state(config)
        if state.next:
            tasks = getattr(state, 'tasks', [])
            if tasks and hasattr(tasks[0], 'interrupts') and tasks[0].interrupts:
                interrupt_value = tasks[0].interrupts[0].value
                if isinstance(interrupt_value, dict) and interrupt_value.get("type") == "input_required":
                    return InputRequiredResponse(
                        thread_id=thread_id,
                        input_required=True,
                        prompt=interrupt_value.get("prompt", ""),
                        context=interrupt_value
                    )

        # Build response
        response_messages = []
        for msg in result.get("messages", []):
            if isinstance(msg, dict):
                response_messages.append(Message(
                    role=msg.get("role", "assistant"),
                    content=msg.get("content", ""),
                    name=msg.get("name")
                ))

        final_response = ""
        if response_messages:
            final_response = response_messages[-1].content

        worker_results = _extract_worker_results(result)

        logger.info(
            "chat_resume_complete",
            thread_id=thread_id,
            iterations=result.get("iteration", 0)
        )

        return ChatResponse(
            thread_id=thread_id,
            messages=response_messages,
            final_response=final_response,
            worker_results=worker_results,
            iterations=result.get("iteration", 0),
            done=result.get("done", True)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("chat_resume_error", thread_id=thread_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Resume error: {str(e)}"
        )


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    http_request: Request,
    context: dict[str, Any] = Depends(get_app_context)
):
    """
    Start a streaming chat conversation.

    Always returns Server-Sent Events stream regardless of stream parameter.
    """
    # Force streaming
    request.stream = True
    return await chat(request, http_request, context)


@router.get("/chat/{thread_id}/state")
async def get_thread_state(
    thread_id: str,
    context: dict[str, Any] = Depends(get_app_context)
) -> dict[str, Any]:
    """
    Get the current state of a conversation thread.

    Useful for debugging or resuming conversations.
    """
    graph = context.get("graph")

    if not graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    config = {"configurable": {"thread_id": thread_id}}

    try:
        state = await graph.aget_state(config)

        if state.values is None:
            raise HTTPException(
                status_code=404,
                detail=f"Thread '{thread_id}' not found"
            )

        return {
            "thread_id": thread_id,
            "values": state.values,
            "next": state.next,
            "config": state.config
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_state_error", thread_id=thread_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error getting thread state: {str(e)}"
        )


@router.delete("/chat/{thread_id}")
async def delete_thread(
    thread_id: str,
    context: dict[str, Any] = Depends(get_app_context)
) -> dict[str, Any]:
    """
    Delete a conversation thread.

    Note: This only works if a checkpointer with delete capability is configured.
    """
    checkpointer = context.get("checkpointer")

    if not checkpointer:
        return {
            "deleted": False,
            "message": "No checkpointer configured, threads are ephemeral"
        }

    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Try to delete if checkpointer supports it
        if hasattr(checkpointer, 'adelete'):
            await checkpointer.adelete(config)
            return {"deleted": True, "thread_id": thread_id}
        else:
            return {
                "deleted": False,
                "message": "Checkpointer does not support deletion"
            }

    except Exception as e:
        logger.error("delete_thread_error", thread_id=thread_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting thread: {str(e)}"
        )


def _extract_worker_results(result: dict[str, Any]) -> list[WorkerResultInfo]:
    """Extract worker results from graph result."""
    worker_results = []

    last_result = result.get("last_result")
    if last_result:
        if isinstance(last_result, WorkerResult):
            tool_calls = []
            if last_result.output.tool_calls:
                for tc in last_result.output.tool_calls:
                    tool_calls.append(ToolCallInfo(
                        tool_id=tc.tool_id,
                        tool_name=tc.tool_name,
                        input_args=tc.input_args,
                        output=tc.output,
                        success=tc.success,
                        error_message=tc.error_message,
                        duration_ms=tc.duration_ms
                    ))

            worker_results.append(WorkerResultInfo(
                from_agent=last_result.from_agent,
                content=last_result.content,
                result_type=last_result.output.type.value,
                tool_calls=tool_calls,
                duration_ms=last_result.metadata.duration_ms
            ))
        elif isinstance(last_result, dict):
            worker_results.append(WorkerResultInfo(
                from_agent=last_result.get("from_agent", "unknown"),
                content=last_result.get("output", {}).get("content", ""),
                result_type=last_result.get("output", {}).get("type", "text")
            ))

    return worker_results
