"""A2A integration module for MAOS."""

from maos.a2a.client import A2AClient
from maos.a2a.discovery import A2ADiscovery
from maos.a2a.models import (
    A2AMessage,
    A2ARequest,
    A2AResponse,
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    DiscoveredAgent,
    TaskStatus,
)

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
