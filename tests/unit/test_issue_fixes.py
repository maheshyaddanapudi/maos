"""Tests for Issues 7-26 fixes.

Issue 7:  Whiteboard hypotheses populated from agent responses
Issue 8:  Trimmed message history in _invoke_agent
Issue 9:  No dual system prompts in House MD factory
Issue 10: SSE streaming handles AIMessage objects
Issue 11: Non-streaming response builder handles AIMessage objects
Issue 12: Smart hypothesis matching (word-overlap similarity)
Issue 13: Broader hypothesis extraction patterns
Issue 14: Configurable max_context_messages
Issue 15: Environmental findings extracted to whiteboard
Issue 16: PersonalityWrapper always prepends system prompt
Issue 17: Roster/personality name mismatch — always use personality names
Issue 18: Testing node extracts hypotheses to whiteboard
Issue 19: Wilson consult node extracts hypotheses to whiteboard
Issue 20: Provocation node extracts hypotheses to whiteboard
Issue 22: Re-entry to differential/critique after testing cycles
Issue 23: Critique round sets team_context before invocation
Issue 24: Confidence arithmetic supports convergence (+0.15 per evidence)
Issue 25: Whiteboard iteration count stays in sync
Issue 26: House MD mode preserves multi-turn messages
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
    _hypothesis_similarity,
    _tokenize,
    extract_environmental_findings,
    extract_hypotheses,
    run_critique_round,
)
from maos.house_md.graphs.differential_diagnosis import (
    create_initial_diagnostic_state,
)
from maos.house_md.graphs.factory import (
    _DEFAULT_MAX_CONTEXT_MESSAGES,
    _invoke_agent,
    _update_whiteboard_hypotheses,
)
from maos.house_md.graphs.states import DiagnosticPhase
from maos.house_md.memory.whiteboard import Whiteboard
from maos.house_md.personalities.base import (
    PersonalityConfig,
    PersonalityWrapper,
    TeamContext,
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
        # 1 system + 1 first msg + _DEFAULT_MAX_CONTEXT_MESSAGES recent + 1 context = 13
        assert len(msgs) == 1 + 1 + _DEFAULT_MAX_CONTEXT_MESSAGES + 1
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


# ══════════════════════════════════════════════════════════════════════════════
# Issue 12: Smart hypothesis matching (word-overlap similarity)
# ══════════════════════════════════════════════════════════════════════════════


class TestTokenize:
    def test_basic_tokenization(self):
        result = _tokenize("Connection Pool Exhaustion")
        assert "connection" in result
        assert "pool" in result
        assert "exhaustion" in result

    def test_stopwords_removed(self):
        result = _tokenize("the connection is exhausted due to a leak")
        assert "the" not in result
        assert "is" not in result
        assert "due" not in result
        assert "a" not in result
        assert "connection" in result
        assert "exhausted" in result
        assert "leak" in result

    def test_case_insensitive(self):
        result = _tokenize("Database CONNECTION Pool")
        assert "database" in result
        assert "connection" in result
        assert "pool" in result

    def test_empty_string(self):
        result = _tokenize("")
        assert result == set()

    def test_only_stopwords(self):
        result = _tokenize("the is a an")
        assert result == set()


class TestHypothesisSimilarity:
    def test_identical_strings(self):
        score = _hypothesis_similarity(
            "connection pool exhaustion", "connection pool exhaustion"
        )
        assert score == 1.0

    def test_completely_different(self):
        score = _hypothesis_similarity("memory leak", "network timeout")
        assert score == 0.0

    def test_partial_overlap(self):
        score = _hypothesis_similarity(
            "connection pool exhaustion due to ORM upgrade",
            "connection pool exhaustion",
        )
        # All words in shorter set appear in longer → 1.0
        assert score >= 0.8

    def test_subset_match(self):
        score = _hypothesis_similarity(
            "pool exhaustion", "connection pool exhaustion"
        )
        assert score >= 0.8

    def test_empty_strings(self):
        assert _hypothesis_similarity("", "") == 0.0
        assert _hypothesis_similarity("connection pool", "") == 0.0

    def test_below_threshold(self):
        """Unrelated hypotheses should score below threshold."""
        score = _hypothesis_similarity(
            "database connection pool", "race condition in thread scheduler"
        )
        assert score < 0.5

    def test_distinguishes_pool_types(self):
        """'thread pool' and 'connection pool' share 'pool' but differ."""
        score = _hypothesis_similarity("thread pool starvation", "connection pool exhaustion")
        # Only "pool" overlaps out of 2-3 meaningful words → low score
        assert score < 0.5


class TestFindExistingHypothesisSimilarity:
    """Test _find_existing_hypothesis with the word-overlap similarity approach."""

    def test_similar_wording_matches(self):
        wb = Whiteboard()
        wb.add_hypothesis("database connection pool exhaustion", "foreman")
        result = _find_existing_hypothesis(wb, "connection pool exhaustion")
        assert result is not None

    def test_different_hypothesis_no_match(self):
        wb = Whiteboard()
        wb.add_hypothesis("thread pool starvation", "foreman")
        result = _find_existing_hypothesis(wb, "connection pool exhaustion")
        assert result is None

    def test_best_match_chosen(self):
        wb = Whiteboard()
        wb.add_hypothesis("memory leak in handler", "foreman")
        wb.add_hypothesis("connection pool exhaustion", "chase")
        result = _find_existing_hypothesis(wb, "database connection pool exhaustion")
        assert result is not None
        assert "connection pool" in result.hypothesis

    def test_empty_whiteboard(self):
        wb = Whiteboard()
        result = _find_existing_hypothesis(wb, "any hypothesis")
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# Issue 13: Broader hypothesis extraction patterns
# ══════════════════════════════════════════════════════════════════════════════


class TestBroaderExtractionPatterns:
    def test_diagnosis_prefix(self):
        content = "Diagnosis: ORM regression causing connection leaks"
        results = extract_hypotheses(content, "house")
        assert len(results) >= 1
        assert any("orm" in h["hypothesis"].lower() for h in results)

    def test_markdown_bold_hypothesis(self):
        content = "**Hypothesis**: Thread pool saturation under load"
        results = extract_hypotheses(content, "chase")
        assert len(results) >= 1

    def test_bulleted_hypothesis(self):
        content = "- HYPOTHESIS: Cache invalidation race condition"
        results = extract_hypotheses(content, "foreman")
        assert len(results) >= 1
        assert "cache invalidation" in results[0]["hypothesis"].lower()

    def test_numbered_hypothesis(self):
        content = "1. Hypothesis: Deadlock in worker threads"
        results = extract_hypotheses(content, "thirteen")
        assert len(results) >= 1

    def test_caused_by_pattern(self):
        content = "This is caused by a misconfigured load balancer timeout."
        results = extract_hypotheses(content, "chase")
        assert len(results) >= 1

    def test_triggered_by_pattern(self):
        content = "This was triggered by a race condition in the scheduler."
        results = extract_hypotheses(content, "foreman")
        assert len(results) >= 1

    def test_evidence_suggests_pattern(self):
        content = "Evidence suggests a memory leak in the request handler."
        results = extract_hypotheses(content, "thirteen")
        assert len(results) >= 1

    def test_recommend_investigating_pattern(self):
        content = "I recommend investigating the connection timeout settings."
        results = extract_hypotheses(content, "wilson")
        assert len(results) >= 1

    def test_dedup_within_heuristic_extraction(self):
        """Multiple causal patterns matching similar text shouldn't duplicate."""
        content = (
            "I think the root cause is a thread pool exhaustion. "
            "I believe the issue is thread pool exhaustion under load."
        )
        results = extract_hypotheses(content, "chase")
        # Should deduplicate similar hypotheses
        assert len(results) <= 2


