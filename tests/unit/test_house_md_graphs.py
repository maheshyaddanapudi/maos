"""Tests for House MD diagnostic graphs."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from maos.house_md.graphs.critique_round import (
    _build_critique_prompt,
    run_critique_round,
)
from maos.house_md.graphs.differential_diagnosis import (
    create_diagnostic_graph,
    create_initial_diagnostic_state,
    differential_node,
    environmental_node,
    intake_node,
    provocation_node,
    resolution_node,
    route_after_provocation,
    wilson_consult_node,
)
from maos.house_md.graphs.differential_diagnosis import (
    testing_node as run_testing_node,
)
from maos.house_md.graphs.states import DiagnosticPhase
from maos.house_md.memory.whiteboard import Whiteboard

# ── DiagnosticState ──────────────────────────────────────────────────────────


class TestDiagnosticState:
    def test_create_initial_state(self):
        state = create_initial_diagnostic_state("Server returns 500 errors")
        assert len(state["messages"]) == 1
        assert state["symptoms"] == ["Server returns 500 errors"]
        assert state["hypotheses"] == []
        assert state["current_phase"] == "intake"
        assert state["final_diagnosis"] is None
        assert state["confidence"] == 0.0
        assert state["iteration"] == 0

    def test_create_initial_state_custom_team(self):
        state = create_initial_diagnostic_state(
            "Bug report",
            active_team=["house", "chase"],
        )
        assert state["active_team"] == ["house", "chase"]

    def test_create_initial_state_default_team(self):
        state = create_initial_diagnostic_state("Test")
        assert "house" in state["active_team"]
        assert "foreman" in state["active_team"]
        assert "cameron" in state["active_team"]
        assert "chase" in state["active_team"]


class TestDiagnosticPhase:
    def test_all_phases(self):
        phases = [p.value for p in DiagnosticPhase]
        assert "intake" in phases
        assert "differential" in phases
        assert "provocation" in phases
        assert "testing" in phases
        assert "environmental" in phases
        assert "wilson_consult" in phases
        assert "resolution" in phases


# ── Graph Nodes ──────────────────────────────────────────────────────────────


class TestIntakeNode:
    def test_records_symptoms(self):
        state = create_initial_diagnostic_state("Error 500")
        result = intake_node(state)
        assert result["current_phase"] == "intake"
        assert "Error 500" in result["symptoms"]
        assert len(result["messages"]) == 1
        assert "Intake" in result["messages"][0].content

    def test_intake_everybody_lies(self):
        state = create_initial_diagnostic_state("Server is broken")
        result = intake_node(state)
        assert "everybody lies" in result["messages"][0].content.lower()


class TestDifferentialNode:
    def test_starts_whiteboard_session(self):
        state = create_initial_diagnostic_state("Memory leak")
        result = differential_node(state)
        assert result["current_phase"] == "differential"
        assert "Whiteboard session" in result["messages"][0].content
        assert "Memory leak" in result["messages"][0].content

    def test_mentions_active_team(self):
        state = create_initial_diagnostic_state(
            "Bug", active_team=["house", "foreman", "chase"]
        )
        result = differential_node(state)
        content = result["messages"][0].content
        assert "house" in content
        assert "foreman" in content
        assert "chase" in content


class TestProvocationNode:
    def test_no_hypotheses(self):
        state = create_initial_diagnostic_state("Error")
        result = provocation_node(state)
        assert result["current_phase"] == "provocation"
        assert "Nothing on the board" in result["messages"][0].content
        assert result["iteration"] == 1

    def test_single_hypothesis(self):
        state = create_initial_diagnostic_state("Error")
        wb = Whiteboard.from_dict(state["whiteboard"])
        wb.add_hypothesis("DB timeout", "foreman", confidence=0.6)
        state["whiteboard"] = wb.to_dict()
        result = provocation_node(state)
        content = result["messages"][0].content
        assert "too obvious" in content.lower() or "DB timeout" in content

    def test_high_confidence_triggers_skepticism(self):
        state = create_initial_diagnostic_state("Error")
        wb = Whiteboard.from_dict(state["whiteboard"])
        wb.add_hypothesis("Known bug", "chase", confidence=0.9)
        wb.add_hypothesis("Config issue", "foreman", confidence=0.3)
        state["whiteboard"] = wb.to_dict()
        result = provocation_node(state)
        content = result["messages"][0].content
        assert "confident" in content.lower() or "NOT seeing" in content

    def test_multiple_hypotheses(self):
        state = create_initial_diagnostic_state("Error")
        wb = Whiteboard.from_dict(state["whiteboard"])
        wb.add_hypothesis("A", "chase", confidence=0.4)
        wb.add_hypothesis("B", "foreman", confidence=0.5)
        wb.add_hypothesis("C", "cameron", confidence=0.3)
        state["whiteboard"] = wb.to_dict()
        result = provocation_node(state)
        content = result["messages"][0].content
        assert "differentials" in content.lower() or "rule out" in content.lower()

    def test_iteration_increments(self):
        state = create_initial_diagnostic_state("Error")
        state["iteration"] = 2
        result = provocation_node(state)
        assert result["iteration"] == 3


class TestTestingNodeFunc:
    def test_runs_tests(self):
        state = create_initial_diagnostic_state("Bug")
        wb = Whiteboard.from_dict(state["whiteboard"])
        wb.add_hypothesis("Race condition", "thirteen")
        state["whiteboard"] = wb.to_dict()
        result = run_testing_node(state)
        assert result["current_phase"] == "testing"
        assert "Testing" in result["messages"][0].content


class TestEnvironmentalNode:
    def test_investigates_environment(self):
        state = create_initial_diagnostic_state("Performance issue")
        result = environmental_node(state)
        assert result["current_phase"] == "environmental"
        content = result["messages"][0].content
        assert "environmental" in content.lower() or "patient" in content.lower()


class TestWilsonConsultNode:
    def test_provides_insight(self):
        state = create_initial_diagnostic_state("Stuck problem")
        result = wilson_consult_node(state)
        assert result["current_phase"] == "wilson_consult"
        assert "Wilson" in result["messages"][0].content

    def test_references_symptoms(self):
        state = create_initial_diagnostic_state("Memory leak")
        result = wilson_consult_node(state)
        content = result["messages"][0].content
        assert "Memory leak" in content or "what you think" in content


class TestResolutionNode:
    def test_confirms_top_hypothesis(self):
        state = create_initial_diagnostic_state("Error")
        wb = Whiteboard.from_dict(state["whiteboard"])
        wb.add_hypothesis("Root cause found", "house", confidence=0.9)
        state["whiteboard"] = wb.to_dict()
        result = resolution_node(state)
        assert result["current_phase"] == "resolution"
        assert result["final_diagnosis"] == "Root cause found"
        # Confidence should reflect the pre-confirm value, not 1.0
        assert result["confidence"] == 0.9
        assert "Root cause found" in result["messages"][0].content
        assert "Chase" in result["messages"][0].content

    def test_inconclusive(self):
        state = create_initial_diagnostic_state("Mystery")
        result = resolution_node(state)
        assert result["final_diagnosis"] is None
        assert result["confidence"] == 0.0
        assert "Inconclusive" in result["messages"][0].content


# ── Routing ──────────────────────────────────────────────────────────────────


class TestRouteAfterProvocation:
    def test_max_iterations_goes_to_resolution(self):
        state = create_initial_diagnostic_state("Test")
        state["iteration"] = 5
        assert route_after_provocation(state) == "resolution"

    def test_high_confidence_goes_to_resolution(self):
        state = create_initial_diagnostic_state("Test")
        state["iteration"] = 1
        wb = Whiteboard.from_dict(state["whiteboard"])
        wb.add_hypothesis("Answer", "house", confidence=0.9)
        state["whiteboard"] = wb.to_dict()
        assert route_after_provocation(state) == "resolution"

    def test_no_hypotheses_goes_to_wilson(self):
        state = create_initial_diagnostic_state("Test")
        state["iteration"] = 1
        assert route_after_provocation(state) == "wilson_consult"

    def test_iteration_2_goes_to_environmental(self):
        state = create_initial_diagnostic_state("Test")
        state["iteration"] = 2
        wb = Whiteboard.from_dict(state["whiteboard"])
        wb.add_hypothesis("Something", "chase", confidence=0.5)
        state["whiteboard"] = wb.to_dict()
        assert route_after_provocation(state) == "environmental"

    def test_default_goes_to_testing(self):
        state = create_initial_diagnostic_state("Test")
        state["iteration"] = 1
        wb = Whiteboard.from_dict(state["whiteboard"])
        wb.add_hypothesis("Something", "chase", confidence=0.5)
        state["whiteboard"] = wb.to_dict()
        assert route_after_provocation(state) == "testing"

    def test_environmental_already_done_goes_to_testing(self):
        state = create_initial_diagnostic_state("Test")
        state["iteration"] = 3
        wb = Whiteboard.from_dict(state["whiteboard"])
        wb.add_hypothesis("Something", "chase", confidence=0.5)
        wb.add_environmental_finding("Found something")
        state["whiteboard"] = wb.to_dict()
        assert route_after_provocation(state) == "testing"


# ── Graph Construction ───────────────────────────────────────────────────────


class TestDiagnosticGraph:
    def test_graph_compiles(self):
        graph = create_diagnostic_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_graph_has_all_nodes(self):
        graph = create_diagnostic_graph()
        node_names = set(graph.nodes.keys())
        expected = {
            "intake", "differential", "provocation",
            "testing", "environmental", "wilson_consult", "resolution",
        }
        assert expected.issubset(node_names)


# ── Critique Round ───────────────────────────────────────────────────────────


class TestCritiqueRound:
    def test_build_critique_prompt(self):
        wb = Whiteboard()
        wb.add_hypothesis("Memory leak", "foreman", confidence=0.7)
        prompt = _build_critique_prompt(wb, "chase")
        assert "chase" in prompt
        assert "Memory leak" in prompt
        assert "support or challenge" in prompt

    @pytest.mark.asyncio
    async def test_run_critique_round(self):
        state = create_initial_diagnostic_state("Error")
        wb = Whiteboard.from_dict(state["whiteboard"])
        wb.add_hypothesis("DB issue", "foreman")
        state["whiteboard"] = wb.to_dict()
        state["active_team"] = ["foreman", "chase"]

        async def mock_agent(s):
            return {"messages": [AIMessage(content="I agree with DB issue")]}

        agent_nodes = {
            "foreman": mock_agent,
            "chase": mock_agent,
        }

        result = await run_critique_round(state, agent_nodes)
        assert "agent_beliefs" in result
        assert "foreman" in result["agent_beliefs"]
        assert "chase" in result["agent_beliefs"]

    @pytest.mark.asyncio
    async def test_run_critique_round_with_ainvoke(self):
        state = create_initial_diagnostic_state("Bug")
        state["active_team"] = ["wilson"]
        wb = Whiteboard.from_dict(state["whiteboard"])
        wb.add_hypothesis("Config error", "house")
        state["whiteboard"] = wb.to_dict()

        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="What if it's simpler?")]
        })

        result = await run_critique_round(state, {"wilson": mock_agent})
        assert "wilson" in result["agent_beliefs"]

    @pytest.mark.asyncio
    async def test_run_critique_round_skips_missing_agents(self):
        state = create_initial_diagnostic_state("Error")
        state["active_team"] = ["house", "nonexistent_agent"]

        async def mock_agent(s):
            return {"messages": [AIMessage(content="Response")]}

        result = await run_critique_round(state, {"house": mock_agent})
        assert "house" in result["agent_beliefs"]
        assert "nonexistent_agent" not in result["agent_beliefs"]

    @pytest.mark.asyncio
    async def test_run_critique_round_skips_non_invocable(self):
        state = create_initial_diagnostic_state("Error")
        state["active_team"] = ["broken"]

        result = await run_critique_round(state, {"broken": "not_callable"})
        assert "broken" not in result.get("agent_beliefs", {})
