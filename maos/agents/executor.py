"""Unified agent executor interface.

This module defines a common interface (Protocol) that both native workers
and external A2A agents implement, enabling a unified execution model.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, runtime_checkable


@dataclass
class AgentInput:
    """Input to an agent execution."""
    task: str
    context: Optional[Dict[str, Any]] = None
    thread_id: Optional[str] = None
    timeout_seconds: Optional[int] = None


@dataclass
class AgentOutput:
    """Output from an agent execution."""
    content: str
    success: bool = True
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


@runtime_checkable
class AgentExecutor(Protocol):
    """Protocol for agent execution.

    Both native workers and external A2A agents implement this interface,
    enabling unified execution regardless of agent type.
    """

    @property
    def name(self) -> str:
        """Get the agent name."""
        ...

    @property
    def description(self) -> str:
        """Get the agent description."""
        ...

    async def execute(self, input: AgentInput) -> AgentOutput:
        """
        Execute the agent with the given input.

        Args:
            input: Agent input containing task and context.

        Returns:
            Agent output with response content.
        """
        ...

    async def stream(self, input: AgentInput) -> AsyncIterator[str]:
        """
        Stream agent execution.

        Args:
            input: Agent input containing task and context.

        Yields:
            Response chunks.
        """
        ...


class BaseAgentExecutor(ABC):
    """Base class for agent executors with common functionality."""

    def __init__(self, name: str, description: str = ""):
        self._name = name
        self._description = description

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @abstractmethod
    async def execute(self, input: AgentInput) -> AgentOutput:
        """Execute the agent."""
        pass

    async def stream(self, input: AgentInput) -> AsyncIterator[str]:
        """Default stream implementation - execute and yield result."""
        result = await self.execute(input)
        yield result.content