# ══════════════════════════════════════════════════════════════════════════════
# Issue 14: Configurable max_context_messages
# ══════════════════════════════════════════════════════════════════════════════


class TestConfigurableContextMessages:
    def test_default_value(self):
        assert _DEFAULT_MAX_CONTEXT_MESSAGES == 10

    @pytest.mark.asyncio
    async def test_custom_max_context(self):
        """Custom max_context_messages limits the trimmed history."""
        agent = _mock_personality_agent("response")
        many_messages = [HumanMessage(content="original")] + [
            AIMessage(content=f"msg {i}") for i in range(20)
        ]
        state = _make_state(messages=many_messages)

        # Use a custom limit of 5
        await _invoke_agent(
            agent, state, "test prompt", "house", max_context_messages=5
        )

        call_args = agent.base_agent.ainvoke.call_args[0][0]
        msgs = call_args["messages"]
        # 1 system (personality) + 1 first msg + 5 recent + 1 context = 8
        assert len(msgs) == 1 + 1 + 5 + 1

    @pytest.mark.asyncio
    async def test_large_limit_no_trimming(self):
        """When limit exceeds message count, no trimming occurs."""
        agent = _mock_personality_agent("response")
        state = _make_state(messages=[
            HumanMessage(content="original"),
            AIMessage(content="reply"),
        ])

        await _invoke_agent(
            agent, state, "test prompt", "house", max_context_messages=100
        )

        call_args = agent.base_agent.ainvoke.call_args[0][0]
        msgs = call_args["messages"]
        # 1 system + 2 original + 1 context = 4
        assert len(msgs) == 4

    def test_config_model_field_exists(self):
        """GraphConfig has a max_context_messages field."""
        from maos.config.models import GraphConfig

        gc = GraphConfig(mode="house_md")
        assert hasattr(gc, "max_context_messages")
        assert gc.max_context_messages == 10  # default

    def test_config_model_custom_value(self):
        from maos.config.models import GraphConfig

        gc = GraphConfig(mode="house_md", max_context_messages=25)
        assert gc.max_context_messages == 25


