"""Tests for the House MD graph factory integration.

Tests cover:
- HouseMDGraphFactory building with personality-wrapped agents
- GraphFactory mode branching (supervisor vs house_md)
- Diagnostic graph nodes invoking real agents
- Critique round integration within differential node
- Initial state creation for both modes in chat.py
- Iteration counter sync between whiteboard and graph
- Config mode field validation
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from maos.config.models import GraphConfig
from maos.house_md.graphs.differential_diagnosis import (
    create_initial_diagnostic_state,
)
from maos.house_md.graphs.factory import (
    HouseMDGraphFactory,
    _extract_content,
    _invoke_agent,
)
from maos.house_md.graphs.states import DiagnosticPhase, DiagnosticState
from maos.house_md.memory.whiteboard import Whiteboard
from maos.house_md.personalities.base import (
    PersonalityConfig,
    PersonalityWrapper,
)
from maos.house_md.personalities.team import PERSONALITY_CONFIGS

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_state(**overrides) -> DiagnosticState:
    """Create a minimal DiagnosticState for testing."""
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
    wrapper = PersonalityWrapper(base_agent=base, personality=personality)
    return wrapper


# ── GraphConfig mode field ───────────────────────────────────────────────────


class TestGraphConfigMode:
    def test_default_mode_is_supervisor(self):
        config = GraphConfig()
        assert config.mode == "supervisor"

    def test_house_md_mode(self):
        config = GraphConfig(mode="house_md")
        assert config.mode == "house_md"

    def test_invalid_mode_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GraphConfig(mode="invalid")


# ── _extract_content helper ──────────────────────────────────────────────────


class TestExtractContent:
    def test_extract_from_ai_message(self):
        result = {"messages": [AIMessage(content="hello", name="test")]}
        assert _extract_content(result) == "hello"

    def test_extract_from_dict_message(self):
        result = {"messages": [{"role": "assistant", "content": "world"}]}
        assert _extract_content(result) == "world"

    def test_extract_from_multiple_messages(self):
        result = {
            "messages": [
                AIMessage(content="first", name="a"),
                AIMessage(content="second", name="b"),
            ]
        }
        assert _extract_content(result) == "second"

    def test_empty_messages(self):
        result = {"messages": []}
        assert _extract_content(result) == "No response generated."

    def test_no_messages_key(self):
        result = {"other": "data"}
        assert _extract_content(result) == "No response generated."


# ── _invoke_agent helper ────────────────────────────────────────────────────


class TestInvokeAgent:
    @pytest.mark.asyncio
    async def test_invoke_success(self):
        agent = _mock_personality_agent("analysis complete")
        state = _make_state()

        result = await _invoke_agent(agent, state, "analyze this", "house")

        assert "messages" in result
        # Verify team context was set
        assert agent.team_context is not None
        assert "house" in agent.team_context.active_agents

    @pytest.mark.asyncio
    async def test_invoke_sets_team_context(self):
        agent = _mock_personality_agent()
        state = _make_state(active_team=["house", "foreman", "cameron"])

        await _invoke_agent(agent, state, "prompt", "house")

        assert agent.team_context.active_agents == [
            "house", "foreman", "cameron"
        ]
        assert agent.team_context.current_phase == "intake"

    @pytest.mark.asyncio
    async def test_invoke_handles_error(self):
        agent = _mock_personality_agent()
        agent.base_agent.ainvoke.side_effect = RuntimeError("LLM timeout")

        state = _make_state()
        result = await _invoke_agent(agent, state, "test", "house")

        # Should return error message instead of crashing
        messages = result.get("messages", [])
        assert len(messages) == 1
        assert "Error" in messages[0].content


# ── HouseMDGraphFactory ─────────────────────────────────────────────────────


class TestHouseMDGraphFactory:
    def _make_factory(self):
        """Create a factory with mocked dependencies."""
        config = MagicMock()
        config.graph.max_iterations = 5
        config.graph.mode = "house_md"
        config.llms = {
            "frontier": MagicMock(),
            "mid-tier": MagicMock(),
            "precise": MagicMock(),
        }

        agent_registry = MagicMock()
        # Mock workers
        worker1 = MagicMock()
        worker1.llm_name = "mid-tier"
        worker1.system_prompt = "You are Foreman"
        worker1.tool_ids = []
        worker2 = MagicMock()
        worker2.llm_name = "precise"
        worker2.system_prompt = "You are Chase"
        worker2.tool_ids = []
        agent_registry.get_workers.return_value = [
            ("foreman", worker1),
            ("chase", worker2),
        ]

        # Mock supervisor
        supervisor = MagicMock()
        supervisor.name = "house"
        supervisor.llm_name = "frontier"
        supervisor.system_prompt = "You are House"
        agent_registry.get_supervisor.return_value = supervisor

        llm_factory = MagicMock()
        llm_factory.create_chat_model.return_value = MagicMock()

        tool_registry = MagicMock()

        return HouseMDGraphFactory(
            config=config,
            agent_registry=agent_registry,
            llm_factory=llm_factory,
            tool_registry=tool_registry,
        )

    @patch("maos.house_md.graphs.factory.create_react_agent")
    def test_create_agent_runnables(self, mock_create):
        """Agents are created for workers + supervisor."""
        mock_create.return_value = MagicMock()
        factory = self._make_factory()

        runnables = factory._create_agent_runnables()

        # Should have foreman, chase, and house
        assert "foreman" in runnables
        assert "chase" in runnables
        assert "house" in runnables
        assert mock_create.call_count == 3

    @patch("maos.house_md.graphs.factory.create_react_agent")
    def test_wrap_with_personalities(self, mock_create):
        """Each agent is wrapped with its House MD personality."""
        mock_create.return_value = MagicMock()
        factory = self._make_factory()

        runnables = factory._create_agent_runnables()
        wrapped = factory._wrap_with_personalities(runnables)

        for name, wrapper in wrapped.items():
            assert isinstance(wrapper, PersonalityWrapper)
            if name in PERSONALITY_CONFIGS:
                assert wrapper.personality.name == PERSONALITY_CONFIGS[name].name

    @patch("maos.house_md.graphs.factory.create_react_agent")
    def test_build_returns_state_graph(self, mock_create):
        """build() returns a StateGraph with all diagnostic nodes."""
        mock_create.return_value = MagicMock()
        factory = self._make_factory()

        graph = factory.build()

        # Verify all nodes are present
        node_names = set(graph.nodes.keys())
        expected = {
            "intake", "differential", "provocation",
            "testing", "environmental", "wilson_consult", "resolution",
        }
        assert expected.issubset(node_names)

    @patch("maos.house_md.graphs.factory.create_react_agent")
    def test_compile_returns_compiled_graph(self, mock_create):
        """compile() returns a runnable compiled graph."""
        mock_create.return_value = MagicMock()
        factory = self._make_factory()

        compiled = factory.compile()

        # Should have ainvoke method
        assert hasattr(compiled, "ainvoke")


# ── GraphFactory mode branching ──────────────────────────────────────────────


class TestGraphFactoryModeBranching:
    def test_supervisor_mode_uses_create_supervisor(self):
        """Default mode builds with langgraph-supervisor."""
        from maos.graph.factory import GraphFactory

        config = MagicMock()
        config.graph.mode = "supervisor"
        config.graph.max_iterations = 12

        factory = GraphFactory(
            config=config,
            agent_registry=MagicMock(),
            llm_factory=MagicMock(),
            tool_registry=MagicMock(),
        )

        with patch.object(factory, '_build_house_md') as mock_hmd:
            # Supervisor path will fail (mocked deps), but house_md shouldn't be called
            try:
                factory.build()
            except Exception:
                pass
            mock_hmd.assert_not_called()

    def test_house_md_mode_delegates_to_house_md_factory(self):
        """house_md mode delegates to HouseMDGraphFactory."""
        from maos.graph.factory import GraphFactory

        config = MagicMock()
        config.graph.mode = "house_md"

        factory = GraphFactory(
            config=config,
            agent_registry=MagicMock(),
            llm_factory=MagicMock(),
            tool_registry=MagicMock(),
        )

        with patch(
            "maos.house_md.graphs.factory.HouseMDGraphFactory"
        ) as mock_hmd_factory:
            mock_instance = MagicMock()
            mock_instance.build.return_value = MagicMock()
            mock_hmd_factory.return_value = mock_instance

            factory.build()

            mock_hmd_factory.assert_called_once()
            mock_instance.build.assert_called_once()


# ── Chat route state creation branching ──────────────────────────────────────


class TestChatRouteStateBranching:
    def test_supervisor_mode_creates_graph_state(self):
        """In supervisor mode, create_initial_state is used."""
        from maos.graph.state import create_initial_state

        messages = [{"role": "user", "content": "fix the bug"}]
        state = create_initial_state(
            messages=messages, roster=["foreman", "chase"], thread_id="t1"
        )

        assert "task" in state
        assert "roster" in state
        assert state["task"] == "fix the bug"
        assert state["roster"] == ["foreman", "chase"]

    def test_house_md_mode_creates_diagnostic_state(self):
        """In house_md mode, create_initial_diagnostic_state is used."""
        state = create_initial_diagnostic_state(
            user_message="API returns 500 errors intermittently",
            active_team=["house", "foreman", "chase"],
        )

        assert "symptoms" in state
        assert "whiteboard" in state
        assert "current_phase" in state
        assert state["symptoms"] == ["API returns 500 errors intermittently"]
        assert state["active_team"] == ["house", "foreman", "chase"]

    def test_diagnostic_state_has_api_compatible_fields(self):
        """DiagnosticState result can be consumed by chat.py response builder."""
        state = create_initial_diagnostic_state(
            user_message="test",
            active_team=["house"],
        )

        # chat.py accesses these with .get() defaults:
        assert isinstance(state.get("messages", []), list)
        assert isinstance(state.get("iteration", 0), int)
        # "done" defaults to True in chat.py, absent from DiagnosticState is OK
        assert state.get("done", True) is True
        # "last_result" defaults to None in chat.py
        assert state.get("last_result") is None


# ── Iteration counter sync (Issue 6) ────────────────────────────────────────


class TestIterationSync:
    def test_whiteboard_advance_phase_syncs_iteration(self):
        """advance_phase with iteration arg syncs the counter."""
        wb = Whiteboard()
        wb.advance_phase("differential", iteration=3)
        assert wb.iteration_count == 3
        assert wb.current_phase == "differential"

    def test_whiteboard_advance_phase_without_iteration_increments(self):
        """advance_phase without iteration arg still increments."""
        wb = Whiteboard()
        assert wb.iteration_count == 0
        wb.advance_phase("intake")
        assert wb.iteration_count == 1
        wb.advance_phase("differential")
        assert wb.iteration_count == 2

    def test_provocation_node_increments_and_syncs(self):
        """provocation_node increments iteration and syncs whiteboard."""
        from maos.house_md.graphs.differential_diagnosis import (
            provocation_node,
        )

        state = _make_state(iteration=2)
        result = provocation_node(state)

        # Graph iteration incremented
        assert result["iteration"] == 3
        # Whiteboard synced
        wb = Whiteboard.from_dict(result["whiteboard"])
        assert wb.iteration_count == 3

    def test_testing_node_does_not_increment(self):
        """testing_node keeps iteration unchanged and syncs whiteboard."""
        from maos.house_md.graphs.differential_diagnosis import (
            testing_node as run_testing_node,
        )

        state = _make_state(iteration=4)
        result = run_testing_node(state)

        # No "iteration" in result — it didn't increment
        assert "iteration" not in result
        # Whiteboard synced to current iteration
        wb = Whiteboard.from_dict(result["whiteboard"])
        assert wb.iteration_count == 4

    def test_intake_syncs_whiteboard_to_zero(self):
        """intake_node syncs whiteboard iteration to graph's 0."""
        from maos.house_md.graphs.differential_diagnosis import intake_node

        state = _make_state(iteration=0)
        result = intake_node(state)

        wb = Whiteboard.from_dict(result["whiteboard"])
        assert wb.iteration_count == 0


