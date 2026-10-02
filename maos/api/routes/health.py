"""Health check endpoint."""

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends

from maos.api.models import (
    ComponentHealth,
    HealthResponse,
    HealthStatus,
)

logger = structlog.get_logger()

router = APIRouter(tags=["health"])


def get_app_context() -> dict[str, Any]:
    """Get application context - to be overridden by dependency injection."""
    return {}


@router.get("/health", response_model=HealthResponse)
async def health_check(context: dict[str, Any] = Depends(get_app_context)) -> HealthResponse:
    """
    Check the health of the MAOS system.

    Returns health status of all components including:
    - LLM registries
    - MCP servers
    - Tool registries
    - Agent registries
    """
    components = []
    overall_status = HealthStatus.HEALTHY

    # Check LLM registry
    llm_registry = context.get("llm_registry")
    if llm_registry:
        llm_names = llm_registry.list() if hasattr(llm_registry, "list") else []
        components.append(
            ComponentHealth(
                name="llm_registry",
                status=HealthStatus.HEALTHY if llm_names else HealthStatus.DEGRADED,
                message=f"{len(llm_names)} LLM adapters registered",
                details={"adapters": llm_names},
            )
        )
        if not llm_names:
            overall_status = HealthStatus.DEGRADED

    # Check MCP registry
    mcp_registry = context.get("mcp_registry")
    if mcp_registry:
        try:
            server_names = (
                mcp_registry.list_servers() if hasattr(mcp_registry, "list_servers") else []
            )
            connected = [s for s in server_names if mcp_registry.is_connected(s)]
            components.append(
                ComponentHealth(
                    name="mcp_registry",
                    status=HealthStatus.HEALTHY
                    if len(connected) == len(server_names)
                    else HealthStatus.DEGRADED,
                    message=f"{len(connected)}/{len(server_names)} MCP servers connected",
                    details={"servers": server_names, "connected": connected},
                )
            )
            if len(connected) < len(server_names):
                overall_status = HealthStatus.DEGRADED
        except Exception as e:
            components.append(
                ComponentHealth(
                    name="mcp_registry",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Error checking MCP servers: {str(e)}",
                )
            )
            overall_status = HealthStatus.UNHEALTHY

    # Check Tool registry
    tool_registry = context.get("tool_registry")
    if tool_registry:
        tool_count = len(tool_registry.list()) if hasattr(tool_registry, "list") else 0
        components.append(
            ComponentHealth(
                name="tool_registry",
                status=HealthStatus.HEALTHY,
                message=f"{tool_count} tools available",
            )
        )

    # Check Agent registry
    agent_registry = context.get("agent_registry")
    if agent_registry:
        try:
            supervisor = (
                agent_registry.get_supervisor()
                if hasattr(agent_registry, "get_supervisor")
                else None
            )
            workers = (
                list(agent_registry.get_workers()) if hasattr(agent_registry, "get_workers") else []
            )
            roster = agent_registry.get_roster() if hasattr(agent_registry, "get_roster") else []

            has_supervisor = supervisor is not None
            components.append(
                ComponentHealth(
                    name="agent_registry",
                    status=HealthStatus.HEALTHY if has_supervisor else HealthStatus.DEGRADED,
                    message=f"Supervisor: {'yes' if has_supervisor else 'no'}, Workers: {len(workers)}",
                    details={"roster": roster, "has_supervisor": has_supervisor},
                )
            )
            if not has_supervisor:
                overall_status = HealthStatus.DEGRADED
        except Exception as e:
            components.append(
                ComponentHealth(
                    name="agent_registry",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Error checking agents: {str(e)}",
                )
            )
            overall_status = HealthStatus.UNHEALTHY

    # Check Graph
    graph = context.get("graph")
    if graph:
        components.append(
            ComponentHealth(
                name="graph", status=HealthStatus.HEALTHY, message="LangGraph compiled and ready"
            )
        )
    else:
        components.append(
            ComponentHealth(
                name="graph", status=HealthStatus.UNHEALTHY, message="LangGraph not compiled"
            )
        )
        overall_status = HealthStatus.UNHEALTHY

    return HealthResponse(status=overall_status, components=components, timestamp=datetime.now(UTC))


@router.get("/ready")
async def readiness_check(context: dict[str, Any] = Depends(get_app_context)) -> dict[str, Any]:
    """
    Quick readiness check for load balancers.

    Returns 200 if ready, 503 if not.
    """
    graph = context.get("graph")

    if graph is None:
        return {"ready": False, "reason": "Graph not initialized"}

    return {"ready": True}


@router.get("/live")
async def liveness_check() -> dict[str, Any]:
    """
    Quick liveness check.

    Always returns 200 if the server is responding.
    """
    return {"alive": True}