# ══════════════════════════════════════════════════════════════════════════════
# Issue 15: Environmental findings extracted to whiteboard
# ══════════════════════════════════════════════════════════════════════════════


class TestEnvironmentalFindingsExtraction:
    def test_structured_finding_marker(self):
        content = "FINDING: Recent deployment changed connection pool size from 10 to 5"
        results = extract_environmental_findings(content)
        assert len(results) == 1
        assert "connection pool size" in results[0].lower()

    def test_multiple_findings(self):
        content = (
            "FINDING: Git history shows config change last week\n"
            "FINDING: Deployment logs indicate version rollback\n"
        )
        results = extract_environmental_findings(content)
        assert len(results) == 2

    def test_finding_case_variants(self):
        content = "Finding: The environment was recently updated"
        results = extract_environmental_findings(content)
        assert len(results) >= 1

    def test_environmental_prefix(self):
        content = "Environmental: Server memory reduced to 2GB last month"
        results = extract_environmental_findings(content)
        assert len(results) >= 1

    def test_heuristic_discovered(self):
        content = "I discovered that the deployment was rolled back yesterday."
        results = extract_environmental_findings(content)
        assert len(results) >= 1

    def test_heuristic_git_history(self):
        content = "Git history shows a breaking change was merged two days ago."
        results = extract_environmental_findings(content)
        assert len(results) >= 1

    def test_heuristic_config_reveals(self):
        content = "Configuration reveals that SSL certificates expired last week."
        results = extract_environmental_findings(content)
        assert len(results) >= 1

    def test_no_findings_in_generic_text(self):
        content = "Everything looks normal. No issues detected."
        results = extract_environmental_findings(content)
        assert len(results) == 0

    def test_short_finding_ignored(self):
        content = "FINDING: bug"
        results = extract_environmental_findings(content)
        assert len(results) == 0


# ══════════════════════════════════════════════════════════════════════════════
# Issue 16: PersonalityWrapper always prepends system prompt
# ══════════════════════════════════════════════════════════════════════════════


