"""
MAOS Agents Routes.

Endpoints for agent information.
"""

from fastapi import APIRouter, Depends

from maos.api.models import AgentInfo, AgentsResponse

router = APIRouter(tags=["agents"])


def get_agent_registry():
    """Dependency to get the agent registry."""
    from maos.api.server import _app_state
    return _app_state.get("agent_registry")


def get_external_agents():
    """Dependency to get external agents."""
    from maos.api.server import _app_state
    return _app_state.get("external_agents", [])


@router.get("/agents", response_model=AgentsResponse)
async def list_agents(
    agent_registry=Depends(get_agent_registry),
    external_agents=Depends(get_external_agents),
):
    """List all available agents."""
    response = AgentsResponse()

    if agent_registry is None:
        return response

    # Get supervisor
    supervisor = agent_registry.get_supervisor()
    if supervisor:
        response.supervisor = AgentInfo(
            name=supervisor.name,
            description=supervisor.description,
            kind="supervisor",
            skills=[],
            framework=supervisor.framework.value if supervisor.framework else None,
            status="active",
        )

    # Get native workers
    workers = agent_registry.get_workers()
    for name, agent in workers.items():
        response.native_workers.append(AgentInfo(
            name=name,
            description=agent.description,
            kind="native_worker",
            skills=agent.get_tool_names(),
            framework=agent.framework.value if agent.framework else None,
            status="active",
        ))

    # Get external agents
    for ext in external_agents:
        response.external_agents.append(AgentInfo(
            name=f"ext::{ext.card.name}",
            description=ext.card.description,
            kind="external",
            skills=ext.card.skill_names,
            framework=None,
            status="active",
        ))

    return response
