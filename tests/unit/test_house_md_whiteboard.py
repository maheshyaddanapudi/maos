"""Tests for House MD whiteboard (shared diagnostic state)."""


from maos.house_md.memory.whiteboard import (
    HypothesisStatus,
    Whiteboard,
    WhiteboardEntry,
)

# ── WhiteboardEntry ──────────────────────────────────────────────────────────


class TestWhiteboardEntry:
    def test_create_default(self):
        entry = WhiteboardEntry(hypothesis="Memory leak", proposer="foreman")
        assert entry.hypothesis == "Memory leak"
        assert entry.proposer == "foreman"
        assert entry.confidence == 0.5
        assert entry.status == HypothesisStatus.PROPOSED
        assert entry.evidence_for == []
        assert entry.evidence_against == []
        assert entry.challenges == []
        assert len(entry.entry_id) == 8

    def test_add_supporting_evidence(self):
        entry = WhiteboardEntry(hypothesis="Bug", proposer="chase")
        entry.add_supporting_evidence("Stack trace matches")
        assert len(entry.evidence_for) == 1
        assert entry.confidence == 0.65

    def test_add_supporting_evidence_caps_at_1(self):
        entry = WhiteboardEntry(
            hypothesis="Bug", proposer="chase", confidence=0.95
        )
        entry.add_supporting_evidence("More evidence")
        assert entry.confidence == 1.0

    def test_add_counter_evidence(self):
        entry = WhiteboardEntry(hypothesis="Bug", proposer="chase")
        entry.add_counter_evidence("Tests pass")
        assert len(entry.evidence_against) == 1
        assert entry.confidence == 0.35

    def test_add_counter_evidence_floors_at_0(self):
        entry = WhiteboardEntry(
            hypothesis="Bug", proposer="chase", confidence=0.05
        )
        entry.add_counter_evidence("Disproved")
        assert entry.confidence == 0.0

    def test_add_challenge(self):
        entry = WhiteboardEntry(hypothesis="Design flaw", proposer="chase")
        entry.add_challenge("foreman", "No evidence for this")
        assert len(entry.challenges) == 1
        assert entry.challenges[0]["challenger"] == "foreman"

    def test_rule_out(self):
        entry = WhiteboardEntry(hypothesis="Wrong path", proposer="cameron")
        entry.rule_out("Tests disproved it")
        assert entry.status == HypothesisStatus.RULED_OUT
        assert entry.confidence == 0.0
        assert "RULED OUT" in entry.evidence_against[-1]

    def test_confirm(self):
        entry = WhiteboardEntry(hypothesis="Root cause", proposer="house")
        entry.confirm()
        assert entry.status == HypothesisStatus.CONFIRMED
        assert entry.confidence == 1.0

    def test_to_dict(self):
        entry = WhiteboardEntry(hypothesis="Test", proposer="house")
        d = entry.to_dict()
        assert d["hypothesis"] == "Test"
        assert d["proposer"] == "house"
        assert d["status"] == "proposed"
        assert "entry_id" in d

    def test_from_dict(self):
        data = {
            "hypothesis": "Memory leak",
            "proposer": "foreman",
            "confidence": 0.8,
            "status": "under_test",
            "evidence_for": ["heap dump shows growth"],
            "evidence_against": [],
            "challenges": [],
            "tests_assigned": ["heap_analysis"],
            "created_at": "2024-01-01T00:00:00",
            "entry_id": "abc12345",
        }
        entry = WhiteboardEntry.from_dict(data)
        assert entry.hypothesis == "Memory leak"
        assert entry.confidence == 0.8
        assert entry.status == HypothesisStatus.UNDER_TEST
        assert entry.entry_id == "abc12345"

    def test_roundtrip(self):
        entry = WhiteboardEntry(hypothesis="Test", proposer="chase")
        entry.add_supporting_evidence("Evidence 1")
        entry.add_challenge("foreman", "Challenge")
        restored = WhiteboardEntry.from_dict(entry.to_dict())
        assert restored.hypothesis == entry.hypothesis
        assert restored.evidence_for == entry.evidence_for
        assert restored.challenges == entry.challenges


# ── Whiteboard ────────────────────────────────────────────────────────────────


