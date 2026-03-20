"""Tests for SSE streaming helpers."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from maos.api.models import StreamEventType
from maos.api.streaming import (
    OpenAIStreamFormatter,
    _extract_interrupt_from_state,
    _extract_stream_content,
    create_stream_event,
    format_sse_event,
    stream_graph_events,
    stream_openai_response,
    stream_simple_response,
)

# ── format_sse_event ─────────────────────────────────────────────────────────


class TestFormatSSEEvent:
    def test_basic_format(self):
        result = format_sse_event("chunk", {"content": "hello"})
        assert result.startswith("event: chunk\n")
        assert "data: " in result
        assert result.endswith("\n\n")
        data = json.loads(result.split("data: ")[1].strip())
        assert data["content"] == "hello"

    def test_with_datetime(self):
        now = datetime(2024, 1, 1, 12, 0, 0)
        result = format_sse_event("test", {"timestamp": now})
        assert "2024-01-01" in result

    def test_with_nested_data(self):
        result = format_sse_event("test", {
            "nested": {"key": "value"},
            "list": [1, 2, 3],
        })
        data = json.loads(result.split("data: ")[1].strip())
        assert data["nested"]["key"] == "value"
        assert data["list"] == [1, 2, 3]


# ── create_stream_event ──────────────────────────────────────────────────────


class TestCreateStreamEvent:
    def test_creates_event(self):
        event = create_stream_event(StreamEventType.CHUNK, {"content": "hi"})
        assert event.event == StreamEventType.CHUNK
        assert event.data == {"content": "hi"}
        assert event.timestamp is not None

    def test_different_event_types(self):
        for event_type in [
            StreamEventType.CHUNK,
            StreamEventType.DONE,
            StreamEventType.ERROR,
        ]:
            event = create_stream_event(event_type, {"key": "value"})
            assert event.event == event_type


# ── stream_simple_response ───────────────────────────────────────────────────


class TestStreamSimpleResponse:
    @pytest.mark.asyncio
    async def test_short_content(self):
        chunks = []
        async for chunk in stream_simple_response("Hi", "thread-1", chunk_size=20):
            chunks.append(chunk)
        assert len(chunks) == 2  # content + done
        data = json.loads(chunks[0].split("data: ")[1].strip())
        assert data["content"] == "Hi"
        assert "done" in chunks[-1]

    @pytest.mark.asyncio
    async def test_long_content_chunked(self):
        content = "Hello World! This is a test."
        chunks = []
        async for chunk in stream_simple_response(content, "t1", chunk_size=5):
            chunks.append(chunk)
        # 27 chars / 5 = 6 content chunks + 1 done
        assert len(chunks) == 7

    @pytest.mark.asyncio
    async def test_empty_content(self):
        chunks = []
        async for chunk in stream_simple_response("", "t1"):
            chunks.append(chunk)
        assert len(chunks) == 1  # only done


# ── OpenAIStreamFormatter ────────────────────────────────────────────────────


class TestOpenAIStreamFormatter:
    def test_init(self):
        formatter = OpenAIStreamFormatter(model="gpt-4o")
        assert formatter.model == "gpt-4o"
        assert formatter._id.startswith("chatcmpl-")
        assert isinstance(formatter._created, int)

    def test_format_chunk_role(self):
        formatter = OpenAIStreamFormatter()
        result = formatter.format_chunk(role="assistant")
        assert result.startswith("data: ")
        data = json.loads(result[6:].strip())
        assert data["choices"][0]["delta"]["role"] == "assistant"
        assert "content" not in data["choices"][0]["delta"]

    def test_format_chunk_content(self):
        formatter = OpenAIStreamFormatter()
        result = formatter.format_chunk(content="Hello")
        data = json.loads(result[6:].strip())
        assert data["choices"][0]["delta"]["content"] == "Hello"
        assert "role" not in data["choices"][0]["delta"]

    def test_format_chunk_finish_reason(self):
        formatter = OpenAIStreamFormatter()
        result = formatter.format_chunk(finish_reason="stop")
        data = json.loads(result[6:].strip())
        assert data["choices"][0]["finish_reason"] == "stop"

    def test_format_chunk_model(self):
        formatter = OpenAIStreamFormatter(model="test-model")
        result = formatter.format_chunk(content="x")
        data = json.loads(result[6:].strip())
        assert data["model"] == "test-model"
        assert data["object"] == "chat.completion.chunk"

    def test_format_done(self):
        formatter = OpenAIStreamFormatter()
        assert formatter.format_done() == "data: [DONE]\n\n"

    def test_consistent_id(self):
        formatter = OpenAIStreamFormatter()
        r1 = json.loads(formatter.format_chunk(content="a")[6:].strip())
        r2 = json.loads(formatter.format_chunk(content="b")[6:].strip())
        assert r1["id"] == r2["id"]
        assert r1["created"] == r2["created"]


# ── _extract_stream_content ──────────────────────────────────────────────────


class TestExtractStreamContent:
    def test_dict_message(self):
        event = {
            "event": "on_chain_stream",
            "data": {
                "chunk": {
                    "messages": [{"content": "Hello", "role": "assistant"}]
                }
            },
        }
        assert _extract_stream_content(event) == "Hello"

    def test_ai_message_object(self):
        event = {
            "event": "on_chain_stream",
            "data": {
                "chunk": {
                    "messages": [AIMessage(content="World")]
                }
            },
        }
        assert _extract_stream_content(event) == "World"

    def test_empty_content(self):
        event = {
            "event": "on_chain_stream",
            "data": {
                "chunk": {
                    "messages": [{"content": "", "role": "assistant"}]
                }
            },
        }
        assert _extract_stream_content(event) is None

    def test_no_messages(self):
        event = {
            "event": "on_chain_stream",
            "data": {"chunk": {"messages": []}},
        }
        assert _extract_stream_content(event) is None

    def test_non_chain_stream(self):
        event = {"event": "on_tool_start", "data": {}}
        assert _extract_stream_content(event) is None

    def test_non_dict_chunk(self):
        event = {
            "event": "on_chain_stream",
            "data": {"chunk": "not_a_dict"},
        }
        assert _extract_stream_content(event) is None


# ── _extract_interrupt_from_state ────────────────────────────────────────────


class TestExtractInterruptFromState:
    def test_valid_interrupt(self):
        interrupt = MagicMock()
        interrupt.value = {"type": "input_required", "prompt": "Please confirm"}
        task = MagicMock()
        task.interrupts = [interrupt]
        state = MagicMock()
        state.tasks = [task]
        assert _extract_interrupt_from_state(state) == "Please confirm"

    def test_no_tasks(self):
        state = MagicMock()
        state.tasks = []
        assert _extract_interrupt_from_state(state) is None

    def test_no_interrupts(self):
        task = MagicMock()
        task.interrupts = []
        state = MagicMock()
        state.tasks = [task]
        assert _extract_interrupt_from_state(state) is None

    def test_wrong_interrupt_type(self):
        interrupt = MagicMock()
        interrupt.value = {"type": "other", "prompt": "something"}
        task = MagicMock()
        task.interrupts = [interrupt]
        state = MagicMock()
        state.tasks = [task]
        assert _extract_interrupt_from_state(state) is None

    def test_no_tasks_attribute(self):
        state = MagicMock(spec=[])
        assert _extract_interrupt_from_state(state) is None

    def test_no_interrupts_attribute(self):
        task = MagicMock(spec=[])
        state = MagicMock()
        state.tasks = [task]
        assert _extract_interrupt_from_state(state) is None

    def test_non_dict_interrupt_value(self):
        interrupt = MagicMock()
        interrupt.value = "just a string"
        task = MagicMock()
        task.interrupts = [interrupt]
        state = MagicMock()
        state.tasks = [task]
        assert _extract_interrupt_from_state(state) is None


# ── stream_graph_events ──────────────────────────────────────────────────────


class TestStreamGraphEvents:
    @pytest.mark.asyncio
    async def test_chunk_event(self):
        async def mock_events(*args, **kwargs):
            yield {
                "event": "on_chain_stream",
                "data": {
                    "chunk": {
                        "messages": [{"content": "Hello", "role": "assistant"}]
                    }
                },
            }

        graph = MagicMock()
        graph.astream_events = mock_events
        state_mock = MagicMock()
        state_mock.next = None
        graph.aget_state = AsyncMock(return_value=state_mock)

        chunks = []
        async for chunk in stream_graph_events(
            graph, {}, {"configurable": {"thread_id": "t1"}}
        ):
            chunks.append(chunk)

        assert len(chunks) == 2  # chunk + done
        assert "chunk" in chunks[0]

    @pytest.mark.asyncio
    async def test_supervisor_decision_event(self):
        async def mock_events(*args, **kwargs):
            yield {
                "event": "on_chain_stream",
                "data": {
                    "chunk": {"next": "worker1", "iteration": 2}
                },
            }

        graph = MagicMock()
        graph.astream_events = mock_events
        state_mock = MagicMock()
        state_mock.next = None
        graph.aget_state = AsyncMock(return_value=state_mock)

        chunks = []
        async for chunk in stream_graph_events(graph, {}, {"configurable": {}}):
            chunks.append(chunk)

        assert any("supervisor_decision" in c for c in chunks)

    @pytest.mark.asyncio
    async def test_tool_events(self):
        async def mock_events(*args, **kwargs):
            yield {
                "event": "on_tool_start",
                "data": {"name": "search", "input": {"q": "test"}},
            }
            yield {
                "event": "on_tool_end",
                "data": {"name": "search", "output": "result"},
            }

        graph = MagicMock()
        graph.astream_events = mock_events
        state_mock = MagicMock()
        state_mock.next = None
        graph.aget_state = AsyncMock(return_value=state_mock)

        chunks = []
        async for chunk in stream_graph_events(graph, {}, {"configurable": {}}):
            chunks.append(chunk)

        assert any("tool_call" in c for c in chunks)
        assert any("tool_result" in c for c in chunks)

    @pytest.mark.asyncio
    async def test_worker_start_end(self):
        async def mock_events(*args, **kwargs):
            yield {"event": "on_chain_start", "name": "research_agent", "data": {}}
            yield {"event": "on_chain_end", "name": "research_agent", "data": {}}

        graph = MagicMock()
        graph.astream_events = mock_events
        state_mock = MagicMock()
        state_mock.next = None
        graph.aget_state = AsyncMock(return_value=state_mock)

        chunks = []
        async for chunk in stream_graph_events(graph, {}, {"configurable": {}}):
            chunks.append(chunk)

        assert any("worker_start" in c for c in chunks)
        assert any("worker_end" in c for c in chunks)

    @pytest.mark.asyncio
    async def test_filters_supervisor_chain(self):
        async def mock_events(*args, **kwargs):
            yield {"event": "on_chain_start", "name": "supervisor", "data": {}}
            yield {"event": "on_chain_start", "name": "RunnableSequence", "data": {}}

        graph = MagicMock()
        graph.astream_events = mock_events
        state_mock = MagicMock()
        state_mock.next = None
        graph.aget_state = AsyncMock(return_value=state_mock)

        chunks = []
        async for chunk in stream_graph_events(graph, {}, {"configurable": {}}):
            chunks.append(chunk)

        # Should only have done event, no worker_start for supervisor/RunnableSequence
        assert not any("worker_start" in c for c in chunks)

    @pytest.mark.asyncio
    async def test_interrupt_detection(self):
        async def mock_events(*args, **kwargs):
            yield {
                "event": "on_chain_stream",
                "data": {"chunk": {"messages": [{"content": "Hi"}]}},
            }

        interrupt_val = MagicMock()
        interrupt_val.value = {"type": "input_required", "prompt": "Need input"}
        task = MagicMock()
        task.interrupts = [interrupt_val]
        state_mock = MagicMock()
        state_mock.next = "some_node"
        state_mock.tasks = [task]

        graph = MagicMock()
        graph.astream_events = mock_events
        graph.aget_state = AsyncMock(return_value=state_mock)

        chunks = []
        async for chunk in stream_graph_events(
            graph, {}, {"configurable": {"thread_id": "t1"}}
        ):
            chunks.append(chunk)

        assert any("input_required" in c for c in chunks)
        assert not any("done" in c and "input_required" not in c for c in chunks)

    @pytest.mark.asyncio
    async def test_error_handling(self):
        async def mock_events(*args, **kwargs):
            raise RuntimeError("Graph failed")
            yield  # noqa: F811 - unreachable yield makes it async generator

        graph = MagicMock()
        graph.astream_events = mock_events

        chunks = []
        async for chunk in stream_graph_events(graph, {}, {"configurable": {}}):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert "error" in chunks[0]
        assert "Graph failed" in chunks[0]


# ── stream_openai_response ───────────────────────────────────────────────────


class TestStreamOpenAIResponse:
    @pytest.mark.asyncio
    async def test_basic_stream(self):
        async def mock_events(*args, **kwargs):
            yield {
                "event": "on_chain_stream",
                "data": {
                    "chunk": {
                        "messages": [{"content": "Hello", "role": "assistant"}]
                    }
                },
            }

        graph = MagicMock()
        graph.astream_events = mock_events

        chunks = []
        async for chunk in stream_openai_response(graph, {}, {}):
            chunks.append(chunk)

        # role chunk + content chunk + finish_reason chunk + done
        assert len(chunks) == 4
        assert "assistant" in chunks[0]
        assert "Hello" in chunks[1]
        assert "stop" in chunks[2]
        assert "[DONE]" in chunks[3]

    @pytest.mark.asyncio
    async def test_error_stream(self):
        async def mock_events(*args, **kwargs):
            raise ValueError("boom")
            yield  # noqa

        graph = MagicMock()
        graph.astream_events = mock_events

        chunks = []
        async for chunk in stream_openai_response(graph, {}, {}):
            chunks.append(chunk)

        assert any("Error: boom" in c for c in chunks)
        assert chunks[-1] == "data: [DONE]\n\n"
