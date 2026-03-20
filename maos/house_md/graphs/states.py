"""State definitions for the House MD diagnostic workflow."""

from __future__ import annotations

import operator
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


class DiagnosticState(TypedDict):
    """Shared state for the differential diagnosis workflow.

    Flows through all nodes in the diagnostic graph. Fields use LangGraph
    reducers where appropriate (add_messages for message merging,
    operator.add for hypothesis accumulation).
    """

    messages: Annotated[list, add_messages]
    symptoms: list[str]
    hypotheses: Annotated[list[dict[str, Any]], operator.add]
    evidence: dict[str, Any]
    current_phase: str
    agent_beliefs: dict[str, Any]
    whiteboard: dict[str, Any]
    final_diagnosis: str | None
    confidence: float
    iteration: int
    active_team: list[str]
