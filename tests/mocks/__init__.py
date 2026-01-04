"""MAOS Test Mocks."""

from tests.mocks.a2a import MockA2AAgent, MockA2AHost
from tests.mocks.llm import MockLLMAdapter
from tests.mocks.mcp import MockMCPConnection, MockMCPServer

__all__ = [
    "MockLLMAdapter",
    "MockMCPServer",
    "MockMCPConnection",
    "MockA2AAgent",
    "MockA2AHost",
]
