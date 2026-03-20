"""Whiteboard — the shared diagnostic state visible to all team members.

Mirrors House MD's physical whiteboard where hypotheses are listed, ranked,
crossed out, and annotated during differential diagnosis sessions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class HypothesisStatus(Enum):
    """Status of a hypothesis on the whiteboard."""

    PROPOSED = "proposed"
    UNDER_TEST = "under_test"
    SUPPORTED = "supported"
    WEAKENED = "weakened"
    RULED_OUT = "ruled_out"
    CONFIRMED = "confirmed"


@dataclass
class WhiteboardEntry:
    """A single hypothesis on the whiteboard."""

    hypothesis: str
    proposer: str
    confidence: float = 0.5
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)
    challenges: list[dict[str, str]] = field(default_factory=list)
    tests_assigned: list[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def add_supporting_evidence(self, evidence: str) -> None:
        self.evidence_for.append(evidence)
        self.confidence = min(1.0, self.confidence + 0.1)

    def add_counter_evidence(self, evidence: str) -> None:
        self.evidence_against.append(evidence)
        self.confidence = max(0.0, self.confidence - 0.1)

    def add_challenge(self, challenger: str, challenge: str) -> None:
        self.challenges.append({"challenger": challenger, "challenge": challenge})

    def rule_out(self, reason: str) -> None:
        self.status = HypothesisStatus.RULED_OUT
        self.evidence_against.append(f"RULED OUT: {reason}")
        self.confidence = 0.0

    def confirm(self) -> None:
        self.status = HypothesisStatus.CONFIRMED
        self.confidence = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "hypothesis": self.hypothesis,
            "proposer": self.proposer,
            "confidence": self.confidence,
            "status": self.status.value,
            "evidence_for": self.evidence_for,
            "evidence_against": self.evidence_against,
            "challenges": self.challenges,
            "tests_assigned": self.tests_assigned,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WhiteboardEntry:
        return cls(
            hypothesis=data["hypothesis"],
            proposer=data["proposer"],
            confidence=data.get("confidence", 0.5),
            status=HypothesisStatus(data.get("status", "proposed")),
            evidence_for=data.get("evidence_for", []),
            evidence_against=data.get("evidence_against", []),
            challenges=data.get("challenges", []),
            tests_assigned=data.get("tests_assigned", []),
            created_at=data.get("created_at", ""),
            entry_id=data.get("entry_id", str(uuid.uuid4())[:8]),
        )


@dataclass
class Whiteboard:
    """Shared diagnostic whiteboard for the team.

    Tracks hypotheses, evidence, and the current diagnostic phase.
    Provides a structured view of the team's collective thinking.
    """

    entries: list[WhiteboardEntry] = field(default_factory=list)
    current_phase: str = "intake"
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symptoms: list[str] = field(default_factory=list)
    environmental_findings: list[str] = field(default_factory=list)
    iteration_count: int = 0

    def add_hypothesis(
        self,
        hypothesis: str,
        proposer: str,
        confidence: float = 0.5,
    ) -> WhiteboardEntry:
        """Add a new hypothesis to the whiteboard."""
        entry = WhiteboardEntry(
            hypothesis=hypothesis,
            proposer=proposer,
            confidence=confidence,
        )
        self.entries.append(entry)
        return entry

    def get_active_hypotheses(self) -> list[WhiteboardEntry]:
        """Return hypotheses not yet ruled out."""
        return [
            e for e in self.entries
            if e.status != HypothesisStatus.RULED_OUT
        ]

    def get_top_hypothesis(self) -> WhiteboardEntry | None:
        """Return the highest-confidence active hypothesis."""
        active = self.get_active_hypotheses()
        if not active:
            return None
        return max(active, key=lambda e: e.confidence)

    def get_confirmed(self) -> WhiteboardEntry | None:
        """Return the confirmed hypothesis, if any."""
        for entry in self.entries:
            if entry.status == HypothesisStatus.CONFIRMED:
                return entry
        return None

    def rule_out(self, entry_id: str, reason: str) -> bool:
        """Rule out a hypothesis by ID."""
        for entry in self.entries:
            if entry.entry_id == entry_id:
                entry.rule_out(reason)
                return True
        return False

    def advance_phase(self, new_phase: str, iteration: int | None = None) -> None:
        """Advance to the next diagnostic phase.

        Args:
            new_phase: The new phase name.
            iteration: If provided, sync whiteboard iteration to the graph's
                       iteration counter (prevents counter drift).
        """
        self.current_phase = new_phase
        if iteration is not None:
            self.iteration_count = iteration
        else:
            self.iteration_count += 1

    def add_symptom(self, symptom: str) -> None:
        """Record a new symptom/observation."""
        if symptom not in self.symptoms:
            self.symptoms.append(symptom)

    def add_environmental_finding(self, finding: str) -> None:
        """Record an environmental finding ('breaking into their house')."""
        if finding not in self.environmental_findings:
            self.environmental_findings.append(finding)

    def summary(self) -> str:
        """Generate a human-readable whiteboard summary."""
        lines = [
            f"=== DIAGNOSTIC WHITEBOARD (Phase: {self.current_phase}, "
            f"Iteration: {self.iteration_count}) ===",
        ]
        if self.symptoms:
            lines.append(f"\nSymptoms: {', '.join(self.symptoms)}")
        if self.environmental_findings:
            lines.append(
                f"Environmental: {', '.join(self.environmental_findings)}"
            )

        active = self.get_active_hypotheses()
        ruled_out = [
            e for e in self.entries
            if e.status == HypothesisStatus.RULED_OUT
        ]

        if active:
            lines.append("\nActive Hypotheses:")
            for e in sorted(active, key=lambda x: x.confidence, reverse=True):
                lines.append(
                    f"  [{e.confidence:.0%}] {e.hypothesis} "
                    f"(by {e.proposer}, {e.status.value})"
                )
                if e.evidence_for:
                    lines.append(f"    + {', '.join(e.evidence_for)}")
                if e.evidence_against:
                    lines.append(f"    - {', '.join(e.evidence_against)}")

        if ruled_out:
            lines.append("\nRuled Out:")
            for e in ruled_out:
                lines.append(f"  [X] {e.hypothesis}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "current_phase": self.current_phase,
            "iteration_count": self.iteration_count,
            "symptoms": self.symptoms,
            "environmental_findings": self.environmental_findings,
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Whiteboard:
        return cls(
            session_id=data.get("session_id", str(uuid.uuid4())),
            current_phase=data.get("current_phase", "intake"),
            iteration_count=data.get("iteration_count", 0),
            symptoms=data.get("symptoms", []),
            environmental_findings=data.get("environmental_findings", []),
            entries=[
                WhiteboardEntry.from_dict(e) for e in data.get("entries", [])
            ],
        )