class TestPersonalityWrapperAlwaysPrepends:
    def _make_wrapper(self) -> PersonalityWrapper:
        base = AsyncMock()
        personality = PersonalityConfig(
            name="TestAgent",
            role_description="test role",
            system_prompt_additions="be thorough",
        )
        return PersonalityWrapper(base_agent=base, personality=personality)

    def test_no_messages_creates_system(self):
        wrapper = self._make_wrapper()
        state: dict[str, Any] = {}
        result = wrapper.enhance_state(state)
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], SystemMessage)
        assert "TestAgent" in result["messages"][0].content

    def test_prepends_before_human_messages(self):
        wrapper = self._make_wrapper()
        state: dict[str, Any] = {
            "messages": [
                HumanMessage(content="user question"),
                AIMessage(content="reply"),
            ]
        }
        result = wrapper.enhance_state(state)
        assert isinstance(result["messages"][0], SystemMessage)
        assert "TestAgent" in result["messages"][0].content
        # Original messages preserved after system
        assert result["messages"][1].content == "user question"
        assert result["messages"][2].content == "reply"

    def test_merges_existing_system_message(self):
        wrapper = self._make_wrapper()
        state: dict[str, Any] = {
            "messages": [
                SystemMessage(content="existing system prompt"),
                HumanMessage(content="user question"),
            ]
        }
        result = wrapper.enhance_state(state)
        # Should be merged: personality + existing content, then user msg
        assert len(result["messages"]) == 2  # 1 merged system + 1 human
        assert isinstance(result["messages"][0], SystemMessage)
        assert "TestAgent" in result["messages"][0].content
        assert "existing system prompt" in result["messages"][0].content
        assert isinstance(result["messages"][1], HumanMessage)

    def test_multiple_system_messages_merged(self):
        wrapper = self._make_wrapper()
        state: dict[str, Any] = {
            "messages": [
                SystemMessage(content="system A"),
                HumanMessage(content="user msg"),
                SystemMessage(content="system B"),
                AIMessage(content="reply"),
            ]
        }
        result = wrapper.enhance_state(state)
        # All system content merged into one personality msg at front
        assert isinstance(result["messages"][0], SystemMessage)
        assert "system A" in result["messages"][0].content
        assert "system B" in result["messages"][0].content
        # Non-system messages preserved in order
        assert result["messages"][1].content == "user msg"
        assert result["messages"][2].content == "reply"
        assert len(result["messages"]) == 3

    def test_dict_system_message_handled(self):
        wrapper = self._make_wrapper()
        state: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": "dict system prompt"},
                HumanMessage(content="user question"),
            ]
        }
        result = wrapper.enhance_state(state)
        assert isinstance(result["messages"][0], SystemMessage)
        assert "dict system prompt" in result["messages"][0].content
        assert "TestAgent" in result["messages"][0].content

    def test_personality_always_first(self):
        """Even with no existing system messages, personality is first."""
        wrapper = self._make_wrapper()
        state: dict[str, Any] = {
            "messages": [
                AIMessage(content="some AI msg"),
                HumanMessage(content="user msg"),
            ]
        }
        result = wrapper.enhance_state(state)
        assert isinstance(result["messages"][0], SystemMessage)
        assert "house_md_personality" in result["messages"][0].content
        assert len(result["messages"]) == 3  # system + 2 original

    def test_idempotent_double_enhance(self):
        """Enhancing twice shouldn't stack system messages."""
        wrapper = self._make_wrapper()
        state: dict[str, Any] = {
            "messages": [HumanMessage(content="question")],
        }
        result1 = wrapper.enhance_state(state)
        result2 = wrapper.enhance_state(result1)
        # Should still have exactly 1 system message + 1 human
        system_msgs = [
            m for m in result2["messages"] if isinstance(m, SystemMessage)
        ]
        assert len(system_msgs) == 1
        assert isinstance(result2["messages"][0], SystemMessage)


# ══════════════════════════════════════════════════════════════════════════════
# Issue 17: Roster uses personality names, not config names
# ══════════════════════════════════════════════════════════════════════════════


class TestRosterPersonalityNames:
    def test_default_active_team(self):
        """Default active_team uses House MD personality names."""
        state = create_initial_diagnostic_state(user_message="test bug")
        assert "house" in state["active_team"]
        assert "foreman" in state["active_team"]
        assert "cameron" in state["active_team"]
        assert "chase" in state["active_team"]

    def test_none_roster_gets_defaults(self):
        """Passing None for active_team falls back to defaults."""
        state = create_initial_diagnostic_state(
            user_message="test", active_team=None
        )
        assert state["active_team"] == ["house", "foreman", "cameron", "chase"]


# ══════════════════════════════════════════════════════════════════════════════
# Issues 18-20: Hypothesis extraction from testing/wilson/provocation nodes
# ══════════════════════════════════════════════════════════════════════════════