# ── Personality wrapper integration ──────────────────────────────────────────


class TestPersonalityIntegration:
    def test_wrapper_used_in_factory(self):
        """HouseMDGraphFactory wraps agents with PersonalityWrapper."""
        with patch(
            "maos.house_md.graphs.factory.create_react_agent"
        ) as mock_create:
            mock_create.return_value = MagicMock()

            config = MagicMock()
            config.graph.max_iterations = 5
            config.llms = {"frontier": MagicMock(), "mid-tier": MagicMock()}

            agent_registry = MagicMock()
            worker = MagicMock()
            worker.llm_name = "mid-tier"
            worker.system_prompt = "prompt"
            worker.tool_ids = []
            agent_registry.get_workers.return_value = [("foreman", worker)]

            supervisor = MagicMock()
            supervisor.name = "house"
            supervisor.llm_name = "frontier"
            supervisor.system_prompt = "sup prompt"
            agent_registry.get_supervisor.return_value = supervisor

            factory = HouseMDGraphFactory(
                config=config,
                agent_registry=agent_registry,
                llm_factory=MagicMock(),
                tool_registry=MagicMock(),
            )

            runnables = factory._create_agent_runnables()
            wrapped = factory._wrap_with_personalities(runnables)

            # Foreman should be wrapped with Foreman personality
            assert "foreman" in wrapped
            assert wrapped["foreman"].personality.name == "Foreman"
            # House should be wrapped with House personality
            assert "house" in wrapped
            assert wrapped["house"].personality.name == "House"

    @pytest.mark.asyncio
    async def test_team_context_updated_per_invocation(self):
        """team_context is updated for each phase invocation."""
        agent = _mock_personality_agent("response")
        state1 = _make_state(
            current_phase="intake",
            active_team=["house", "foreman"],
        )
        state2 = _make_state(
            current_phase="testing",
            active_team=["house", "chase"],
        )

        await _invoke_agent(agent, state1, "prompt", "house")
        assert agent.team_context.current_phase == "intake"
        assert agent.team_context.active_agents == ["house", "foreman"]

        await _invoke_agent(agent, state2, "prompt", "house")
        assert agent.team_context.current_phase == "testing"
        assert agent.team_context.active_agents == ["house", "chase"]


