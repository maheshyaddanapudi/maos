"""A2A individual agent server."""

from typing import Any, Callable, Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import structlog

logger = structlog.get_logger()


class A2AIndividualServer:
    """Single-agent A2A server."""

    def __init__(
        self,
        name: str,
        description: str,
        handler_fn: Callable[[Dict], Any],
        host: str = "0.0.0.0",
        port: int = 9010,
        skills: List[Dict[str, str]] = None
    ):
        """
        Initialize the individual agent server.

        Args:
            name: Agent name.
            description: Agent description.
            handler_fn: Function to handle requests.
            host: Host to bind to.
            port: Port to listen on.
            skills: List of skill definitions.
        """
        self._name = name
        self._description = description
        self._handler_fn = handler_fn
        self._host = host
        self._port = port
        self._skills = skills or []
        self._app = FastAPI(title=f"A2A Agent: {name}")

        self._setup_routes()

    def _setup_routes(self) -> None:
        """Set up API routes."""

        @self._app.get("/.well-known/agent.json")
        async def get_agent_card():
            """Return agent card."""
            return self._get_card()

        @self._app.post("/")
        async def handle_request(request: Request):
            """Handle A2A request."""
            body = await request.json()
            return await self._handle_request(body)

    def _get_card(self) -> Dict[str, Any]:
        """Get the agent card."""
        return {
            "protocolVersion": "1.0",
            "name": self._name,
            "description": self._description,
            "version": "1.0.0",
            "supportedInterfaces": [
                {
                    "url": f"http://{self._host}:{self._port}/",
                    "protocolBinding": "JSONRPC"
                }
            ],
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
                "stateTransitionHistory": False
            },
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
            "skills": self._skills
        }

    async def _handle_request(self, request: Dict) -> Dict:
        """Handle an A2A request."""
        request_id = request.get("id", "unknown")
        method = request.get("method", "")

        if method == "message/send":
            try:
                # Extract message
                params = request.get("params", {})
                message = params.get("message", {})
                parts = message.get("parts", [])
                text_content = ""
                for part in parts:
                    if part.get("type") == "text":
                        text_content += part.get("text", "")

                # Process with handler
                result = await self._handler_fn({"text": text_content, "raw": request})

                # Format response
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "task": {
                            "id": f"task-{request_id}",
                            "status": "COMPLETED",
                            "result": {
                                "role": "agent",
                                "parts": [
                                    {"type": "text", "text": str(result)}
                                ]
                            }
                        }
                    }
                }

            except Exception as e:
                logger.error("a2a_handler_error", error=str(e))
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "task": {
                            "id": f"task-{request_id}",
                            "status": "FAILED",
                            "error": str(e)
                        }
                    }
                }

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }

    async def start(self) -> None:
        """Start the server."""
        import uvicorn
        config = uvicorn.Config(
            self._app,
            host=self._host,
            port=self._port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()

    @property
    def app(self) -> FastAPI:
        """Get the FastAPI app for testing."""
        return self._app
