"""A2A integration module for MAOS."""

from maos.a2a.models import (
    AgentCard,
    AgentSkill,
    AgentCapabilities,
    DiscoveredAgent,
    A2AMessage,
    A2ARequest,
    A2AResponse,
    TaskStatus,
)
from maos.a2a.discovery import A2ADiscovery
from maos.a2a.client import A2AClient

__all__ = [
    "AgentCard",
    "AgentSkill",
    "AgentCapabilities",
    "DiscoveredAgent",
    "A2AMessage",
    "A2ARequest",
    "A2AResponse",
    "TaskStatus",
    "A2ADiscovery",
    "A2AClient",
]
