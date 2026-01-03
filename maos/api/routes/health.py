"""
MAOS Health Routes.

Health check endpoints.
"""

import time

from fastapi import APIRouter

import maos
from maos.api.models import ComponentHealth, HealthResponse

router = APIRouter(tags=["health"])

_start_time = time.time()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check system health status."""
    from maos.api.server import _app_state

    uptime = int(time.time() - _start_time)
    components = {}
    overall_status = "healthy"

    # Check graph
    if _app_state.get("graph"):
        components["graph"] = ComponentHealth(status="healthy")
    else:
        components["graph"] = ComponentHealth(status="unhealthy", message="Not initialized")
        overall_status = "unhealthy"

    # Check LLM registry
    llm_registry = _app_state.get("llm_registry")
    if llm_registry and len(llm_registry) > 0:
        components["llm"] = ComponentHealth(status="healthy", message=f"{len(llm_registry)} providers")
    else:
        components["llm"] = ComponentHealth(status="unhealthy", message="No LLM providers")
        overall_status = "unhealthy"

    # Check MCP registry
    mcp_registry = _app_state.get("mcp_registry")
    if mcp_registry:
        connected = len(mcp_registry.list_connected_servers())
        total = len(mcp_registry)
        if connected == total:
            components["mcp"] = ComponentHealth(status="healthy", message=f"{connected} servers")
        elif connected > 0:
            components["mcp"] = ComponentHealth(status="degraded", message=f"{connected}/{total} servers")
            if overall_status == "healthy":
                overall_status = "degraded"
        else:
            components["mcp"] = ComponentHealth(status="unhealthy", message="No servers connected")

    # Check agent registry
    agent_registry = _app_state.get("agent_registry")
    if agent_registry and len(agent_registry) > 0:
        components["agents"] = ComponentHealth(status="healthy", message=f"{len(agent_registry)} agents")
    else:
        components["agents"] = ComponentHealth(status="unhealthy", message="No agents")
        overall_status = "unhealthy"

    return HealthResponse(
        status=overall_status,
        version=maos.__version__,
        uptime_seconds=uptime,
        components=components,
    )
