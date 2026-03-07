"""A2A host server for multiple agents."""

from collections.abc import Callable
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = structlog.get_logger()


class A2AHostServer:
    """Multi-agent A2A host server."""

    def __init__(self, host: str = "0.0.0.0", port: int = 9001):
        """
        Initialize the host server.

        Args:
            host: Host to bind to.
            port: Port to listen on.
        """
        self._host = host
        self._port = port
        self._agents: dict[str, A2AAgentHandler] = {}
        self._app = FastAPI(title="A2A Host")

        self._setup_routes()

    def _setup_routes(self) -> None:
        """Set up API routes."""

        @self._app.get("/a2a/index.json")
        async def get_host_index():
            """Return host index listing all agents."""
            return self.get_index()

        @self._app.get("/a2a/{name}/.well-known/agent.json")
        async def get_agent_card(name: str):
            """Return agent card for specific agent."""
            if name not in self._agents:
                return JSONResponse(status_code=404, content={"error": f"Agent '{name}' not found"})
            return self._agents[name].get_card()

        @self._app.post("/a2a/{name}")
        async def handle_agent_request(name: str, request: Request):
            """Handle A2A request for specific agent."""
            if name not in self._agents:
                return JSONResponse(status_code=404, content={"error": f"Agent '{name}' not found"})

            body = await request.json()
            response = await self._agents[name].handle_request(body)
            return response

    def register_agent(self, name: str, handler: "A2AAgentHandler") -> None:
        """
        Register an agent at /a2a/{name}/.

        Args:
            name: Agent name.
            handler: Handler for the agent.
        """
        self._agents[name] = handler
        logger.info("registered_a2a_agent", name=name)

    def get_index(self) -> dict[str, Any]:
        """Get host index listing all agents."""
        return {
            "version": "1.0",
            "host": {"name": "MAOS A2A Host", "base_url": f"http://{self._host}:{self._port}"},
            "agents": [
                {
                    "name": name,
                    "path": f"/a2a/{name}",
                    "agent_card_path": f"/a2a/{name}/.well-known/agent.json",
                    "description": handler.get_description(),
                }
                for name, handler in self._agents.items()
            ],
        }

    async def start(self) -> None:
        """Start the server."""
        import uvicorn

        config = uvicorn.Config(self._app, host=self._host, port=self._port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

    @property
    def app(self) -> FastAPI:
        """Get the FastAPI app for testing."""
        return self._app


class A2AAgentHandler:
    """Handler for a single A2A agent."""

    def __init__(self, name: str, description: str, handler_fn: Callable[[dict], Any]):
        """
        Initialize the agent handler.

        Args:
            name: Agent name.
            description: Agent description.
            handler_fn: Function to handle requests.
        """
        self._name = name
        self._description = description
        self._handler_fn = handler_fn
        self._skills = []

    def add_skill(self, skill_id: str, name: str, description: str = "") -> None:
        """Add a skill to the agent."""
        self._skills.append({"id": skill_id, "name": name, "description": description})

    def get_card(self) -> dict[str, Any]:
        """Get the agent card."""
        return {
            "protocolVersion": "1.0",
            "name": self._name,
            "description": self._description,
            "version": "1.0.0",
            "supportedInterfaces": [{"url": f"/a2a/{self._name}", "protocolBinding": "JSONRPC"}],
            "capabilities": {"streaming": False, "pushNotifications": False},
            "skills": self._skills,
        }

    def get_description(self) -> str:
        """Get agent description."""
        return self._description

    async def handle_request(self, request: dict) -> dict:
        """Handle an A2A request."""
        return await self._handler_fn(request)
