"""Base MCP transport protocol."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class MCPTransport(ABC):
    """Abstract base class for MCP transports."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the MCP server."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the MCP server."""
        pass

    @abstractmethod
    async def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a JSON-RPC message and get response.

        Args:
            message: JSON-RPC request message.

        Returns:
            JSON-RPC response message.
        """
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if transport is connected."""
        pass