class TestWhiteboard:
    def test_create_default(self):
        wb = Whiteboard()
        assert wb.entries == []
        assert wb.current_phase == "intake"
        assert wb.iteration_count == 0
        assert wb.symptoms == []

    def test_add_hypothesis(self):
        wb = Whiteboard()
        entry = wb.add_hypothesis("Memory leak", "foreman", confidence=0.7)
        assert len(wb.entries) == 1
        assert entry.hypothesis == "Memory leak"
        assert entry.confidence == 0.7

    def test_get_active_hypotheses(self):
        wb = Whiteboard()
        wb.add_hypothesis("A", "chase")
        wb.add_hypothesis("B", "foreman")
        wb.add_hypothesis("C", "cameron")
        wb.entries[1].rule_out("Disproved")
        active = wb.get_active_hypotheses()
        assert len(active) == 2
        assert all(e.status != HypothesisStatus.RULED_OUT for e in active)

    def test_get_top_hypothesis(self):
        wb = Whiteboard()
        wb.add_hypothesis("Low", "chase", confidence=0.3)
        wb.add_hypothesis("High", "foreman", confidence=0.9)
        wb.add_hypothesis("Mid", "cameron", confidence=0.6)
        top = wb.get_top_hypothesis()
        assert top is not None
        assert top.hypothesis == "High"

    def test_get_top_hypothesis_empty(self):
        wb = Whiteboard()
        assert wb.get_top_hypothesis() is None

    def test_get_top_hypothesis_excludes_ruled_out(self):
        wb = Whiteboard()
        entry = wb.add_hypothesis("High", "house", confidence=0.9)
        entry.rule_out("Wrong")
        wb.add_hypothesis("Low", "chase", confidence=0.3)
        top = wb.get_top_hypothesis()
        assert top is not None
        assert top.hypothesis == "Low"

    def test_get_confirmed(self):
        wb = Whiteboard()
        wb.add_hypothesis("A", "chase")
        entry = wb.add_hypothesis("B", "house")
        entry.confirm()
        confirmed = wb.get_confirmed()
        assert confirmed is not None
        assert confirmed.hypothesis == "B"

    def test_get_confirmed_none(self):
        wb = Whiteboard()
        wb.add_hypothesis("A", "chase")
        assert wb.get_confirmed() is None

    def test_rule_out_by_id(self):
        wb = Whiteboard()
        entry = wb.add_hypothesis("Test", "chase")
        result = wb.rule_out(entry.entry_id, "Disproved")
        assert result is True
        assert entry.status == HypothesisStatus.RULED_OUT

    def test_rule_out_nonexistent(self):
        wb = Whiteboard()
        result = wb.rule_out("nonexistent", "Reason")
        assert result is False

    def test_advance_phase(self):
        wb = Whiteboard()
        assert wb.current_phase == "intake"
        assert wb.iteration_count == 0
        wb.advance_phase("differential")
        assert wb.current_phase == "differential"
        assert wb.iteration_count == 1

    def test_add_symptom(self):
        wb = Whiteboard()
        wb.add_symptom("NullPointerException in line 42")
        wb.add_symptom("Slow response times")
        wb.add_symptom("NullPointerException in line 42")  # Duplicate
        assert len(wb.symptoms) == 2

    def test_add_environmental_finding(self):
        wb = Whiteboard()
        wb.add_environmental_finding("Recent deployment changed DB version")
        wb.add_environmental_finding("Recent deployment changed DB version")
        assert len(wb.environmental_findings) == 1

    def test_summary_empty(self):
        wb = Whiteboard()
        summary = wb.summary()
        assert "DIAGNOSTIC WHITEBOARD" in summary
        assert "Phase: intake" in summary

    def test_summary_with_content(self):
        wb = Whiteboard()
        wb.add_symptom("Error 500")
        wb.add_hypothesis("DB timeout", "foreman", confidence=0.7)
        wb.add_hypothesis("Memory leak", "chase", confidence=0.4)
        entry = wb.add_hypothesis("Wrong config", "cameron", confidence=0.2)
        entry.rule_out("Config verified correct")
        summary = wb.summary()
        assert "Error 500" in summary
        assert "DB timeout" in summary
        assert "70%" in summary
        assert "Ruled Out" in summary
        assert "Wrong config" in summary

    def test_summary_with_evidence(self):
        wb = Whiteboard()
        entry = wb.add_hypothesis("Bug", "house")
        entry.add_supporting_evidence("Stack trace")
        entry.add_counter_evidence("Tests pass")
        summary = wb.summary()
        assert "Stack trace" in summary
        assert "Tests pass" in summary

    def test_to_dict(self):
        wb = Whiteboard()
        wb.add_symptom("Error")
        wb.add_hypothesis("Bug", "house")
        d = wb.to_dict()
        assert d["current_phase"] == "intake"
        assert len(d["entries"]) == 1
        assert d["symptoms"] == ["Error"]

    def test_from_dict(self):
        data = {
            "session_id": "test-session",
            "current_phase": "differential",
            "iteration_count": 3,
            "symptoms": ["Error 500", "Slow queries"],
            "environmental_findings": ["DB upgraded"],
            "entries": [
                {
                    "hypothesis": "DB issue",
                    "proposer": "foreman",
                    "confidence": 0.8,
                    "status": "supported",
                    "evidence_for": ["Query logs"],
                    "evidence_against": [],
                    "challenges": [],
                    "tests_assigned": [],
                    "created_at": "2024-01-01",
                    "entry_id": "test123",
                }
            ],
        }
        wb = Whiteboard.from_dict(data)
        assert wb.session_id == "test-session"
        assert wb.current_phase == "differential"
        assert wb.iteration_count == 3
        assert len(wb.entries) == 1
        assert wb.entries[0].confidence == 0.8

    def test_roundtrip(self):
        wb = Whiteboard()
        wb.add_symptom("Error")
        wb.add_environmental_finding("Finding")
        wb.add_hypothesis("Bug", "house", confidence=0.7)
        wb.advance_phase("testing")
        restored = Whiteboard.from_dict(wb.to_dict())
        assert restored.current_phase == wb.current_phase
        assert restored.symptoms == wb.symptoms
        assert len(restored.entries) == len(wb.entries)
        assert restored.entries[0].confidence == wb.entries[0].confidence
