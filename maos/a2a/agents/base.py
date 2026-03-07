"""Base class for external A2A agent servers.

External agents run as standalone A2A-compliant servers that can be
discovered and called by the supervisor via the A2A protocol.
"""

import asyncio
import socket
from abc import abstractmethod
from typing import Any

import structlog
from fastapi import FastAPI, Request

from maos.agents.executor import AgentInput, AgentOutput, BaseAgentExecutor

logger = structlog.get_logger()


def find_free_port() -> int:
    """Find a free port on the system."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(s.getsockname()[1])


class ExternalAgentServer(BaseAgentExecutor):
    """Base class for external A2A agent servers.

    This class combines the AgentExecutor interface with A2A server
    functionality, allowing agents to:
    1. Be called directly via the execute() method (for testing/local use)
    2. Be exposed as an A2A-compliant HTTP server (for distributed use)

    Subclasses must implement:
    - _process(task: str, context: dict) -> str: The actual agent logic
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        host: str = "127.0.0.1",
        port: int | None = None,
        skills: list[dict[str, str]] | None = None,
    ):
        """
        Initialize the external agent server.

        Args:
            name: Agent name (used in A2A card).
            description: Agent description.
            host: Host to bind to.
            port: Port to listen on (None = find free port).
            skills: List of skill definitions for A2A card.
        """
        super().__init__(name, description)
        self._host = host
        self._port = port or find_free_port()
        self._skills = skills or []
        self._app: FastAPI | None = None
        self._server: Any | None = None
        self._server_task: asyncio.Task | None = None
        self._running = False

    @property
    def port(self) -> int:
        """Get the port this server is running on."""
        return self._port

    @property
    def endpoint(self) -> str:
        """Get the A2A endpoint URL."""
        return f"http://{self._host}:{self._port}/"

    @property
    def agent_card_url(self) -> str:
        """Get the agent card URL."""
        return f"http://{self._host}:{self._port}/.well-known/agent.json"

    @abstractmethod
    async def _process(self, task: str, context: dict[str, Any] | None = None) -> str:
        """
        Process a task and return the result.

        This is the core logic that subclasses must implement.

        Args:
            task: The task/message to process.
            context: Optional context (e.g., conversation history).

        Returns:
            The response string.
        """
        pass

    async def execute(self, input: AgentInput) -> AgentOutput:
        """Execute the agent with the given input."""
        try:
            result = await self._process(input.task, input.context)
            return AgentOutput(content=result, success=True)
        except Exception as e:
            logger.error("agent_execution_failed", agent=self.name, error=str(e))
            return AgentOutput(content="", success=False, error=str(e))

    def _create_app(self) -> FastAPI:
        """Create the FastAPI application."""
        app = FastAPI(title=f"A2A Agent: {self.name}")

        @app.get("/.well-known/agent.json")
        async def get_agent_card() -> dict[str, Any]:
            """Return the A2A agent card."""
            return self._get_agent_card()

        @app.post("/")
        async def handle_request(request: Request) -> dict[str, Any]:
            """Handle A2A request."""
            body = await request.json()
            return await self._handle_a2a_request(body)

        return app

    def _get_agent_card(self) -> dict[str, Any]:
        """Generate the A2A agent card."""
        return {
            "protocolVersion": "1.0",
            "name": self.name,
            "description": self.description,
            "version": "1.0.0",
            "supportedInterfaces": [{"url": self.endpoint, "protocolBinding": "JSONRPC"}],
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
                "stateTransitionHistory": False,
            },
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
            "skills": self._skills,
        }

    async def _handle_a2a_request(self, request: dict) -> dict:
        """Handle an A2A JSON-RPC request."""
        request_id = request.get("id", "unknown")
        method = request.get("method", "")

        if method == "message/send":
            try:
                params = request.get("params", {})
                message = params.get("message", {})
                parts = message.get("parts", [])

                # Extract text content
                text_content = ""
                for part in parts:
                    if part.get("type") == "text":
                        text_content += part.get("text", "")

                # Process the request
                result = await self._process(text_content, {"raw_request": request})

                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "task": {
                            "id": f"task-{request_id}",
                            "status": "COMPLETED",
                            "result": {
                                "role": "agent",
                                "parts": [{"type": "text", "text": str(result)}],
                            },
                        }
                    },
                }

            except Exception as e:
                logger.error("a2a_handler_error", agent=self.name, error=str(e))
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "task": {
                            "id": f"task-{request_id}",
                            "status": "FAILED",
                            "error": "Internal processing error",
                        }
                    },
                }

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    async def start(self) -> None:
        """Start the A2A server."""
        if self._running:
            return

        import uvicorn

        self._app = self._create_app()
        config = uvicorn.Config(
            self._app,
            host=self._host,
            port=self._port,
            log_level="warning",
        )
        server = uvicorn.Server(config)

        self._running = True
        logger.info("starting_external_agent", name=self.name, endpoint=self.endpoint)

        await server.serve()

    async def start_background(self) -> None:
        """Start the server in the background."""
        if self._running:
            return

        import uvicorn

        self._app = self._create_app()
        config = uvicorn.Config(
            self._app,
            host=self._host,
            port=self._port,
            log_level="warning",
        )
        self._server = uvicorn.Server(config)

        self._server_task = asyncio.create_task(self._server.serve())
        self._running = True

        # Wait briefly for server to start
        await asyncio.sleep(0.1)

        logger.info("started_external_agent_background", name=self.name, endpoint=self.endpoint)

    async def stop(self) -> None:
        """Gracefully stop the A2A server.

        Signals uvicorn to exit via should_exit flag, allowing the ASGI lifespan
        protocol to complete its shutdown handshake before the event loop closes.
        Falls back to task cancellation if graceful shutdown times out.
        """
        if self._server_task and not self._server_task.done():
            # Signal uvicorn to exit gracefully — this lets the lifespan
            # receive queue drain properly instead of dying mid-protocol.
            if self._server:
                self._server.should_exit = True

            try:
                await asyncio.wait_for(self._server_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("graceful_shutdown_timeout", name=self.name)
                self._server_task.cancel()
                try:
                    await self._server_task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                pass

        self._server = None
        self._running = False
        logger.info("stopped_external_agent", name=self.name)

    @property
    def app(self) -> FastAPI | None:
        """Get the FastAPI app (for testing)."""
        if self._app is None:
            self._app = self._create_app()
        return self._app
