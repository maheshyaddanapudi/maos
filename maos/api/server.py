"""FastAPI server factory for MAOS."""

import os
import traceback
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from maos.api.middleware.auth import AuthConfig, AuthMiddleware
from maos.api.middleware.rate_limiter import (
    RateLimitConfig,
    RateLimitMiddleware,
)
from maos.api.middleware.security_headers import (
    SecurityHeadersMiddleware,
)
from maos.api.routes import (
    agents,
    chat,
    conversations,
    health,
    langgraph_studio,
    openai_compat,
    tasks,
)
from maos.config.models import Config, ServingConfig

logger = structlog.get_logger()


class AppContext:
    """
    Application context holding all registries and the compiled graph.

    This is used for dependency injection into route handlers.
    """

    def __init__(self) -> None:
        self.config: Config | None = None
        self.llm_registry = None
        self.mcp_registry = None
        self.tool_registry = None
        self.skill_registry = None
        self.skillset_registry = None
        self.agent_registry = None
        self.graph = None
        self.checkpointer = None
        self.conversation_store = None

    def to_dict(self) -> dict[str, Any]:
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
            "checkpointer": self.checkpointer,
            "conversation_store": self.conversation_store,
        }


# Global context instance
_app_context = AppContext()


def get_app_context() -> dict[str, Any]:
    """Dependency for getting app context in routes."""
    return _app_context.to_dict()


def create_app(
    config: Config | None = None,
    serving_config: ServingConfig | None = None,
    lifespan: Callable | None = None,
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
        lifespan=lifespan,
    )

    # Add CORS middleware
    if "*" in serving.api.cors_origins:
        logger.warning(
            "cors_wildcard_origins",
            message="CORS allows all origins — restrict in production",
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=serving.api.cors_origins,
        allow_credentials="*" not in serving.api.cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Accept"],
    )

    # --- Security middleware ---
    # Security headers on every response
    app.add_middleware(SecurityHeadersMiddleware)

    # Rate limiting (per-client token bucket)
    security = serving.security
    rate_cfg = RateLimitConfig(
        enabled=security.rate_limit_enabled,
        requests_per_minute=security.rate_limit_rpm,
        burst_size=security.rate_limit_burst,
    )
    app.add_middleware(RateLimitMiddleware, config=rate_cfg)

    # Authentication (Bearer API keys)
    api_keys: list[str] = []
    if security.api_key_env:
        raw = os.environ.get(security.api_key_env, "")
        api_keys = [k.strip() for k in raw.split(",") if k.strip()]
    auth_cfg = AuthConfig(
        enabled=security.auth_enabled,
        api_keys=api_keys,
    )
    if auth_cfg.enabled and not api_keys:
        logger.warning(
            "auth_enabled_no_keys",
            message="Auth is enabled but no API keys configured — all requests will be rejected. "
            "Set the api_key_env config or disable auth.",
        )
    app.add_middleware(AuthMiddleware, auth_config=auth_cfg)

    # Request ID correlation
    from maos.api.middleware.request_id import (
        RequestIdMiddleware,
    )

    app.add_middleware(RequestIdMiddleware)

    # --- Global exception handler ---
    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Return standardised JSON for unhandled errors."""
        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": "http_error",
                    "message": exc.detail,
                },
            )
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            traceback=traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": ("An unexpected error occurred."),
            },
        )

    # Override dependency in all routers
    def override_context() -> dict[str, Any]:
        return get_app_context()

    # Include routers with dependency override
    app.include_router(health.router)
    app.include_router(agents.router)
    app.include_router(chat.router)
    app.include_router(openai_compat.router)
    app.include_router(tasks.router)
    app.include_router(langgraph_studio.router)
    app.include_router(conversations.router)

    # Override dependencies
    app.dependency_overrides[health.get_app_context] = override_context
    app.dependency_overrides[agents.get_app_context] = override_context
    app.dependency_overrides[chat.get_app_context] = override_context
    app.dependency_overrides[openai_compat.get_app_context] = override_context
    app.dependency_overrides[tasks.get_app_context] = override_context
    app.dependency_overrides[langgraph_studio.get_app_context] = override_context
    app.dependency_overrides[conversations.get_app_context] = override_context

    # Store config in context
    if config:
        _app_context.config = config

    logger.info(
        "fastapi_app_created",
        cors_origins=serving.api.cors_origins,
        host=serving.api.host,
        port=serving.api.port,
    )

    return app


def set_app_context(
    llm_registry: Any = None,
    mcp_registry: Any = None,
    tool_registry: Any = None,
    skill_registry: Any = None,
    skillset_registry: Any = None,
    agent_registry: Any = None,
    graph: Any = None,
    checkpointer: Any = None,
    conversation_store: Any = None,
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
    if conversation_store is not None:
        _app_context.conversation_store = conversation_store

    logger.debug("app_context_updated")


def get_context() -> AppContext:
    """Get the global app context object."""
    return _app_context


@asynccontextmanager
async def default_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Default lifespan manager.

    Logs startup and shutdown events.
    """
    logger.info("maos_starting")
    yield
    logger.info("maos_shutting_down")


async def run_server(app: FastAPI, host: str = "127.0.0.1", port: int = 7777) -> None:
    """
    Run the server using uvicorn.

    Args:
        app: FastAPI application.
        host: Host to bind to.
        port: Port to listen on.
    """
    import uvicorn

    config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()
