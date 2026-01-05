"""FastAPI server factory for MAOS."""

from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, Optional

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from maos.config.models import Config, ServingConfig
from maos.api.routes import health, agents, chat, openai_compat, tasks

logger = structlog.get_logger()


class AppContext:
    """
    Application context holding all registries and the compiled graph.

    This is used for dependency injection into route handlers.
    """

    def __init__(self):
        self.config: Optional[Config] = None
        self.llm_registry = None
        self.mcp_registry = None
        self.tool_registry = None
        self.skill_registry = None
        self.skillset_registry = None
        self.agent_registry = None
        self.graph = None
        self.checkpointer = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for route handlers."""
        return {
            "config": self.config,
            "llm_registry": self.llm_registry,
            "mcp_registry": self.mcp_registry,
            "tool_registry": self.tool_registry,
            "skill_registry": self.skill_registry,
            "skillset_registry": self.skillset_registry,
            "agent_registry": self.agent_registry,
            "graph": self.graph,
            "checkpointer": self.checkpointer
        }


# Global context instance
_app_context = AppContext()


def get_app_context() -> Dict[str, Any]:
    """Dependency for getting app context in routes."""
    return _app_context.to_dict()


def create_app(
    config: Optional[Config] = None,
    serving_config: Optional[ServingConfig] = None,
    lifespan: Optional[Callable] = None
) -> FastAPI:
    """
    Create the FastAPI application.

    Args:
        config: Full MAOS configuration.
        serving_config: Server-specific configuration.
        lifespan: Optional lifespan context manager.

    Returns:
        Configured FastAPI application.
    """
    serving = serving_config or (config.serving if config else ServingConfig())

    # Create app with optional lifespan
    app = FastAPI(
        title="MAOS - Multi-Agent Orchestration System",
        description="Config-driven multi-agent orchestration with LangGraph, MCP, and A2A",
        version="0.1.0",
        lifespan=lifespan
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=serving.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Override dependency in all routers
    def override_context():
        return get_app_context()

    # Include routers with dependency override
    app.include_router(health.router)
    app.include_router(agents.router)
    app.include_router(chat.router)
    app.include_router(openai_compat.router)
    app.include_router(tasks.router)

    # Override dependencies
    app.dependency_overrides[health.get_app_context] = override_context
    app.dependency_overrides[agents.get_app_context] = override_context
    app.dependency_overrides[chat.get_app_context] = override_context
    app.dependency_overrides[openai_compat.get_app_context] = override_context
    app.dependency_overrides[tasks.get_app_context] = override_context

    # Store config in context
    if config:
        _app_context.config = config

    logger.info(
        "fastapi_app_created",
        cors_origins=serving.api.cors_origins,
        host=serving.api.host,
        port=serving.api.port
    )

    return app


def set_app_context(
    llm_registry=None,
    mcp_registry=None,
    tool_registry=None,
    skill_registry=None,
    skillset_registry=None,
    agent_registry=None,
    graph=None,
    checkpointer=None
) -> None:
    """
    Set the application context.

    Called during application startup to inject all registries
    and the compiled graph.
    """
    if llm_registry is not None:
        _app_context.llm_registry = llm_registry
    if mcp_registry is not None:
        _app_context.mcp_registry = mcp_registry
    if tool_registry is not None:
        _app_context.tool_registry = tool_registry
    if skill_registry is not None:
        _app_context.skill_registry = skill_registry
    if skillset_registry is not None:
        _app_context.skillset_registry = skillset_registry
    if agent_registry is not None:
        _app_context.agent_registry = agent_registry
    if graph is not None:
        _app_context.graph = graph
    if checkpointer is not None:
        _app_context.checkpointer = checkpointer

    logger.debug("app_context_updated")


def get_context() -> AppContext:
    """Get the global app context object."""
    return _app_context


@asynccontextmanager
async def default_lifespan(app: FastAPI):
    """
    Default lifespan manager.

    Logs startup and shutdown events.
    """
    logger.info("maos_starting")
    yield
    logger.info("maos_shutting_down")


async def run_server(
    app: FastAPI,
    host: str = "0.0.0.0",
    port: int = 7777
) -> None:
    """
    Run the server using uvicorn.

    Args:
        app: FastAPI application.
        host: Host to bind to.
        port: Port to listen on.
    """
    import uvicorn

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()
