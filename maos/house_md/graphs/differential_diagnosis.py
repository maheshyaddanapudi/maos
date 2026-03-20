"""Differential diagnosis graph — the core House MD diagnostic workflow.

Implements the 5-phase diagnostic protocol as a LangGraph StateGraph:
1. Intake — gather and verify symptoms
2. Differential — team brainstorms hypotheses
3. Provocation — House challenges and synthesizes
4. Testing/Environmental — run tests, investigate context
5. Resolution — House makes the final call

The graph supports iteration: after testing, control returns to
provocation for re-evaluation, mimicking the show's "reconvene and restart"
pattern.
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from maos.house_md.graphs.states import DiagnosticPhase, DiagnosticState
from maos.house_md.memory.whiteboard import Whiteboard

MAX_ITERATIONS = 5


def create_initial_diagnostic_state(
    user_message: str | None = None,
    user_messages: list[str] | None = None,
    active_team: list[str] | None = None,
) -> DiagnosticState:
    """Create the initial state for a diagnostic session.

    Accepts either a single ``user_message`` (backwards-compatible) or a
    list of ``user_messages`` for multi-turn conversations.  All user
    messages are recorded as symptoms and included in the message history.
    """
    if active_team is None:
        active_team = ["house", "foreman", "cameron", "chase"]

    # Normalise to a list of messages
    msgs: list[str] = []
    if user_messages:
        msgs = list(user_messages)
    elif user_message:
        msgs = [user_message]

    whiteboard = Whiteboard()
    for m in msgs:
        whiteboard.add_symptom(m)

    return DiagnosticState(
        messages=[HumanMessage(content=m) for m in msgs] if msgs else [],
        symptoms=list(msgs),
        hypotheses=[],
        evidence={},
        current_phase=DiagnosticPhase.INTAKE.value,
        agent_beliefs={},
        whiteboard=whiteboard.to_dict(),
        final_diagnosis=None,
        confidence=0.0,
        iteration=0,
        active_team=active_team,
    )


def intake_node(state: DiagnosticState) -> dict[str, Any]:
    """Phase 1: Gather and verify initial symptoms.

    'Everybody lies' — question assumptions about what's reported.
    """
    whiteboard = Whiteboard.from_dict(state["whiteboard"])
    iteration = state.get("iteration", 0)
    whiteboard.advance_phase(DiagnosticPhase.INTAKE.value, iteration)

    messages = list(state["messages"])
    last_user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break
        if isinstance(msg, dict) and msg.get("role") == "user":
            last_user_msg = msg["content"]
            break

    symptoms = list(state.get("symptoms", []))
    if last_user_msg and last_user_msg not in symptoms:
        symptoms.append(last_user_msg)
        whiteboard.add_symptom(last_user_msg)

    intake_msg = AIMessage(
        content=(
            f"[House - Intake] Case presented. Initial symptoms recorded. "
            f"Remember: everybody lies. Let's verify before we diagnose.\n\n"
            f"Symptoms: {', '.join(symptoms)}"
        ),
        name="house",
    )

    return {
        "messages": [intake_msg],
        "symptoms": symptoms,
        "current_phase": DiagnosticPhase.INTAKE.value,
        "whiteboard": whiteboard.to_dict(),
    }


def differential_node(state: DiagnosticState) -> dict[str, Any]:
    """Phase 2: Team brainstorms hypotheses (whiteboard session).

    Each active team member proposes hypotheses from their specialty.
    """
    whiteboard = Whiteboard.from_dict(state["whiteboard"])
    iteration = state.get("iteration", 0)
    whiteboard.advance_phase(DiagnosticPhase.DIFFERENTIAL.value, iteration)

    symptoms_text = ", ".join(state.get("symptoms", ["unknown"]))

    diff_msg = AIMessage(
        content=(
            f"[House - Differential] Whiteboard session. "
            f"Symptoms: {symptoms_text}. "
            f"Team, what are we looking at? No idea dismissed without consideration. "
            f"Active team: {', '.join(state.get('active_team', []))}."
        ),
        name="house",
    )

    return {
        "messages": [diff_msg],
        "current_phase": DiagnosticPhase.DIFFERENTIAL.value,
        "whiteboard": whiteboard.to_dict(),
    }


def provocation_node(state: DiagnosticState) -> dict[str, Any]:
    """Phase 3: House synthesizes, challenges, and provokes.

    Implements House's meta-cognitive analysis:
    - Detect premature consensus (groupthink discount)
    - Challenge weak evidence
    - Exploit known agent biases productively
    - Override if pattern recognition triggers
    """
    whiteboard = Whiteboard.from_dict(state["whiteboard"])
    iteration = state.get("iteration", 0) + 1
    whiteboard.advance_phase(DiagnosticPhase.PROVOCATION.value, iteration)

    active = whiteboard.get_active_hypotheses()
    top = whiteboard.get_top_hypothesis()

    if not active:
        provocation = (
            "[House - Provocation] Nothing on the board yet. "
            "That's either very bad or very lazy. "
            "Team, give me differentials. Now."
        )
    elif len(active) == 1 and top:
        provocation = (
            f"[House - Provocation] Only one hypothesis? '{top.hypothesis}'? "
            f"That's too obvious. It's never the obvious answer. "
            f"What else could explain {', '.join(state.get('symptoms', []))}? "
            f"Foreman, challenge this. Cameron, what about the user impact?"
        )
    elif top and top.confidence > 0.8:
        provocation = (
            f"[House - Provocation] Everyone seems very confident about "
            f"'{top.hypothesis}'. Too confident. "
            f"Confidence: {top.confidence:.0%}. "
            f"What are we NOT seeing? What if everybody's lying?"
        )
    else:
        hyp_summary = "; ".join(
            f"'{h.hypothesis}' ({h.confidence:.0%})" for h in active[:3]
        )
        provocation = (
            f"[House - Provocation] Current differentials: {hyp_summary}. "
            f"Iteration {iteration}. "
            f"Which ones can we rule out? What tests do we need?"
        )

    return {
        "messages": [AIMessage(content=provocation, name="house")],
        "current_phase": DiagnosticPhase.PROVOCATION.value,
        "whiteboard": whiteboard.to_dict(),
        "iteration": iteration,
    }


def testing_node(state: DiagnosticState) -> dict[str, Any]:
    """Phase 4a: Run tests to rule out hypotheses.

    'It's never lupus' — common diagnoses were likely already ruled out.
    """
    whiteboard = Whiteboard.from_dict(state["whiteboard"])
    iteration = state.get("iteration", 0)
    whiteboard.advance_phase(DiagnosticPhase.TESTING.value, iteration)

    active = whiteboard.get_active_hypotheses()
    test_summary = ", ".join(h.hypothesis for h in active[:3])

    testing_msg = AIMessage(
        content=(
            f"[Chase - Testing] Running tests against: {test_summary}. "
            f"Results will update hypothesis probabilities."
        ),
        name="chase",
    )

    return {
        "messages": [testing_msg],
        "current_phase": DiagnosticPhase.TESTING.value,
        "whiteboard": whiteboard.to_dict(),
    }


def environmental_node(state: DiagnosticState) -> dict[str, Any]:
    """Phase 4b: Investigate context beyond immediate symptoms.

    'Break into their house' — examine codebase history, deployment
    environment, user patterns. Find what the patient isn't telling us.
    """
    whiteboard = Whiteboard.from_dict(state["whiteboard"])
    iteration = state.get("iteration", 0)
    whiteboard.advance_phase(DiagnosticPhase.ENVIRONMENTAL.value, iteration)

    env_msg = AIMessage(
        content=(
            "[Thirteen - Environmental] Investigating beyond the reported symptoms. "
            "Checking codebase history, deployment context, and user patterns. "
            "What isn't the 'patient' telling us?"
        ),
        name="thirteen",
    )

    return {
        "messages": [env_msg],
        "current_phase": DiagnosticPhase.ENVIRONMENTAL.value,
        "whiteboard": whiteboard.to_dict(),
    }


def wilson_consult_node(state: DiagnosticState) -> dict[str, Any]:
    """Phase 4c: Wilson consultation for breakthrough insight.

    House talks to Wilson about something seemingly unrelated.
    The eureka trigger: cross-domain insight that unlocks the case.
    """
    whiteboard = Whiteboard.from_dict(state["whiteboard"])
    iteration = state.get("iteration", 0)
    whiteboard.advance_phase(DiagnosticPhase.WILSON_CONSULT.value, iteration)

    symptoms = state.get("symptoms", [])
    wilson_msg = AIMessage(
        content=(
            f"[Wilson - Consult] House, you've been staring at this for too long. "
            f"Let me ask you something completely different — "
            f"what if the problem isn't about {symptoms[0] if symptoms else 'what you think'}? "
            f"What if it's about context you haven't examined yet? "
            f"Sometimes the answer is right in front of you, hidden in plain sight."
        ),
        name="wilson",
    )

    return {
        "messages": [wilson_msg],
        "current_phase": DiagnosticPhase.WILSON_CONSULT.value,
        "whiteboard": whiteboard.to_dict(),
    }


def resolution_node(state: DiagnosticState) -> dict[str, Any]:
    """Phase 5: House makes the final diagnostic call.

    If confident: House announces the diagnosis and Chase implements.
    If not: summarize the best hypothesis and explain remaining uncertainty.
    """
    whiteboard = Whiteboard.from_dict(state["whiteboard"])
    iteration = state.get("iteration", 0)
    whiteboard.advance_phase(DiagnosticPhase.RESOLUTION.value, iteration)

    confirmed = whiteboard.get_confirmed()
    top = whiteboard.get_top_hypothesis()
    diagnosis = confirmed or top

    if diagnosis:
        # Capture confidence BEFORE confirm() sets it to 1.0
        pre_confirm_confidence = diagnosis.confidence
        resolution_msg = AIMessage(
            content=(
                f"[House - Resolution] Diagnosis: {diagnosis.hypothesis}. "
                f"Confidence: {pre_confirm_confidence:.0%}. "
                f"Proposed by: {diagnosis.proposer}. "
                f"Evidence: {', '.join(diagnosis.evidence_for) or 'clinical judgment'}. "
                f"Chase, implement the fix."
            ),
            name="house",
        )
        final_diagnosis = diagnosis.hypothesis
        confidence = pre_confirm_confidence
        diagnosis.confirm()
    else:
        resolution_msg = AIMessage(
            content=(
                "[House - Resolution] Inconclusive. No hypothesis reached "
                "sufficient confidence. Recommending further investigation "
                "or escalation to Cuddy for governance review."
            ),
            name="house",
        )
        final_diagnosis = None
        confidence = 0.0

    return {
        "messages": [resolution_msg],
        "current_phase": DiagnosticPhase.RESOLUTION.value,
        "whiteboard": whiteboard.to_dict(),
        "final_diagnosis": final_diagnosis,
        "confidence": confidence,
    }


def route_after_provocation(
    state: DiagnosticState,
) -> Literal["testing", "environmental", "wilson_consult", "resolution"]:
    """Route after House's provocation based on diagnostic state.

    Decision logic:
    - If max iterations reached → resolution
    - If a hypothesis is confirmed (confidence > 0.85) → resolution
    - If stuck (no active hypotheses) → wilson_consult
    - If environmental factors not yet investigated → environmental
    - Default → testing
    """
    iteration = state.get("iteration", 0)
    if iteration >= MAX_ITERATIONS:
        return "resolution"

    whiteboard = Whiteboard.from_dict(state["whiteboard"])
    top = whiteboard.get_top_hypothesis()

    if top and top.confidence > 0.85:
        return "resolution"

    active = whiteboard.get_active_hypotheses()
    if not active:
        return "wilson_consult"

    if not whiteboard.environmental_findings and iteration >= 2:
        return "environmental"

    return "testing"


def create_diagnostic_graph() -> StateGraph:
    """Create the full differential diagnosis StateGraph.

    Graph topology::

        START → intake → differential → provocation ──┐
                                  ▲                    │
                                  │            ┌───────┤
                                  │            ▼       ▼
                          wilson_consult   testing  environmental
                                  │            │       │
                                  └────────────┘       │
                                  ▲                    │
                                  └────────────────────┘
                                         provocation → resolution → END
    """
    workflow = StateGraph(DiagnosticState)

    workflow.add_node("intake", intake_node)
    workflow.add_node("differential", differential_node)
    workflow.add_node("provocation", provocation_node)
    workflow.add_node("testing", testing_node)
    workflow.add_node("environmental", environmental_node)
    workflow.add_node("wilson_consult", wilson_consult_node)
    workflow.add_node("resolution", resolution_node)

    workflow.add_edge(START, "intake")
    workflow.add_edge("intake", "differential")
    workflow.add_edge("differential", "provocation")
    workflow.add_conditional_edges(
        "provocation",
        route_after_provocation,
        {
            "testing": "testing",
            "environmental": "environmental",
            "wilson_consult": "wilson_consult",
            "resolution": "resolution",
        },
    )
    workflow.add_edge("testing", "provocation")
    workflow.add_edge("environmental", "provocation")
    workflow.add_edge("wilson_consult", "differential")
    workflow.add_edge("resolution", END)

    return workflow
