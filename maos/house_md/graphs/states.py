"""State definitions for the House MD diagnostic workflow."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class DiagnosticPhase(Enum):
    """Phases of the differential diagnosis protocol."""

    INTAKE = "intake"
    DIFFERENTIAL = "differential"
    PROVOCATION = "provocation"
    TESTING = "testing"
    ENVIRONMENTAL = "environmental"
    WILSON_CONSULT = "wilson_consult"
    RESOLUTION = "resolution"


def _merge_hypotheses(
    existing: list[dict[str, Any]],
    new: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge hypothesis lists, deduplicating by hypothesis text.

    Replaces ``operator.add`` to prevent unbounded growth (Issue 90).
    When a hypothesis with the same text already exists, the newer entry
    wins (higher confidence or updated evidence).
    """
    seen: dict[str, dict[str, Any]] = {}
    for h in existing:
        key = h.get("hypothesis", "").lower().strip()
        if key:
            seen[key] = h
    for h in new:
        key = h.get("hypothesis", "").lower().strip()
        if key:
            existing_h = seen.get(key)
            if existing_h is None:
                seen[key] = h
            else:
                # Keep whichever has higher confidence
                if h.get("confidence", 0) > existing_h.get("confidence", 0):
                    seen[key] = h
    return list(seen.values())


class DiagnosticState(TypedDict):
    """Shared state for the differential diagnosis workflow.

    Flows through all nodes in the diagnostic graph. Fields use LangGraph
    reducers where appropriate (add_messages for message merging,
    _merge_hypotheses for deduplicating hypothesis accumulation).
    """

    messages: Annotated[list, add_messages]
    symptoms: list[str]
    hypotheses: Annotated[list[dict[str, Any]], _merge_hypotheses]
    evidence: dict[str, Any]
    current_phase: str
    agent_beliefs: dict[str, Any]
    whiteboard: dict[str, Any]
    final_diagnosis: str | None
    confidence: float
    iteration: int
    active_team: list[str]
