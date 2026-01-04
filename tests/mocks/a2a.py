"""
Mock A2A Agent and Host for Testing.
"""

from typing import Any


class MockA2AAgent:
    """Mock A2A agent for testing."""

    def __init__(
        self,
        name: str,
        skills: list[str] | None = None,
        description: str = "",
    ):
        self.name = name
        self.skills = skills or []
        self.description = description or f"Mock {name} agent"
        self._responses: dict[str, str] = {}
        self._calls: list[dict] = []

    def get_agent_card(self) -> dict[str, Any]:
        """Return Agent Card."""
        return {
            "protocolVersion": "1.0",
            "name": self.name,
            "description": self.description,
            "version": "1.0.0",
            "supportedInterfaces": [
                {"url": f"http://mock/{self.name}", "protocolBinding": "JSONRPC"}
            ],
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
            },
            "skills": [
                {"id": s, "name": s, "tags": ["mock"]}
                for s in self.skills
            ],
        }

    def set_response(self, response: str) -> None:
        """Set response for next call."""
        self._responses["default"] = response

    def set_response_for(self, pattern: str, response: str) -> None:
        """Set response for specific message pattern."""
        self._responses[pattern] = response

    async def handle_request(self, request: dict) -> dict:
        """Handle A2A request."""
        self._calls.append(request)

        # Find matching response
        message_text = ""
        params = request.get("params", {})
        if "message" in params:
            parts = params["message"].get("parts", [])
            for part in parts:
                if part.get("type") == "text":
                    message_text = part.get("text", "")
                    break

        # Check for pattern matches
        response_text = self._responses.get("default", f"Mock response from {self.name}")
        for pattern, resp in self._responses.items():
            if pattern != "default" and pattern in message_text:
                response_text = resp
                break

        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "task": {
                    "id": f"task-{request.get('id')}",
                    "status": "COMPLETED",
                    "result": {
                        "role": "agent",
                        "parts": [{"type": "text", "text": response_text}]
                    }
                }
            }
        }

    def get_calls(self) -> list[dict]:
        """Get recorded calls."""
        return self._calls


class MockA2AHost:
    """Mock A2A host with multiple agents."""

    def __init__(self, name: str = "Mock Host"):
        self.name = name
        self._agents: dict[str, MockA2AAgent] = {}

    def add_agent(self, agent: MockA2AAgent) -> None:
        """Add an agent to the host."""
        self._agents[agent.name] = agent

    def get_agent(self, name: str) -> MockA2AAgent | None:
        """Get agent by name."""
        return self._agents.get(name)

    def get_host_index(self) -> dict[str, Any]:
        """Return host index."""
        return {
            "version": "1.0",
            "host": {
                "name": self.name,
                "description": "Mock A2A host for testing",
            },
            "agents": [
                {
                    "name": name,
                    "path": f"/a2a/{name}",
                    "agent_card_path": f"/a2a/{name}/.well-known/agent.json",
                    "description": agent.description,
                    "tags": ["mock"],
                }
                for name, agent in self._agents.items()
            ]
        }

    def get_all_agent_cards(self) -> dict[str, dict]:
        """Get all agent cards."""
        return {
            name: agent.get_agent_card()
            for name, agent in self._agents.items()
        }
