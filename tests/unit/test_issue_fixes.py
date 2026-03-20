"""Tests for Issues 7-11 fixes.

Issue 7:  Whiteboard hypotheses populated from agent responses
Issue 8:  Trimmed message history in _invoke_agent
Issue 9:  No dual system prompts in House MD factory
Issue 10: SSE streaming handles AIMessage objects
Issue 11: Non-streaming response builder handles AIMessage objects
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from maos.api.routes.chat import _build_response_messages
from maos.api.streaming import (
    _extract_message_content,
    stream_graph_events,
)
from maos.house_md.graphs.critique_round import (
    _find_existing_hypothesis,
    extract_hypotheses,
    run_critique_round,
)
from maos.house_md.graphs.factory import (
    _MAX_CONTEXT_MESSAGES,
    _invoke_agent,
)
from maos.house_md.graphs.states import DiagnosticPhase
from maos.house_md.memory.whiteboard import Whiteboard
from maos.house_md.personalities.base import (
    PersonalityConfig,
    PersonalityWrapper,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_state(**overrides) -> dict[str, Any]:
    """Create a minimal DiagnosticState dict for testing."""
    wb = Whiteboard()
    wb.add_symptom("test symptom")
    defaults: dict[str, Any] = {
        "messages": [HumanMessage(content="test symptom")],
        "symptoms": ["test symptom"],
        "hypotheses": [],
        "evidence": {},
        "current_phase": DiagnosticPhase.INTAKE.value,
        "agent_beliefs": {},
        "whiteboard": wb.to_dict(),
        "final_diagnosis": None,
        "confidence": 0.0,
        "iteration": 0,
        "active_team": ["house", "foreman", "chase"],
    }
    defaults.update(overrides)
    return defaults


def _mock_personality_agent(response_text: str = "mock response") -> PersonalityWrapper:
    """Create a mock PersonalityWrapper that returns a canned response."""
    base = AsyncMock()
    base.ainvoke = AsyncMock(
        return_value={
            "messages": [AIMessage(content=response_text, name="mock")]
        }
    )
    personality = PersonalityConfig(
        name="TestAgent",
        role_description="test",
        system_prompt_additions="test",
    )
    return PersonalityWrapper(base_agent=base, personality=personality)


# ══════════════════════════════════════════════════════════════════════════════
# Issue 7: Hypothesis extraction and whiteboard population
# ══════════════════════════════════════════════════════════════════════════════


class TestExtractHypotheses:
    """Test the extract_hypotheses function."""

    def test_structured_hypothesis_marker(self):
        content = (
            "After reviewing the symptoms, I believe:\n"
            "HYPOTHESIS: Database connection pool exhaustion due to ORM upgrade\n"
            "This is supported by the timing correlation."
        )
        results = extract_hypotheses(content, "chase")
        assert len(results) == 1
        assert "connection pool exhaustion" in results[0]["hypothesis"].lower()
        assert results[0]["confidence"] == 0.5

    def test_multiple_structured_hypotheses(self):
        content = (
            "HYPOTHESIS: Race condition in connection pool\n"
            "HYPOTHESIS: ORM query optimization disabled\n"
        )
        results = extract_hypotheses(content, "foreman")
        assert len(results) == 2

    def test_hypothesis_with_confidence_percentage(self):
        content = "HYPOTHESIS: Memory leak in handler (75% confident)"
        results = extract_hypotheses(content, "cameron")
        assert len(results) == 1
        assert results[0]["confidence"] == 0.75

    def test_case_insensitive_marker(self):
        content = "hypothesis: connection timeout under load"
        results = extract_hypotheses(content, "chase")
        assert len(results) == 1

    def test_heuristic_root_cause(self):
        content = "I believe the root cause is a misconfigured thread pool."
        results = extract_hypotheses(content, "thirteen")
        assert len(results) >= 1
        assert any("thread pool" in h["hypothesis"].lower() for h in results)

    def test_heuristic_likely_caused_by(self):
        content = "This is likely caused by a deadlock in the connection handler."
        results = extract_hypotheses(content, "foreman")
        assert len(results) >= 1

    def test_heuristic_problem_is(self):
        content = "The issue is a stale cache invalidation after the upgrade."
        results = extract_hypotheses(content, "chase")
        assert len(results) >= 1

    def test_no_hypotheses_in_generic_text(self):
        content = "I agree with the team's assessment. Let's run more tests."
        results = extract_hypotheses(content, "cameron")
        assert len(results) == 0

    def test_short_text_ignored(self):
        content = "HYPOTHESIS: bug"
        results = extract_hypotheses(content, "chase")
        # "bug" is too short (<=5 chars)
        assert len(results) == 0

    def test_structured_takes_priority_over_heuristic(self):
        content = (
            "HYPOTHESIS: Thread pool saturation\n"
            "I think the root cause is a thread pool saturation issue."
        )
        results = extract_hypotheses(content, "chase")
        # Should only return the structured one (not a duplicate from heuristic)
        assert len(results) == 1
        assert "thread pool" in results[0]["hypothesis"].lower()

    def test_high_confidence_keyword(self):
        content = "HYPOTHESIS: ORM bug (I'm very confident about this)"
        results = extract_hypotheses(content, "foreman")
        assert len(results) == 1
        assert results[0]["confidence"] == 0.7

    def test_low_confidence_keyword(self):
        content = "HYPOTHESIS: Kernel bug (unlikely but possible)"
        results = extract_hypotheses(content, "thirteen")
        assert len(results) == 1
        assert results[0]["confidence"] == 0.3


class TestFindExistingHypothesis:
    def test_exact_match(self):
        wb = Whiteboard()
        wb.add_hypothesis("connection pool exhaustion", "foreman")
        result = _find_existing_hypothesis(wb, "connection pool exhaustion")
        assert result is not None
        assert result.hypothesis == "connection pool exhaustion"

    def test_substring_match(self):
        wb = Whiteboard()
        wb.add_hypothesis("connection pool exhaustion due to ORM upgrade", "foreman")
        result = _find_existing_hypothesis(wb, "connection pool exhaustion")
        assert result is not None

    def test_reverse_substring_match(self):
        wb = Whiteboard()
        wb.add_hypothesis("pool exhaustion", "foreman")
        result = _find_existing_hypothesis(wb, "connection pool exhaustion")
        assert result is not None

    def test_no_match(self):
        wb = Whiteboard()
        wb.add_hypothesis("memory leak", "foreman")
        result = _find_existing_hypothesis(wb, "connection pool exhaustion")
        assert result is None

    def test_case_insensitive(self):
        wb = Whiteboard()
        wb.add_hypothesis("Memory Leak", "foreman")
        result = _find_existing_hypothesis(wb, "memory leak")
        assert result is not None


class TestCritiqueRoundHypothesisPopulation:
    """Test that critique round actually populates whiteboard hypotheses."""

    @pytest.mark.asyncio
    async def test_hypothesis_added_to_whiteboard(self):
        state = _make_state(active_team=["chase"])

        async def mock_agent(s):
            return {
                "messages": [
                    AIMessage(
                        content="HYPOTHESIS: Database connection pool exhaustion"
                    )
                ]
            }

        result = await run_critique_round(state, {"chase": mock_agent})

        # Whiteboard should now have the hypothesis
        wb = Whiteboard.from_dict(result["whiteboard"])
        active = wb.get_active_hypotheses()
        assert len(active) == 1
        assert "connection pool exhaustion" in active[0].hypothesis.lower()
        assert active[0].proposer == "chase"

    @pytest.mark.asyncio
    async def test_multiple_agents_add_hypotheses(self):
        state = _make_state(active_team=["foreman", "chase"])

        async def foreman_agent(s):
            return {
                "messages": [AIMessage(content="HYPOTHESIS: ORM regression bug")]
            }

        async def chase_agent(s):
            return {
                "messages": [
                    AIMessage(content="HYPOTHESIS: Thread pool starvation")
                ]
            }

        agents = {"foreman": foreman_agent, "chase": chase_agent}
        result = await run_critique_round(state, agents)

        wb = Whiteboard.from_dict(result["whiteboard"])
        active = wb.get_active_hypotheses()
        assert len(active) == 2
        hyp_texts = {h.hypothesis.lower() for h in active}
        assert any("orm" in h for h in hyp_texts)
        assert any("thread pool" in h for h in hyp_texts)

    @pytest.mark.asyncio
    async def test_duplicate_hypothesis_gets_evidence(self):
        """When two agents propose the same hypothesis, the second adds evidence."""
        state = _make_state(active_team=["foreman", "chase"])

        async def foreman_agent(s):
            return {
                "messages": [
                    AIMessage(content="HYPOTHESIS: Connection pool exhaustion")
                ]
            }

        async def chase_agent(s):
            return {
                "messages": [
                    AIMessage(content="HYPOTHESIS: Connection pool exhaustion")
                ]
            }

        agents = {"foreman": foreman_agent, "chase": chase_agent}
        result = await run_critique_round(state, agents)

        wb = Whiteboard.from_dict(result["whiteboard"])
        active = wb.get_active_hypotheses()
        # Should be one hypothesis with extra evidence, not two
        assert len(active) == 1
        assert active[0].confidence > 0.5  # Boosted by second agent's support

    @pytest.mark.asyncio
    async def test_new_hypotheses_returned_in_result(self):
        state = _make_state(active_team=["chase"])

        async def mock_agent(s):
            return {
                "messages": [AIMessage(content="HYPOTHESIS: Cache invalidation race")]
            }

        result = await run_critique_round(state, {"chase": mock_agent})
        assert len(result["hypotheses"]) == 1
        assert "cache invalidation" in result["hypotheses"][0]["hypothesis"].lower()

    @pytest.mark.asyncio
    async def test_no_hypotheses_when_none_proposed(self):
        state = _make_state(active_team=["cameron"])

        async def mock_agent(s):
            return {
                "messages": [AIMessage(content="I agree with the team.")]
            }

        result = await run_critique_round(state, {"cameron": mock_agent})

        wb = Whiteboard.from_dict(result["whiteboard"])
        assert len(wb.get_active_hypotheses()) == 0
        assert len(result["hypotheses"]) == 0


# ══════════════════════════════════════════════════════════════════════════════
# Issue 8: Trimmed message history
# ══════════════════════════════════════════════════════════════════════════════


class TestTrimmedMessageHistory:
    @pytest.mark.asyncio
    async def test_short_history_not_trimmed(self):
        """Messages below the limit are all passed through."""
        agent = _mock_personality_agent("response")
        state = _make_state(messages=[
            HumanMessage(content="original"),
            AIMessage(content="reply 1"),
            AIMessage(content="reply 2"),
        ])

        await _invoke_agent(agent, state, "test prompt", "house")

        call_args = agent.base_agent.ainvoke.call_args[0][0]
        msgs = call_args["messages"]
        # PersonalityWrapper.enhance_state() prepends a SystemMessage,
        # so: 1 system + 3 original + 1 context/phase = 5
        assert len(msgs) == 5
        # First is personality system message, second is original user msg
        assert isinstance(msgs[0], SystemMessage)
        assert msgs[1].content == "original"

    @pytest.mark.asyncio
    async def test_long_history_trimmed(self):
        """Messages exceeding the limit are trimmed, keeping first + recent."""
        agent = _mock_personality_agent("response")
        many_messages = [HumanMessage(content="original")] + [
            AIMessage(content=f"msg {i}") for i in range(20)
        ]
        state = _make_state(messages=many_messages)

        await _invoke_agent(agent, state, "test prompt", "house")

        call_args = agent.base_agent.ainvoke.call_args[0][0]
        msgs = call_args["messages"]
        # PersonalityWrapper adds SystemMessage, so:
        # 1 system + 1 first msg + _MAX_CONTEXT_MESSAGES recent + 1 context = 13
        assert len(msgs) == 1 + 1 + _MAX_CONTEXT_MESSAGES + 1
        # First is personality system message
        assert isinstance(msgs[0], SystemMessage)
        # Second is preserved original user message
        assert msgs[1].content == "original"
        # Last real message before context is the most recent
        assert msgs[-2].content == "msg 19"

    @pytest.mark.asyncio
    async def test_whiteboard_summary_in_context(self):
        """The phase prompt includes whiteboard summary."""
        agent = _mock_personality_agent("response")
        state = _make_state()

        await _invoke_agent(agent, state, "analyze this", "house")

        call_args = agent.base_agent.ainvoke.call_args[0][0]
        last_msg = call_args["messages"][-1]
        assert "Whiteboard Context" in last_msg.content
        assert "Phase Task" in last_msg.content
        assert "analyze this" in last_msg.content


# ══════════════════════════════════════════════════════════════════════════════
# Issue 9: No dual system prompts
# ══════════════════════════════════════════════════════════════════════════════


class TestNoDualSystemPrompts:
    def test_house_md_factory_no_prompt_param(self):
        """create_react_agent is called without prompt= in house_md factory."""
        from unittest.mock import patch

        from maos.house_md.graphs.factory import HouseMDGraphFactory

        config = MagicMock()
        config.graph.max_iterations = 5
        config.llms = {"frontier": MagicMock(), "mid-tier": MagicMock()}

        agent_registry = MagicMock()
        worker = MagicMock()
        worker.llm_name = "mid-tier"
        worker.system_prompt = "You are Chase"
        worker.tool_ids = []
        agent_registry.get_workers.return_value = [("chase", worker)]

        supervisor = MagicMock()
        supervisor.name = "house"
        supervisor.llm_name = "frontier"
        supervisor.system_prompt = "You are House"
        agent_registry.get_supervisor.return_value = supervisor

        llm_factory = MagicMock()
        llm_factory.create_chat_model.return_value = MagicMock()

        factory = HouseMDGraphFactory(
            config=config,
            agent_registry=agent_registry,
            llm_factory=llm_factory,
            tool_registry=MagicMock(),
        )

        with patch(
            "maos.house_md.graphs.factory.create_react_agent"
        ) as mock_create:
            mock_create.return_value = MagicMock()
            factory._create_agent_runnables()

            # Verify prompt= was NOT passed in any call
            for call in mock_create.call_args_list:
                kwargs = call.kwargs if call.kwargs else {}
                assert "prompt" not in kwargs, (
                    f"create_react_agent called with prompt= "
                    f"(would create dual system prompts): {kwargs}"
                )


# ══════════════════════════════════════════════════════════════════════════════
# Issue 10: SSE streaming handles AIMessage objects
# ══════════════════════════════════════════════════════════════════════════════


class TestExtractMessageContent:
    def test_ai_message_object(self):
        msg = AIMessage(content="Hello from agent")
        assert _extract_message_content(msg) == "Hello from agent"

    def test_human_message_object(self):
        msg = HumanMessage(content="User says hi")
        assert _extract_message_content(msg) == "User says hi"

    def test_dict_message(self):
        msg = {"content": "Hello", "role": "assistant"}
        assert _extract_message_content(msg) == "Hello"

    def test_empty_content_ai_message(self):
        msg = AIMessage(content="")
        assert _extract_message_content(msg) is None

    def test_empty_content_dict(self):
        msg = {"content": "", "role": "assistant"}
        assert _extract_message_content(msg) is None

    def test_none_returns_none(self):
        assert _extract_message_content(None) is None

    def test_plain_string_returns_none(self):
        assert _extract_message_content("just a string") is None


class TestStreamGraphEventsAIMessages:
    """Test that stream_graph_events handles AIMessage objects from house_md mode."""

    @pytest.mark.asyncio
    async def test_ai_message_streamed(self):
        """AIMessage objects should be streamed as chunks."""
        async def mock_events(*args, **kwargs):
            yield {
                "event": "on_chain_stream",
                "data": {
                    "chunk": {
                        "messages": [AIMessage(content="[House - Intake] Case analysis")]
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

        # Should have chunk + done
        assert len(chunks) == 2
        data = json.loads(chunks[0].split("data: ")[1].strip())
        assert "[House - Intake] Case analysis" in data["content"]

    @pytest.mark.asyncio
    async def test_mixed_message_types_streamed(self):
        """Both dict and AIMessage messages should be streamed."""
        async def mock_events(*args, **kwargs):
            yield {
                "event": "on_chain_stream",
                "data": {
                    "chunk": {
                        "messages": [
                            AIMessage(content="AI message"),
                            {"content": "Dict message", "role": "assistant"},
                        ]
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

        # 2 chunks + 1 done = 3
        assert len(chunks) == 3
        assert "AI message" in chunks[0]
        assert "Dict message" in chunks[1]


# ══════════════════════════════════════════════════════════════════════════════
# Issue 11: Non-streaming response builder handles AIMessage objects
# ══════════════════════════════════════════════════════════════════════════════


class TestBuildResponseMessages:
    def test_dict_messages(self):
        messages = [
            {"role": "assistant", "content": "Hello", "name": "agent1"},
            {"role": "user", "content": "Hi"},
        ]
        result = _build_response_messages(messages)
        assert len(result) == 2
        assert result[0].content == "Hello"
        assert result[0].name == "agent1"

    def test_ai_message_objects(self):
        messages = [
            AIMessage(content="[House - Intake] Analysis", name="house"),
            AIMessage(content="[Chase - Testing] Results", name="chase"),
        ]
        result = _build_response_messages(messages)
        assert len(result) == 2
        assert result[0].role == "assistant"
        assert result[0].content == "[House - Intake] Analysis"
        assert result[0].name == "house"
        assert result[1].content == "[Chase - Testing] Results"

    def test_human_message_objects(self):
        messages = [HumanMessage(content="User question")]
        result = _build_response_messages(messages)
        assert len(result) == 1
        assert result[0].role == "user"  # LangChain "human" mapped to API "user"

    def test_mixed_message_types(self):
        messages = [
            HumanMessage(content="Question"),
            AIMessage(content="Answer", name="house"),
            {"role": "assistant", "content": "Dict answer"},
        ]
        result = _build_response_messages(messages)
        assert len(result) == 3

    def test_empty_messages(self):
        assert _build_response_messages([]) == []

    def test_unknown_type_skipped(self):
        messages = ["just a string", 42, None]
        result = _build_response_messages(messages)
        assert len(result) == 0
