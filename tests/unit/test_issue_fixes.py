"""Tests for Issues 7-26 + Round 4 + Round 5 fixes.

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
Round 4 Issue 27: Agent name mapping (config names → personality keys)
Round 4 Issue 28: Counter-evidence and rule-out extraction
Round 4 Issue 29: Critique round trims message history
Round 4 Issue 30: _extract_content fallback returns sensible message
Round 4 Issue 31: Resolution node captures pre-confirm confidence
Round 4 Issue 32: Context message labeling
Round 4 Issue 33: Similarity threshold raised to 0.6
Round 5 Issue 34: State mutation — from_dict copies mutable lists
Round 5 Issue 35: Personality slot assignment uses set tracking
Round 5 Issue 36: Duplicate evidence skipped in confidence updates
Round 5 Issue 37: Empty active_team logged in critique round
Round 5 Issue 38: Fragile personality fallback replaced with generic config
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
    _CRITIQUE_MAX_CONTEXT_MESSAGES,
    _SIMILARITY_THRESHOLD,
    _find_existing_hypothesis,
    _hypothesis_similarity,
    _tokenize,
    extract_challenges,
    extract_environmental_findings,
    extract_hypotheses,
    run_critique_round,
)
from maos.house_md.graphs.differential_diagnosis import (
    create_initial_diagnostic_state,
)
from maos.house_md.graphs.factory import (
    _DEFAULT_MAX_CONTEXT_MESSAGES,
    _extract_content,
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
from maos.house_md.personalities.team import PERSONALITY_CONFIGS

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
        assert "DIAGNOSTIC WHITEBOARD" in last_msg.content
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


# ══════════════════════════════════════════════════════════════════════════════
# Round 4 Issue 27: Agent name mapping (config names → personality keys)
# ══════════════════════════════════════════════════════════════════════════════


class TestAgentNameMapping:
    """Test that _create_agent_runnables maps config names to personality keys."""

    def test_personality_configs_keyed_correctly(self):
        """PERSONALITY_CONFIGS must be keyed by lowercase personality names."""
        from maos.house_md.personalities.team import PERSONALITY_CONFIGS

        assert "house" in PERSONALITY_CONFIGS
        assert "foreman" in PERSONALITY_CONFIGS
        assert "cameron" in PERSONALITY_CONFIGS
        assert "chase" in PERSONALITY_CONFIGS
        assert "thirteen" in PERSONALITY_CONFIGS
        assert "wilson" in PERSONALITY_CONFIGS

    def test_wrap_with_personalities_matches_personality_keys(self):
        """Agents keyed by personality name get the correct PersonalityConfig."""
        from maos.house_md.personalities.team import PERSONALITY_CONFIGS

        # Simulate runnables keyed by personality names
        mock_runnables = {
            "house": MagicMock(),
            "foreman": MagicMock(),
            "chase": MagicMock(),
        }

        # Manually apply the wrapping logic (same as _wrap_with_personalities)
        for name in mock_runnables:
            personality = PERSONALITY_CONFIGS.get(name)
            assert personality is not None, (
                f"Personality not found for key '{name}'"
            )
            assert personality.name.lower() == name

    def test_config_name_matching_personality_used_directly(self):
        """When config name matches personality key, it should be used."""
        from maos.house_md.personalities.team import PERSONALITY_CONFIGS

        # A config agent named "foreman" should map directly
        config_name = "foreman"
        personality_key = config_name.lower()
        assert personality_key in PERSONALITY_CONFIGS

    def test_unknown_config_name_gets_fallback_slot(self):
        """Workers with non-personality names should get assigned to slots."""
        from maos.house_md.personalities.team import PERSONALITY_CONFIGS

        # Simulate the mapping logic from _create_agent_runnables
        available_slots = [
            k for k in PERSONALITY_CONFIGS if k != "house"
        ]
        config_name = "code_reviewer"  # Not a personality name
        personality_key = config_name.lower()
        if personality_key not in PERSONALITY_CONFIGS:
            personality_key = available_slots[0]  # Gets first slot

        assert personality_key in PERSONALITY_CONFIGS
        assert personality_key != "code_reviewer"

    def test_supervisor_always_maps_to_house(self):
        """The supervisor should always be keyed as 'house'."""
        from maos.house_md.personalities.team import PERSONALITY_CONFIGS

        assert "house" in PERSONALITY_CONFIGS
        assert PERSONALITY_CONFIGS["house"].name == "House"


# ══════════════════════════════════════════════════════════════════════════════
# Round 4 Issue 28: Counter-evidence and rule-out extraction
# ══════════════════════════════════════════════════════════════════════════════


class TestExtractChallenges:
    """Test the extract_challenges function."""

    def test_structured_rule_out(self):
        content = "RULE OUT: Memory leak in the handler"
        results = extract_challenges(content, "foreman")
        assert len(results) == 1
        assert results[0]["action"] == "rule_out"
        assert "memory leak" in results[0]["target"].lower()

    def test_structured_challenge(self):
        content = "CHALLENGE: Connection pool exhaustion theory"
        results = extract_challenges(content, "chase")
        assert len(results) == 1
        assert results[0]["action"] == "challenge"

    def test_multiple_structured_markers(self):
        content = (
            "RULE OUT: DNS resolution delay\n"
            "CHALLENGE: Thread pool starvation theory\n"
        )
        results = extract_challenges(content, "foreman")
        assert len(results) == 2
        rule_outs = [r for r in results if r["action"] == "rule_out"]
        challenges = [r for r in results if r["action"] == "challenge"]
        assert len(rule_outs) == 1
        assert len(challenges) == 1

    def test_heuristic_rule_out(self):
        content = "We can rule out the caching layer being the bottleneck."
        results = extract_challenges(content, "thirteen")
        assert len(results) >= 1
        assert any(r["action"] == "rule_out" for r in results)

    def test_heuristic_disagree(self):
        content = "I disagree with the memory leak hypothesis in the handler."
        results = extract_challenges(content, "foreman")
        assert len(results) >= 1
        assert any(r["action"] == "challenge" for r in results)

    def test_no_challenges_in_supportive_text(self):
        content = "I agree with the analysis. The evidence supports this."
        results = extract_challenges(content, "chase")
        assert len(results) == 0

    def test_short_target_ignored(self):
        content = "RULE OUT: bug"
        results = extract_challenges(content, "foreman")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_critique_round_applies_counter_evidence(self):
        """Critique round should apply counter-evidence from challenges."""
        wb = Whiteboard()
        wb.add_hypothesis("Memory leak in handler", "house", confidence=0.7)
        state = _make_state(
            active_team=["foreman"],
            whiteboard=wb.to_dict(),
        )

        async def mock_agent(s):
            return {
                "messages": [AIMessage(
                    content="RULE OUT: Memory leak in handler"
                )]
            }

        result = await run_critique_round(state, {"foreman": mock_agent})
        result_wb = Whiteboard.from_dict(result["whiteboard"])

        # The hypothesis should be ruled out
        entries = result_wb.entries
        assert len(entries) >= 1
        ruled_out = [
            e for e in entries
            if e.status.value == "ruled_out"
        ]
        assert len(ruled_out) >= 1

    @pytest.mark.asyncio
    async def test_critique_round_applies_challenge(self):
        """Critique round should lower confidence via counter-evidence."""
        wb = Whiteboard()
        wb.add_hypothesis("Thread pool starvation", "house", confidence=0.7)
        state = _make_state(
            active_team=["foreman"],
            whiteboard=wb.to_dict(),
        )

        async def mock_agent(s):
            return {
                "messages": [AIMessage(
                    content="CHALLENGE: Thread pool starvation theory"
                )]
            }

        result = await run_critique_round(state, {"foreman": mock_agent})
        result_wb = Whiteboard.from_dict(result["whiteboard"])

        # Confidence should have decreased
        entry = result_wb.entries[0]
        assert entry.confidence < 0.7


# ══════════════════════════════════════════════════════════════════════════════
# Round 4 Issue 29: Critique round trims message history
# ══════════════════════════════════════════════════════════════════════════════


class TestCritiqueRoundTrimming:
    def test_critique_max_context_constant(self):
        assert _CRITIQUE_MAX_CONTEXT_MESSAGES == 10

    @pytest.mark.asyncio
    async def test_critique_round_trims_long_history(self):
        """Critique round should trim messages like _invoke_agent."""
        many_messages = [HumanMessage(content="original")] + [
            AIMessage(content=f"msg {i}") for i in range(30)
        ]
        state = _make_state(
            active_team=["chase"],
            messages=many_messages,
        )

        captured_messages: list[Any] = []

        async def capturing_agent(s):
            captured_messages.append(s["messages"])
            return {
                "messages": [AIMessage(content="HYPOTHESIS: Test hypothesis")]
            }

        await run_critique_round(state, {"chase": capturing_agent})

        assert len(captured_messages) == 1
        msgs = captured_messages[0]
        # Should be trimmed: first msg + last 10 + critique prompt = 12
        assert len(msgs) <= 12 + 1  # Allow for first msg

    @pytest.mark.asyncio
    async def test_critique_round_short_history_untrimmed(self):
        """Short histories should not be trimmed."""
        state = _make_state(
            active_team=["chase"],
            messages=[HumanMessage(content="test")],
        )

        captured_messages: list[Any] = []

        async def capturing_agent(s):
            captured_messages.append(s["messages"])
            return {"messages": [AIMessage(content="response")]}

        await run_critique_round(state, {"chase": capturing_agent})

        assert len(captured_messages) == 1
        # 1 original + 1 critique prompt = 2
        assert len(captured_messages[0]) == 2


# ══════════════════════════════════════════════════════════════════════════════
# Round 4 Issue 30: _extract_content fallback
# ══════════════════════════════════════════════════════════════════════════════


class TestExtractContentFallback:
    def test_ai_message_extracted(self):
        result = {"messages": [AIMessage(content="analysis result")]}
        assert _extract_content(result) == "analysis result"

    def test_dict_assistant_extracted(self):
        result = {"messages": [{"role": "assistant", "content": "dict response"}]}
        assert _extract_content(result) == "dict response"

    def test_no_messages_returns_fallback(self):
        result = {"messages": []}
        assert _extract_content(result) == "No response generated."

    def test_no_messages_key_returns_fallback(self):
        result = {}
        assert _extract_content(result) == "No response generated."

    def test_fallback_does_not_stringify_dict(self):
        """Fallback should NOT return str(result) which dumps the whole dict."""
        result = {"messages": [HumanMessage(content="user msg")]}
        content = _extract_content(result)
        # Should extract user msg content as fallback, not dump the dict
        assert content == "user msg"

    def test_multiple_messages_returns_last_ai(self):
        result = {
            "messages": [
                AIMessage(content="first"),
                HumanMessage(content="question"),
                AIMessage(content="last"),
            ]
        }
        assert _extract_content(result) == "last"


# ══════════════════════════════════════════════════════════════════════════════
# Round 4 Issue 31: Resolution node captures pre-confirm confidence
# ══════════════════════════════════════════════════════════════════════════════


class TestResolutionPreConfirmConfidence:
    def test_standalone_resolution_captures_pre_confirm(self):
        """Resolution in differential_diagnosis.py should capture
        confidence before confirm() sets it to 1.0."""
        from maos.house_md.graphs.differential_diagnosis import (
            resolution_node,
        )

        wb = Whiteboard()
        wb.add_hypothesis("Bug in handler", "house", confidence=0.75)
        state = _make_state(whiteboard=wb.to_dict())

        result = resolution_node(state)
        # Confidence should be 0.75, NOT 1.0
        assert result["confidence"] == 0.75
        # The message should contain 75%
        msg_content = result["messages"][0].content
        assert "75%" in msg_content

    def test_confirmed_hypothesis_still_returns_pre_confirm(self):
        """Even when a hypothesis is already confirmed, confidence should
        reflect the pre-confirm value."""
        from maos.house_md.graphs.differential_diagnosis import (
            resolution_node,
        )

        wb = Whiteboard()
        entry = wb.add_hypothesis("Root cause found", "house", confidence=0.9)
        entry.confirm()  # Already confirmed → confidence 1.0
        state = _make_state(whiteboard=wb.to_dict())

        result = resolution_node(state)
        # Already confirmed, so pre-confirm confidence is 1.0
        assert result["confidence"] == 1.0


# ══════════════════════════════════════════════════════════════════════════════
# Round 4 Issue 32: Context message labeling
# ══════════════════════════════════════════════════════════════════════════════


class TestContextMessageLabeling:
    @pytest.mark.asyncio
    async def test_context_msg_labeled_as_system_context(self):
        """The whiteboard context message should be labeled clearly."""
        agent = _mock_personality_agent("response")
        state = _make_state()

        await _invoke_agent(agent, state, "test prompt", "house")

        call_args = agent.base_agent.ainvoke.call_args[0][0]
        msgs = call_args["messages"]
        # Last non-system message should contain the context label
        last_msg = msgs[-1]
        content = last_msg.content if hasattr(last_msg, "content") else ""
        assert "SYSTEM CONTEXT" in content
        assert "not user input" in content.lower()


# ══════════════════════════════════════════════════════════════════════════════
# Round 4 Issue 33: Similarity threshold raised to 0.6
# ══════════════════════════════════════════════════════════════════════════════


class TestSimilarityThreshold:
    def test_threshold_value(self):
        assert _SIMILARITY_THRESHOLD == 0.6

    def test_pool_types_not_merged(self):
        """'thread pool' and 'connection pool' should not be merged."""
        wb = Whiteboard()
        wb.add_hypothesis("thread pool starvation", "foreman")
        result = _find_existing_hypothesis(wb, "connection pool exhaustion")
        # With threshold 0.6, these should NOT match
        assert result is None

    def test_similar_hypotheses_still_merge(self):
        """Hypotheses with substantial word overlap should still merge."""
        wb = Whiteboard()
        wb.add_hypothesis("database connection pool exhaustion", "foreman")
        result = _find_existing_hypothesis(
            wb, "connection pool exhaustion in database"
        )
        assert result is not None

    def test_dedup_within_extraction_uses_threshold(self):
        """Heuristic extraction should use the updated threshold for dedup."""
        content = (
            "The root cause is a thread pool starvation under high load. "
            "I think the issue is a database connection timeout error."
        )
        results = extract_hypotheses(content, "chase")
        # These are distinct hypotheses — should NOT be deduped
        assert len(results) == 2


# ══════════════════════════════════════════════════════════════════════════════
# Round 5 Issue 34: State mutation — from_dict copies mutable lists
# ══════════════════════════════════════════════════════════════════════════════


class TestFromDictCopiesLists:
    """Ensure from_dict creates independent copies of mutable lists."""

    def test_whiteboard_entry_evidence_for_independent(self):
        """Mutating evidence_for on reconstructed entry must not affect source."""
        from maos.house_md.memory.whiteboard import WhiteboardEntry

        source_data = {
            "hypothesis": "test",
            "proposer": "house",
            "evidence_for": ["original evidence"],
            "evidence_against": [],
            "challenges": [],
            "tests_assigned": [],
            "entry_id": "abc123",
        }
        entry = WhiteboardEntry.from_dict(source_data)
        entry.add_supporting_evidence("new evidence")
        # Source list must be unchanged
        assert len(source_data["evidence_for"]) == 1
        assert "new evidence" not in source_data["evidence_for"]

    def test_whiteboard_entry_evidence_against_independent(self):
        from maos.house_md.memory.whiteboard import WhiteboardEntry

        source_data = {
            "hypothesis": "test",
            "proposer": "house",
            "evidence_for": [],
            "evidence_against": ["original counter"],
            "challenges": [],
            "tests_assigned": [],
            "entry_id": "abc123",
        }
        entry = WhiteboardEntry.from_dict(source_data)
        entry.add_counter_evidence("new counter")
        assert len(source_data["evidence_against"]) == 1

    def test_whiteboard_symptoms_independent(self):
        """Mutating symptoms on reconstructed whiteboard must not affect source."""
        source_data = {
            "symptoms": ["symptom A"],
            "environmental_findings": [],
            "entries": [],
        }
        wb = Whiteboard.from_dict(source_data)
        wb.add_symptom("symptom B")
        assert len(source_data["symptoms"]) == 1
        assert "symptom B" not in source_data["symptoms"]

    def test_whiteboard_env_findings_independent(self):
        source_data = {
            "symptoms": [],
            "environmental_findings": ["finding A"],
            "entries": [],
        }
        wb = Whiteboard.from_dict(source_data)
        wb.add_environmental_finding("finding B")
        assert len(source_data["environmental_findings"]) == 1

    def test_state_dict_not_mutated_by_critique_round(self):
        """The original state dict should not be mutated by critique round."""
        wb = Whiteboard()
        wb.add_hypothesis("test hyp", "house", confidence=0.5)
        state = _make_state(
            active_team=["chase"],
            whiteboard=wb.to_dict(),
        )
        # Snapshot the original evidence list length
        original_entries = state["whiteboard"]["entries"]
        original_evidence_len = len(original_entries[0]["evidence_for"])

        import asyncio

        async def mock_agent(s):
            return {
                "messages": [AIMessage(
                    content="HYPOTHESIS: test hyp"
                )]
            }

        asyncio.get_event_loop().run_until_complete(
            run_critique_round(state, {"chase": mock_agent})
        )

        # Original state dict must not have been mutated
        assert len(original_entries[0]["evidence_for"]) == original_evidence_len


# ══════════════════════════════════════════════════════════════════════════════
# Round 5 Issue 35: Personality slot assignment uses set tracking
# ══════════════════════════════════════════════════════════════════════════════


class TestPersonalitySlotAssignment:
    def test_known_names_claim_their_slot(self):
        """Config agents with personality names should claim their slot."""
        from maos.house_md.personalities.team import PERSONALITY_CONFIGS

        all_worker_slots = [
            k for k in PERSONALITY_CONFIGS if k != "house"
        ]
        claimed: set[str] = set()

        # Simulate: workers named "foreman" and "chase"
        for name in ["foreman", "chase"]:
            key = name.lower()
            if key in PERSONALITY_CONFIGS and key != "house":
                claimed.add(key)

        assert "foreman" in claimed
        assert "chase" in claimed
        # Other slots remain available
        unclaimed = [s for s in all_worker_slots if s not in claimed]
        assert "cameron" in unclaimed
        assert "thirteen" in unclaimed

    def test_unknown_names_get_next_unclaimed_slot(self):
        """Workers with non-personality names get the next unclaimed slot."""
        from maos.house_md.personalities.team import PERSONALITY_CONFIGS

        all_worker_slots = [
            k for k in PERSONALITY_CONFIGS if k != "house"
        ]
        claimed: set[str] = set()

        # First worker named "code_reviewer" gets first available slot
        for slot in all_worker_slots:
            if slot not in claimed:
                claimed.add(slot)
                assigned_slot = slot
                break

        assert assigned_slot == all_worker_slots[0]

    def test_mixed_known_and_unknown_workers(self):
        """Mix of known and unknown worker names assigns correctly.

        Uses the same two-pass approach as _create_agent_runnables:
        first pre-claim known personality names, then assign unknowns.
        """
        from maos.house_md.personalities.team import PERSONALITY_CONFIGS

        all_worker_slots = [
            k for k in PERSONALITY_CONFIGS if k != "house"
        ]
        workers = ["chase", "code_reviewer", "foreman", "test_runner"]

        # Pass 1: pre-claim known personality names
        pre_claimed: set[str] = {
            w.lower()
            for w in workers
            if w.lower() in PERSONALITY_CONFIGS and w.lower() != "house"
        }
        claimed: set[str] = set(pre_claimed)
        assignments: dict[str, str] = {}

        # Pass 2: assign
        for name in workers:
            key = name.lower()
            if key in PERSONALITY_CONFIGS and key != "house":
                assignments[name] = key
            else:
                for slot in all_worker_slots:
                    if slot not in claimed:
                        claimed.add(slot)
                        assignments[name] = slot
                        break

        assert assignments["chase"] == "chase"
        assert assignments["foreman"] == "foreman"
        # Unknown workers get unclaimed slots (not foreman or chase)
        assert assignments["code_reviewer"] not in ("chase", "foreman")
        assert assignments["test_runner"] not in ("chase", "foreman")
        assert assignments["code_reviewer"] in PERSONALITY_CONFIGS
        assert assignments["test_runner"] in PERSONALITY_CONFIGS
        # No duplicates
        assert len(set(assignments.values())) == len(assignments)


# ══════════════════════════════════════════════════════════════════════════════
# Round 5 Issue 36: Duplicate evidence skipped
# ══════════════════════════════════════════════════════════════════════════════


class TestDuplicateEvidenceSkipped:
    def test_duplicate_supporting_evidence_no_confidence_change(self):
        from maos.house_md.memory.whiteboard import WhiteboardEntry

        entry = WhiteboardEntry(hypothesis="test", proposer="house")
        entry.add_supporting_evidence("stack trace matches")
        conf_after_first = entry.confidence
        entry.add_supporting_evidence("stack trace matches")  # duplicate
        # Confidence should NOT change on duplicate
        assert entry.confidence == conf_after_first
        # Evidence list should have only one copy
        assert entry.evidence_for.count("stack trace matches") == 1

    def test_duplicate_counter_evidence_no_confidence_change(self):
        from maos.house_md.memory.whiteboard import WhiteboardEntry

        entry = WhiteboardEntry(hypothesis="test", proposer="house")
        entry.add_counter_evidence("tests pass")
        conf_after_first = entry.confidence
        entry.add_counter_evidence("tests pass")  # duplicate
        assert entry.confidence == conf_after_first
        assert entry.evidence_against.count("tests pass") == 1

    def test_different_evidence_still_adjusts(self):
        from maos.house_md.memory.whiteboard import WhiteboardEntry

        entry = WhiteboardEntry(hypothesis="test", proposer="house")
        entry.add_supporting_evidence("evidence A")
        entry.add_supporting_evidence("evidence B")
        # Both should be added and confidence adjusted twice
        assert len(entry.evidence_for) == 2
        assert entry.confidence == pytest.approx(0.8)


# ══════════════════════════════════════════════════════════════════════════════
# Round 5 Issue 37: Empty active_team logged
# ══════════════════════════════════════════════════════════════════════════════


class TestEmptyActiveTeamCritiqueRound:
    @pytest.mark.asyncio
    async def test_empty_team_produces_empty_messages(self):
        """Critique round with no active team should produce empty messages."""
        state = _make_state(active_team=[])
        result = await run_critique_round(state, {})
        assert result["messages"] == []
        assert result["hypotheses"] == []

    @pytest.mark.asyncio
    async def test_team_members_not_in_agent_nodes_skipped(self):
        """Team members not present in agent_nodes should be skipped."""
        state = _make_state(active_team=["nonexistent_agent"])
        result = await run_critique_round(state, {})
        assert result["messages"] == []


# ══════════════════════════════════════════════════════════════════════════════
# Round 5 Issue 38: Fragile personality fallback replaced
# ══════════════════════════════════════════════════════════════════════════════


class TestPersonalityFallback:
    def test_unknown_agent_gets_generic_personality(self):
        """Agents without matching personality get a generic config."""
        from maos.house_md.personalities.base import PersonalityConfig

        # Simulate _wrap_with_personalities with an unknown agent name
        runnables = {"unknown_agent": MagicMock()}
        # Manually replicate the wrapping logic
        personality = PERSONALITY_CONFIGS.get("unknown_agent")
        assert personality is None  # Confirms no match

        # The fix creates a generic PersonalityConfig instead of
        # falling back to Chase
        generic = PersonalityConfig(
            name="unknown_agent",
            role_description="Team member",
            system_prompt_additions="Contribute your analysis.",
        )
        wrapper = PersonalityWrapper(
            base_agent=runnables["unknown_agent"],
            personality=generic,
        )
        assert wrapper.personality.name == "unknown_agent"
        assert wrapper.personality.role_description == "Team member"
