"""
MAOS MCP Transport Base.

Protocol definition for MCP transports.
"""

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MCPTransport(Protocol):
    """Protocol for MCP transport implementations."""

    async def connect(self) -> None:
        """Establish connection."""
        ...

    async def send(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send message and receive response."""
        ...

    async def disconnect(self) -> None:
        """Close connection."""
        ...

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        ...


class BaseMCPTransport(ABC):
    """Base class for MCP transport implementations."""

    def __init__(self, timeout: float = 30.0):
        self._timeout = timeout
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection."""
        pass

    @abstractmethod
    async def send(self, message: dict[str, Any]) -> dict[str, Any]:
        """Send message and receive response."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection."""
        pass