class TestUpdateWhiteboardHypotheses:
    """Test the _update_whiteboard_hypotheses helper used by all nodes."""

    def test_new_hypothesis_added(self):
        wb = Whiteboard()
        content = "HYPOTHESIS: Database connection pool exhaustion"
        _update_whiteboard_hypotheses(wb, content, "chase")
        active = wb.get_active_hypotheses()
        assert len(active) == 1
        assert "connection pool" in active[0].hypothesis.lower()
        assert active[0].proposer == "chase"

    def test_existing_hypothesis_gets_evidence(self):
        wb = Whiteboard()
        wb.add_hypothesis("connection pool exhaustion", "foreman")
        content = "HYPOTHESIS: Connection pool exhaustion"
        _update_whiteboard_hypotheses(wb, content, "chase")
        active = wb.get_active_hypotheses()
        assert len(active) == 1
        # Confidence boosted by supporting evidence (+0.15)
        assert active[0].confidence > 0.5

    def test_no_hypotheses_in_generic_text(self):
        wb = Whiteboard()
        content = "I agree with the analysis. Let's proceed."
        _update_whiteboard_hypotheses(wb, content, "house")
        assert len(wb.get_active_hypotheses()) == 0

    def test_multiple_hypotheses_extracted(self):
        wb = Whiteboard()
        content = (
            "HYPOTHESIS: Thread pool starvation\n"
            "HYPOTHESIS: ORM query regression\n"
        )
        _update_whiteboard_hypotheses(wb, content, "house")
        active = wb.get_active_hypotheses()
        assert len(active) == 2


# ══════════════════════════════════════════════════════════════════════════════
# Issue 22: Re-entry to differential/critique after testing cycles
# ══════════════════════════════════════════════════════════════════════════════


class TestRouteReentrytoDifferential:
    """Test that route_after_provocation returns 'differential' on even iterations."""

    def _make_routing_state(
        self, iteration: int, confidence: float = 0.5, has_env: bool = False,
    ) -> dict[str, Any]:
        wb = Whiteboard()
        wb.add_hypothesis("test hypothesis", "foreman", confidence=confidence)
        if has_env:
            wb.add_environmental_finding("some finding")
        return {
            "iteration": iteration,
            "whiteboard": wb.to_dict(),
            "messages": [],
            "symptoms": [],
            "hypotheses": [],
            "evidence": {},
            "current_phase": "provocation",
            "agent_beliefs": {},
            "final_diagnosis": None,
            "confidence": 0.0,
            "active_team": ["house", "foreman", "chase"],
        }

    def test_iteration_2_even_goes_to_differential(self):
        """Even iterations > 1 should route to differential for critique."""
        # We need to simulate what route_after_provocation does
        from maos.house_md.memory.whiteboard import Whiteboard

        state = self._make_routing_state(iteration=2, has_env=True)
        wb = Whiteboard.from_dict(state["whiteboard"])
        iteration = state["iteration"]
        top = wb.get_top_hypothesis()

        # Not at max iterations, not high confidence, has active hyps,
        # has env findings, iteration is even and > 1
        assert iteration > 1
        assert iteration % 2 == 0
        assert top is not None
        assert top.confidence <= 0.85

    def test_iteration_3_odd_goes_to_testing(self):
        """Odd iterations should route to testing."""
        state = self._make_routing_state(iteration=3, has_env=True)
        # iteration 3 is odd, so should go to testing
        assert state["iteration"] % 2 != 0

    def test_high_confidence_goes_to_resolution(self):
        """High confidence should always go to resolution."""
        state = self._make_routing_state(iteration=2, confidence=0.9)
        wb = Whiteboard.from_dict(state["whiteboard"])
        top = wb.get_top_hypothesis()
        assert top.confidence > 0.85


# ══════════════════════════════════════════════════════════════════════════════
# Issue 23: Critique round sets team_context
# ══════════════════════════════════════════════════════════════════════════════


class TestCritiqueRoundTeamContext:
    @pytest.mark.asyncio
    async def test_team_context_set_on_personality_wrapper(self):
        """Critique round should set team_context before calling agents."""
        state = _make_state(active_team=["chase"])

        wrapper = _mock_personality_agent(
            "HYPOTHESIS: Connection pool exhaustion"
        )
        # Verify team_context is None initially
        assert wrapper.team_context is None

        # Track whether team_context was set before invoke
        original_ainvoke = wrapper.base_agent.ainvoke
        team_context_during_call = []

        async def tracking_ainvoke(state, config=None):
            team_context_during_call.append(wrapper.team_context)
            return await original_ainvoke(state, config)

        wrapper.base_agent.ainvoke = tracking_ainvoke

        await run_critique_round(state, {"chase": wrapper})

        # team_context should have been set before the call
        assert len(team_context_during_call) == 1
        ctx = team_context_during_call[0]
        assert isinstance(ctx, TeamContext)
        assert "chase" in ctx.active_agents


