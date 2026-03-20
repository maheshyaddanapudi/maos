"""House MD-inspired multi-agent diagnostic system.

Implements a diagnostic team approach to software development using
character-based agent personalities mapped to the House MD methodology.
"""

from maos.house_md.graphs.states import DiagnosticState
from maos.house_md.memory.whiteboard import Whiteboard, WhiteboardEntry
from maos.house_md.personalities.base import (
    CognitiveBias,
    PersonalityConfig,
    PersonalityWrapper,
)
from maos.house_md.personalities.team import PERSONALITY_CONFIGS, TeamActivation

__all__ = [
    "CognitiveBias",
    "PersonalityConfig",
    "PersonalityWrapper",
    "PERSONALITY_CONFIGS",
    "TeamActivation",
    "Whiteboard",
    "WhiteboardEntry",
    "DiagnosticState",
]
