"""Built-in external A2A agents.

This module provides built-in agent implementations that can be run
as external A2A services within the MAOS system.
"""

from maos.a2a.agents.title_generator import TitleGeneratorAgent
from maos.a2a.agents.base import ExternalAgentServer

__all__ = [
    "TitleGeneratorAgent",
    "ExternalAgentServer",
]

# Registry of built-in agent implementations
BUILTIN_AGENTS = {
    "title_generator": TitleGeneratorAgent,
}


def get_builtin_agent(name: str):
    """Get a built-in agent class by name."""
    return BUILTIN_AGENTS.get(name)