# ══════════════════════════════════════════════════════════════════════════════
# Issue 24: Confidence arithmetic (+0.15 per evidence)
# ══════════════════════════════════════════════════════════════════════════════


class TestConfidenceArithmetic:
    def test_supporting_evidence_adds_015(self):
        from maos.house_md.memory.whiteboard import WhiteboardEntry

        entry = WhiteboardEntry(hypothesis="test", proposer="chase")
        assert entry.confidence == 0.5
        entry.add_supporting_evidence("evidence 1")
        assert entry.confidence == 0.65
        entry.add_supporting_evidence("evidence 2")
        assert entry.confidence == 0.8

    def test_counter_evidence_subtracts_015(self):
        from maos.house_md.memory.whiteboard import WhiteboardEntry

        entry = WhiteboardEntry(hypothesis="test", proposer="chase")
        entry.add_counter_evidence("counter 1")
        assert entry.confidence == 0.35

    def test_three_supporters_reach_threshold(self):
        """With proposer at 0.5, 3 supporters should reach 0.95 > 0.85."""
        from maos.house_md.memory.whiteboard import WhiteboardEntry

        entry = WhiteboardEntry(hypothesis="test", proposer="chase")
        entry.add_supporting_evidence("foreman agrees")
        entry.add_supporting_evidence("cameron agrees")
        entry.add_supporting_evidence("thirteen agrees")
        assert entry.confidence == pytest.approx(0.95)
        assert entry.confidence > 0.85  # Exceeds resolution threshold


# ══════════════════════════════════════════════════════════════════════════════
# Issue 25: Whiteboard iteration count stays in sync
# ══════════════════════════════════════════════════════════════════════════════


class TestWhiteboardIterationSync:
    @pytest.mark.asyncio
    async def test_critique_round_syncs_iteration(self):
        """Critique round should not drift the whiteboard iteration count."""
        state = _make_state(active_team=["chase"], iteration=3)

        async def mock_agent(s):
            return {
                "messages": [AIMessage(content="HYPOTHESIS: Test hypothesis")]
            }

        result = await run_critique_round(state, {"chase": mock_agent})

        wb = Whiteboard.from_dict(result["whiteboard"])
        # Should be synced with the state iteration, not drifted
        assert wb.iteration_count == 3

    def test_advance_phase_with_iteration_syncs(self):
        wb = Whiteboard()
        wb.advance_phase("testing", iteration=5)
        assert wb.iteration_count == 5

    def test_advance_phase_without_iteration_increments(self):
        wb = Whiteboard()
        wb.advance_phase("testing")
        assert wb.iteration_count == 1
        wb.advance_phase("provocation")
        assert wb.iteration_count == 2


# ══════════════════════════════════════════════════════════════════════════════
# Issue 26: House MD mode preserves multi-turn messages
# ══════════════════════════════════════════════════════════════════════════════


class TestMultiTurnMessages:
    def test_single_message_backwards_compatible(self):
        state = create_initial_diagnostic_state(user_message="single bug report")
        assert len(state["messages"]) == 1
        assert state["messages"][0].content == "single bug report"
        assert state["symptoms"] == ["single bug report"]

    def test_multiple_user_messages_preserved(self):
        state = create_initial_diagnostic_state(
            user_messages=[
                "Checkout failing with 500 errors",
                "Also seeing timeouts on the payment page",
                "Error rate is about 15%",
            ]
        )
        assert len(state["messages"]) == 3
        assert state["messages"][0].content == "Checkout failing with 500 errors"
        assert state["messages"][2].content == "Error rate is about 15%"
        assert len(state["symptoms"]) == 3

    def test_user_messages_takes_precedence(self):
        """user_messages parameter takes precedence over user_message."""
        state = create_initial_diagnostic_state(
            user_message="old single",
            user_messages=["msg1", "msg2"],
        )
        assert len(state["messages"]) == 2
        assert state["messages"][0].content == "msg1"

    def test_empty_messages_handled(self):
        state = create_initial_diagnostic_state()
        assert len(state["messages"]) == 0
        assert len(state["symptoms"]) == 0

    def test_whiteboard_records_all_symptoms(self):
        state = create_initial_diagnostic_state(
            user_messages=["symptom A", "symptom B"]
        )
        wb = Whiteboard.from_dict(state["whiteboard"])
        assert "symptom A" in wb.symptoms
        assert "symptom B" in wb.symptoms