# ── Critique round wiring ───────────────────────────────────────────────────


class TestCritiqueRoundWiring:
    @pytest.mark.asyncio
    async def test_critique_round_called_with_personality_agents(self):
        """Differential node calls run_critique_round with real agents."""
        agents = {
            "house": _mock_personality_agent("House says: interesting"),
            "foreman": _mock_personality_agent("Foreman says: risky"),
            "chase": _mock_personality_agent("Chase says: let me fix"),
        }

        state = _make_state(active_team=["house", "foreman", "chase"])

        from maos.house_md.graphs.critique_round import run_critique_round

        result = await run_critique_round(state, agents)

        # Should have messages from active team members
        messages = result.get("messages", [])
        assert len(messages) > 0

        # Should have agent beliefs recorded
        beliefs = result.get("agent_beliefs", {})
        assert "house" in beliefs or "foreman" in beliefs or "chase" in beliefs

    @pytest.mark.asyncio
    async def test_critique_round_skips_missing_agents(self):
        """Agents not in agent_nodes are skipped."""
        agents = {
            "foreman": _mock_personality_agent("Foreman here"),
        }

        state = _make_state(active_team=["house", "foreman", "chase"])

        from maos.house_md.graphs.critique_round import run_critique_round

        result = await run_critique_round(state, agents)

        messages = result.get("messages", [])
        # Only foreman should have responded
        assert len(messages) == 1
        assert "foreman" in messages[0].content.lower()


# ── Config validation ────────────────────────────────────────────────────────


class TestHouseMDConfigValidation:
    def test_house_md_yaml_loads_with_mode(self):
        """config.house_md.yaml loads and has mode: house_md."""
        from maos.config.loader import ConfigLoader

        loader = ConfigLoader()
        config = loader.load("config.house_md.yaml")

        assert config.graph.mode == "house_md"
        assert len(config.agents) == 7
        assert config.graph.max_iterations == 15

    def test_default_config_has_supervisor_mode(self):
        """config.example.yaml has default supervisor mode."""
        from maos.config.loader import ConfigLoader

        loader = ConfigLoader()
        config = loader.load("config.example.yaml")

        assert config.graph.mode == "supervisor"
