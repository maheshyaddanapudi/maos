"""SSE streaming helpers for the API."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import structlog

from maos.api.models import StreamEvent, StreamEventType

logger = structlog.get_logger()


def format_sse_event(event_type: str, data: dict[str, Any]) -> str:
    """
    Format an event for Server-Sent Events.

    Args:
        event_type: The event type.
        data: The event data.

    Returns:
        Formatted SSE string.
    """
    json_data = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {json_data}\n\n"


def create_stream_event(event_type: StreamEventType, data: dict[str, Any]) -> StreamEvent:
    """
    Create a stream event.

    Args:
        event_type: Type of event.
        data: Event data.

    Returns:
        StreamEvent instance.
    """
    return StreamEvent(event=event_type, data=data, timestamp=datetime.now(UTC))


async def stream_graph_events(
    graph: Any, initial_state: dict[str, Any], config: dict[str, Any]
) -> AsyncIterator[str]:
    """
    Stream events from graph execution.

    Args:
        graph: Compiled LangGraph.
        initial_state: Initial graph state.
        config: Graph config with thread_id.

    Yields:
        SSE-formatted event strings.
    """
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")

    try:
        async for event in graph.astream_events(initial_state, config=config, version="v2"):
            event_name = event.get("event", "")
            event_data = event.get("data", {})

            # Handle different event types
            if event_name == "on_chain_stream":
                chunk = event_data.get("chunk", {})
                if isinstance(chunk, dict):
                    # Check for messages
                    messages = chunk.get("messages", [])
                    if messages:
                        for msg in messages:
                            if isinstance(msg, dict) and msg.get("content"):
                                yield format_sse_event(
                                    StreamEventType.CHUNK.value, {"content": msg.get("content", "")}
                                )

                    # Check for supervisor decision
                    if "next" in chunk:
                        yield format_sse_event(
                            StreamEventType.SUPERVISOR_DECISION.value,
                            {"next": chunk.get("next"), "iteration": chunk.get("iteration", 0)},
                        )

            elif event_name == "on_tool_start":
                yield format_sse_event(
                    StreamEventType.TOOL_CALL.value,
                    {
                        "tool_name": event_data.get("name", "unknown"),
                        "input": event_data.get("input", {}),
                    },
                )

            elif event_name == "on_tool_end":
                yield format_sse_event(
                    StreamEventType.TOOL_RESULT.value,
                    {
                        "tool_name": event_data.get("name", "unknown"),
                        "output": str(event_data.get("output", ""))[
                            :1000
                        ],  # Truncate large outputs
                    },
                )

            elif event_name == "on_chain_start":
                # Check if it's a worker starting
                run_name = event.get("name", "")
                if run_name and run_name not in ["supervisor", "RunnableSequence"]:
                    yield format_sse_event(StreamEventType.WORKER_START.value, {"worker": run_name})

            elif event_name == "on_chain_end":
                # Check if it's a worker ending
                run_name = event.get("name", "")
                if run_name and run_name not in ["supervisor", "RunnableSequence"]:
                    yield format_sse_event(StreamEventType.WORKER_END.value, {"worker": run_name})

        # Check for interrupts after streaming
        state = await graph.aget_state(config)
        if state.next:
            # Graph is waiting for input
            tasks = getattr(state, "tasks", [])
            if tasks and hasattr(tasks[0], "interrupts") and tasks[0].interrupts:
                interrupt_value = tasks[0].interrupts[0].value
                if (
                    isinstance(interrupt_value, dict)
                    and interrupt_value.get("type") == "input_required"
                ):
                    yield format_sse_event(
                        StreamEventType.INPUT_REQUIRED.value,
                        {"prompt": interrupt_value.get("prompt", ""), "thread_id": thread_id},
                    )
                    return

        # Stream completed successfully
        yield format_sse_event(StreamEventType.DONE.value, {"thread_id": thread_id})

    except Exception as e:
        logger.error("stream_error", error=str(e), thread_id=thread_id)
        yield format_sse_event(
            StreamEventType.ERROR.value,
            {"error": "Internal server error", "thread_id": thread_id},
        )


async def stream_simple_response(
    content: str, thread_id: str, chunk_size: int = 20
) -> AsyncIterator[str]:
    """
    Stream a simple text response in chunks.

    Args:
        content: The content to stream.
        thread_id: Thread ID.
        chunk_size: Size of each chunk.

    Yields:
        SSE-formatted event strings.
    """
    # Stream content in chunks
    for i in range(0, len(content), chunk_size):
        chunk = content[i : i + chunk_size]
        yield format_sse_event(StreamEventType.CHUNK.value, {"content": chunk})
        await asyncio.sleep(0.01)  # Small delay for realistic streaming

    # Done event
    yield format_sse_event(StreamEventType.DONE.value, {"thread_id": thread_id})


class OpenAIStreamFormatter:
    """Helper for formatting OpenAI-compatible stream chunks."""

    def __init__(self, model: str = "maos"):
        self.model = model
        self._id = f"chatcmpl-{datetime.now(UTC).timestamp()}"
        self._created = int(datetime.now(UTC).timestamp())

    def format_chunk(
        self, content: str | None = None, role: str | None = None, finish_reason: str | None = None
    ) -> str:
        """Format a chunk in OpenAI streaming format."""
        delta = {}
        if role:
            delta["role"] = role
        if content:
            delta["content"] = content

        chunk = {
            "id": self._id,
            "object": "chat.completion.chunk",
            "created": self._created,
            "model": self.model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }

        return f"data: {json.dumps(chunk)}\n\n"

    def format_done(self) -> str:
        """Format the done marker."""
        return "data: [DONE]\n\n"


async def stream_openai_response(
    graph: Any, initial_state: dict[str, Any], config: dict[str, Any], model: str = "maos"
) -> AsyncIterator[str]:
    """
    Stream graph execution in OpenAI-compatible format.

    Args:
        graph: Compiled LangGraph.
        initial_state: Initial graph state.
        config: Graph config.
        model: Model name to report.

    Yields:
        OpenAI-formatted stream strings.
    """
    formatter = OpenAIStreamFormatter(model=model)
    first_chunk = True

    try:
        async for event in graph.astream_events(initial_state, config=config, version="v2"):
            event_name = event.get("event", "")
            event_data = event.get("data", {})

            if event_name == "on_chain_stream":
                chunk = event_data.get("chunk", {})
                if isinstance(chunk, dict):
                    messages = chunk.get("messages", [])
                    for msg in messages:
                        if isinstance(msg, dict):
                            content = msg.get("content", "")
                            if content:
                                if first_chunk:
                                    yield formatter.format_chunk(role="assistant")
                                    first_chunk = False
                                yield formatter.format_chunk(content=content)

        # Final chunk with finish reason
        yield formatter.format_chunk(finish_reason="stop")
        yield formatter.format_done()

    except Exception as e:
        logger.error("openai_stream_error", error=str(e))
        if first_chunk:
            yield formatter.format_chunk(role="assistant")
        yield formatter.format_chunk(content="An error occurred while processing your request.")
        yield formatter.format_chunk(finish_reason="stop")
        yield formatter.format_done()


async def stream_openai_response_with_interrupt(
    graph: Any,
    config: dict[str, Any],
    roster: list[str],
    messages: list[Any],
    is_resuming: bool,
    latest_user_message: str,
    model: str = "maos",
    thread_id: str = "",
) -> AsyncIterator[str]:
    """
    Stream graph execution in OpenAI-compatible format with interrupt handling.

    This function handles both new conversations and resuming interrupted ones.
    When the graph interrupts (via send_message), the interrupt message is
    streamed as a normal assistant response.

    Args:
        graph: Compiled LangGraph.
        config: Graph config with thread_id.
        roster: List of available agents.
        messages: Request messages.
        is_resuming: Whether we're resuming a paused conversation.
        latest_user_message: The most recent user message.
        model: Model name to report.
        thread_id: Thread ID for conversation tracking.

    Yields:
        OpenAI-formatted stream strings.
    """
    from langgraph.types import Command

    from maos.graph.state import create_initial_state

    formatter = OpenAIStreamFormatter(model=model)
    first_chunk = True
    collected_content = []

    try:
        if is_resuming:
            # Resume with Command
            logger.info("openai_stream_resume", thread_id=thread_id)

            async for event in graph.astream_events(
                Command(resume=latest_user_message), config=config, version="v2"
            ):
                chunk_content = _extract_stream_content(event)
                if chunk_content:
                    if first_chunk:
                        yield formatter.format_chunk(role="assistant")
                        first_chunk = False
                    yield formatter.format_chunk(content=chunk_content)
                    collected_content.append(chunk_content)
        else:
            # New conversation
            logger.info("openai_stream_start", thread_id=thread_id)

            # Convert messages
            msg_dicts = [
                {"role": msg.role, "content": msg.content, "name": msg.name} for msg in messages
            ]

            initial_state = create_initial_state(
                messages=msg_dicts, roster=roster, thread_id=thread_id
            )

            async for event in graph.astream_events(initial_state, config=config, version="v2"):
                chunk_content = _extract_stream_content(event)
                if chunk_content:
                    if first_chunk:
                        yield formatter.format_chunk(role="assistant")
                        first_chunk = False
                    yield formatter.format_chunk(content=chunk_content)
                    collected_content.append(chunk_content)

        # Check if graph is interrupted
        state = await graph.aget_state(config)
        if state.next:
            # Graph is paused - extract interrupt message
            interrupt_msg = _extract_interrupt_from_state(state)
            if interrupt_msg:
                logger.info("openai_stream_interrupted", thread_id=thread_id)
                # Stream the interrupt message as normal content
                if first_chunk:
                    yield formatter.format_chunk(role="assistant")
                    first_chunk = False
                yield formatter.format_chunk(content=interrupt_msg)

        # Final chunk with finish reason
        yield formatter.format_chunk(finish_reason="stop")
        yield formatter.format_done()

    except Exception as e:
        logger.error("openai_stream_error", error=str(e), thread_id=thread_id)
        if first_chunk:
            yield formatter.format_chunk(role="assistant")
        yield formatter.format_chunk(content="An error occurred while processing your request.")
        yield formatter.format_chunk(finish_reason="stop")
        yield formatter.format_done()


def _extract_stream_content(event: dict[str, Any]) -> str | None:
    """Extract content from a stream event."""
    event_name = event.get("event", "")
    event_data = event.get("data", {})

    if event_name == "on_chain_stream":
        chunk = event_data.get("chunk", {})
        if isinstance(chunk, dict):
            messages = chunk.get("messages", [])
            for msg in messages:
                # Handle AIMessage objects
                if hasattr(msg, "type") and msg.type == "ai":
                    content = getattr(msg, "content", "")
                    if content:
                        return str(content)
                # Handle dict messages
                elif isinstance(msg, dict):
                    content = msg.get("content", "")
                    if content:
                        return str(content)

    return None


def _extract_interrupt_from_state(state: Any) -> str | None:
    """Extract interrupt message from graph state."""
    tasks = getattr(state, "tasks", [])
    if tasks and hasattr(tasks[0], "interrupts") and tasks[0].interrupts:
        interrupt_value = tasks[0].interrupts[0].value
        if isinstance(interrupt_value, dict) and interrupt_value.get("type") == "input_required":
            return str(interrupt_value.get("prompt", ""))
    return None
