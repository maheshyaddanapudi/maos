"""LangGraph Studio-compatible API endpoints.

This module provides endpoints compatible with LangGraph Studio,
allowing MAOS to be used with the LangGraph Studio UI for visualization,
debugging, and testing.

Endpoints:
- /assistants/* - Manage assistants (graph configurations)
- /threads/* - Manage conversation threads
- /threads/{thread_id}/runs/* - Execute and manage runs
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from langgraph.types import Command

from maos.api.models import (
    Assistant,
    AssistantConfig,
    AssistantCreate,
    AssistantSearch,
    Run,
    RunCreate,
    RunStatus,
    Thread,
    ThreadCreate,
    ThreadState,
    ThreadStateUpdate,
)
from maos.graph.state import create_initial_state

logger = structlog.get_logger()

router = APIRouter(tags=["langgraph-studio"])


# In-memory stores (in production, use persistent storage)
_MAX_STORE_SIZE = 10_000
_assistants: dict[str, Assistant] = {}
_threads: dict[str, Thread] = {}
_runs: dict[str, Run] = {}


def _enforce_store_limit(store: dict, max_size: int = _MAX_STORE_SIZE) -> None:
    """Evict oldest entries if store exceeds max_size."""
    while len(store) > max_size:
        oldest_key = next(iter(store))
        del store[oldest_key]


def get_app_context() -> dict[str, Any]:
    """Get application context - to be overridden by dependency injection."""
    return {}


def _now_iso() -> str:
    """Get current time as ISO string."""
    return datetime.now(UTC).isoformat()


def _init_default_assistant(context: dict[str, Any]) -> None:
    """Initialize default assistant from MAOS config."""
    if "default" in _assistants:
        return

    description = "MAOS Multi-Agent Orchestration System"

    _assistants["default"] = Assistant(
        assistant_id="default",
        graph_id="maos",
        name="MAOS Default Assistant",
        description=description,
        config=AssistantConfig(),
        metadata={"auto_created": True},
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )


# =============================================================================
# Assistants Endpoints
# =============================================================================


@router.get("/assistants", response_model=list[Assistant])
async def list_assistants(context: dict[str, Any] = Depends(get_app_context)) -> list[Assistant]:
    """List all assistants."""
    _init_default_assistant(context)
    return list(_assistants.values())


@router.post("/assistants", response_model=Assistant)
async def create_assistant(
    request: AssistantCreate, context: dict[str, Any] = Depends(get_app_context)
) -> Assistant:
    """Create a new assistant."""
    assistant_id = str(uuid.uuid4())
    now = _now_iso()

    assistant = Assistant(
        assistant_id=assistant_id,
        graph_id=request.graph_id,
        name=request.name or f"Assistant {assistant_id[:8]}",
        description=request.description,
        config=request.config or AssistantConfig(),
        metadata=request.metadata or {},
        created_at=now,
        updated_at=now,
    )

    _assistants[assistant_id] = assistant
    _enforce_store_limit(_assistants)
    logger.info("assistant_created", assistant_id=assistant_id)
    return assistant


@router.post("/assistants/search", response_model=list[Assistant])
async def search_assistants(
    request: AssistantSearch, context: dict[str, Any] = Depends(get_app_context)
) -> list[Assistant]:
    """Search assistants by criteria."""
    _init_default_assistant(context)

    results = list(_assistants.values())

    if request.graph_id:
        results = [a for a in results if a.graph_id == request.graph_id]
    if request.name:
        results = [a for a in results if request.name.lower() in a.name.lower()]

    # Apply pagination
    start = request.offset
    end = start + request.limit
    return results[start:end]


@router.get("/assistants/{assistant_id}", response_model=Assistant)
async def get_assistant(
    assistant_id: str, context: dict[str, Any] = Depends(get_app_context)
) -> Assistant:
    """Get an assistant by ID."""
    _init_default_assistant(context)

    if assistant_id not in _assistants:
        raise HTTPException(status_code=404, detail=f"Assistant {assistant_id} not found")

    return _assistants[assistant_id]


@router.delete("/assistants/{assistant_id}")
async def delete_assistant(
    assistant_id: str, context: dict[str, Any] = Depends(get_app_context)
) -> dict[str, str]:
    """Delete an assistant."""
    if assistant_id not in _assistants:
        raise HTTPException(status_code=404, detail=f"Assistant {assistant_id} not found")

    if assistant_id == "default":
        raise HTTPException(status_code=400, detail="Cannot delete default assistant")

    del _assistants[assistant_id]
    logger.info("assistant_deleted", assistant_id=assistant_id)
    return {"status": "deleted"}


# =============================================================================
# Threads Endpoints
# =============================================================================


@router.post("/threads", response_model=Thread)
async def create_thread(
    request: ThreadCreate, context: dict[str, Any] = Depends(get_app_context)
) -> Thread:
    """Create a new thread."""
    thread_id = request.thread_id or str(uuid.uuid4())
    now = _now_iso()

    if thread_id in _threads:
        raise HTTPException(status_code=409, detail=f"Thread {thread_id} already exists")

    thread = Thread(
        thread_id=thread_id,
        created_at=now,
        updated_at=now,
        metadata=request.metadata or {},
        status="idle",
    )

    _threads[thread_id] = thread
    _enforce_store_limit(_threads)
    logger.info("thread_created", thread_id=thread_id)
    return thread


@router.get("/threads/{thread_id}", response_model=Thread)
async def get_thread(thread_id: str, context: dict[str, Any] = Depends(get_app_context)) -> Thread:
    """Get a thread by ID."""
    if thread_id not in _threads:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    return _threads[thread_id]


@router.delete("/threads/{thread_id}")
async def delete_thread(
    thread_id: str, context: dict[str, Any] = Depends(get_app_context)
) -> dict[str, str]:
    """Delete a thread."""
    if thread_id not in _threads:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    del _threads[thread_id]

    # Clean up associated runs
    runs_to_delete = [r_id for r_id, r in _runs.items() if r.thread_id == thread_id]
    for r_id in runs_to_delete:
        del _runs[r_id]

    logger.info("thread_deleted", thread_id=thread_id)
    return {"status": "deleted"}


@router.get("/threads/{thread_id}/state", response_model=ThreadState)
async def get_thread_state(
    thread_id: str, context: dict[str, Any] = Depends(get_app_context)
) -> ThreadState:
    """Get the state of a thread."""
    graph = context.get("graph")

    if not graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    config = {"configurable": {"thread_id": thread_id}}

    try:
        state = await graph.aget_state(config)

        values = state.values if state.values else {}
        next_nodes = list(state.next) if state.next else []

        # Extract tasks info
        tasks_info = []
        if hasattr(state, "tasks") and state.tasks:
            for task in state.tasks:
                task_info = {"id": str(id(task))}
                if hasattr(task, "interrupts") and task.interrupts:
                    task_info["interrupts"] = [{"value": i.value} for i in task.interrupts]
                tasks_info.append(task_info)

        return ThreadState(
            values=values,
            next=next_nodes,
            tasks=tasks_info,
            metadata=_threads.get(
                thread_id, Thread(thread_id=thread_id, created_at=_now_iso(), updated_at=_now_iso())
            ).metadata,
            created_at=_threads.get(
                thread_id, Thread(thread_id=thread_id, created_at=_now_iso(), updated_at=_now_iso())
            ).created_at,
        )

    except Exception as e:
        logger.error("get_state_error", thread_id=thread_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/threads/{thread_id}/state")
async def update_thread_state(
    thread_id: str, request: ThreadStateUpdate, context: dict[str, Any] = Depends(get_app_context)
) -> ThreadState:
    """Update the state of a thread."""
    graph = context.get("graph")

    if not graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Update state
        await graph.aupdate_state(config, request.values, as_node=request.as_node)

        # Return updated state
        return await get_thread_state(thread_id, context)

    except Exception as e:
        logger.error("update_state_error", thread_id=thread_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# Runs Endpoints
# =============================================================================


@router.post("/threads/{thread_id}/runs", response_model=Run)
async def create_run(
    thread_id: str, request: RunCreate, context: dict[str, Any] = Depends(get_app_context)
) -> Run:
    """Create and execute a run (non-streaming)."""
    graph = context.get("graph")
    agent_registry = context.get("agent_registry")

    if not graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    _init_default_assistant(context)

    # Verify assistant exists
    if request.assistant_id not in _assistants:
        raise HTTPException(status_code=404, detail=f"Assistant {request.assistant_id} not found")

    run_id = str(uuid.uuid4())
    now = _now_iso()

    # Create run record
    run = Run(
        run_id=run_id,
        thread_id=thread_id,
        assistant_id=request.assistant_id,
        status=RunStatus.RUNNING,
        created_at=now,
        updated_at=now,
        metadata=request.metadata or {},
    )
    _runs[run_id] = run
    _enforce_store_limit(_runs)

    # Ensure thread exists
    if thread_id not in _threads:
        _threads[thread_id] = Thread(
            thread_id=thread_id, created_at=now, updated_at=now, status="busy"
        )
    else:
        _threads[thread_id].status = "busy"
        _threads[thread_id].updated_at = now

    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Check if resuming
        state = await graph.aget_state(config)
        is_resuming = state.next is not None

        roster = []
        if agent_registry and hasattr(agent_registry, "get_roster"):
            roster = agent_registry.get_roster()

        if is_resuming:
            # Resume with input
            input_value = request.input or {}
            resume_value = input_value.get("messages", [{}])[-1].get("content", "")
            await graph.ainvoke(Command(resume=resume_value), config)
        else:
            # New run
            input_value = request.input or {}
            messages = input_value.get("messages", [])

            initial_state = create_initial_state(
                messages=messages, roster=roster, thread_id=thread_id
            )
            await graph.ainvoke(initial_state, config)

        # Check if interrupted
        state = await graph.aget_state(config)
        if state.next:
            run.status = RunStatus.INTERRUPTED
            _threads[thread_id].status = "interrupted"
        else:
            run.status = RunStatus.SUCCESS
            _threads[thread_id].status = "idle"

        run.updated_at = _now_iso()
        _threads[thread_id].updated_at = _now_iso()

        logger.info("run_completed", run_id=run_id, status=run.status.value)
        return run

    except Exception as e:
        run.status = RunStatus.ERROR
        run.updated_at = _now_iso()
        _threads[thread_id].status = "error"
        logger.error("run_error", run_id=run_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/threads/{thread_id}/runs/stream")
async def create_run_stream(
    thread_id: str, request: RunCreate, context: dict[str, Any] = Depends(get_app_context)
):
    """Create and execute a run with streaming."""
    graph = context.get("graph")
    agent_registry = context.get("agent_registry")

    if not graph:
        raise HTTPException(status_code=503, detail="Graph not initialized")

    _init_default_assistant(context)

    if request.assistant_id not in _assistants:
        raise HTTPException(status_code=404, detail=f"Assistant {request.assistant_id} not found")

    run_id = str(uuid.uuid4())

    return StreamingResponse(
        _stream_run(
            graph=graph,
            agent_registry=agent_registry,
            thread_id=thread_id,
            run_id=run_id,
            request=request,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


async def _stream_run(graph, agent_registry, thread_id: str, run_id: str, request: RunCreate):
    """Stream run execution."""
    now = _now_iso()

    # Create run record
    run = Run(
        run_id=run_id,
        thread_id=thread_id,
        assistant_id=request.assistant_id,
        status=RunStatus.RUNNING,
        created_at=now,
        updated_at=now,
        metadata=request.metadata or {},
    )
    _runs[run_id] = run

    # Ensure thread exists
    if thread_id not in _threads:
        _threads[thread_id] = Thread(
            thread_id=thread_id, created_at=now, updated_at=now, status="busy"
        )

    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Check if resuming
        state = await graph.aget_state(config)
        is_resuming = state.next is not None

        roster = []
        if agent_registry and hasattr(agent_registry, "get_roster"):
            roster = agent_registry.get_roster()

        # Send metadata event
        yield f"event: metadata\ndata: {json.dumps({'run_id': run_id})}\n\n"

        if is_resuming:
            input_value = request.input or {}
            resume_value = input_value.get("messages", [{}])[-1].get("content", "")

            async for event in graph.astream_events(
                Command(resume=resume_value), config=config, version="v2"
            ):
                sse_event = _format_studio_event(event)
                if sse_event:
                    yield sse_event
        else:
            input_value = request.input or {}
            messages = input_value.get("messages", [])

            initial_state = create_initial_state(
                messages=messages, roster=roster, thread_id=thread_id
            )

            async for event in graph.astream_events(initial_state, config=config, version="v2"):
                sse_event = _format_studio_event(event)
                if sse_event:
                    yield sse_event

        # Check final state
        state = await graph.aget_state(config)
        if state.next:
            run.status = RunStatus.INTERRUPTED
            _threads[thread_id].status = "interrupted"

            # Send interrupt event
            tasks = getattr(state, "tasks", [])
            if tasks and hasattr(tasks[0], "interrupts") and tasks[0].interrupts:
                interrupt_value = tasks[0].interrupts[0].value
                # Sanitize interrupt value to prevent leaking internal state
                safe_value = (
                    str(interrupt_value)
                    if isinstance(interrupt_value, str)
                    else {"message": str(interrupt_value)}
                )
                yield f"event: interrupt\ndata: {json.dumps(safe_value)}\n\n"
        else:
            run.status = RunStatus.SUCCESS
            _threads[thread_id].status = "idle"

        run.updated_at = _now_iso()

        # Send end event
        yield f"event: end\ndata: {json.dumps({'status': run.status.value})}\n\n"

    except Exception as e:
        run.status = RunStatus.ERROR
        logger.error("stream_run_error", run_id=run_id, error=str(e))
        yield f"event: error\ndata: {json.dumps({'error': 'Internal server error'})}\n\n"


def _format_studio_event(event: dict[str, Any]) -> str | None:
    """Format a LangGraph event for Studio streaming."""
    event_name = event.get("event", "")
    event_data = event.get("data", {})

    if event_name == "on_chain_stream":
        chunk = event_data.get("chunk", {})
        if chunk:
            return f"event: updates\ndata: {json.dumps(chunk)}\n\n"

    elif event_name == "on_chat_model_stream":
        chunk = event_data.get("chunk", {})
        if hasattr(chunk, "content") and chunk.content:
            return f"event: messages\ndata: {json.dumps({'content': chunk.content})}\n\n"

    elif event_name == "on_tool_start":
        return f"event: events\ndata: {json.dumps({'type': 'tool_start', 'name': event_data.get('name')})}\n\n"

    elif event_name == "on_tool_end":
        return f"event: events\ndata: {json.dumps({'type': 'tool_end', 'name': event_data.get('name')})}\n\n"

    return None


@router.get("/threads/{thread_id}/runs/{run_id}", response_model=Run)
async def get_run(
    thread_id: str, run_id: str, context: dict[str, Any] = Depends(get_app_context)
) -> Run:
    """Get a run by ID."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run = _runs[run_id]
    if run.thread_id != thread_id:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found in thread {thread_id}")

    return run


@router.get("/threads/{thread_id}/runs", response_model=list[Run])
async def list_runs(
    thread_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    context: dict[str, Any] = Depends(get_app_context),
) -> list[Run]:
    """List runs for a thread."""
    runs = [r for r in _runs.values() if r.thread_id == thread_id]
    runs.sort(key=lambda r: r.created_at, reverse=True)
    return runs[offset : offset + limit]


# =============================================================================
# Resume Endpoint (for interrupted runs)
# =============================================================================


@router.post("/threads/{thread_id}/runs/{run_id}/resume", response_model=Run)
async def resume_run(
    thread_id: str,
    run_id: str,
    request: RunCreate,
    context: dict[str, Any] = Depends(get_app_context),
) -> Run:
    """Resume an interrupted run."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run = _runs[run_id]
    if run.status != RunStatus.INTERRUPTED:
        raise HTTPException(
            status_code=400, detail=f"Run {run_id} is not interrupted (status: {run.status.value})"
        )

    # Create a new run for the resume
    return await create_run(thread_id, request, context)
