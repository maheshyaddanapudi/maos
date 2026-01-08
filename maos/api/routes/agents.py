"""Agent listing endpoint."""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends
import structlog

from maos.api.models import AgentInfo, AgentListResponse

logger = structlog.get_logger()

router = APIRouter(tags=["agents"])


def get_app_context() -> Dict[str, Any]:
    """Get application context - to be overridden by dependency injection."""
    return {}


@router.get("/agents", response_model=AgentListResponse)
async def list_agents(
    context: Dict[str, Any] = Depends(get_app_context)
) -> AgentListResponse:
    """
    List all available agents.

    Returns information about:
    - The supervisor agent
    - All worker agents (native)
    - All external agents (via A2A)
    """
    workers: List[AgentInfo] = []
    external_agents: List[AgentInfo] = []
    supervisor_info = None

    agent_registry = context.get("agent_registry")
    tool_registry = context.get("tool_registry")

    if agent_registry:
        # Get supervisor
        supervisor = agent_registry.get_supervisor() if hasattr(agent_registry, 'get_supervisor') else None
        if supervisor:
            supervisor_info = AgentInfo(
                name=supervisor.name,
                kind="supervisor",
                description=getattr(supervisor, 'description', None),
                llm=getattr(supervisor, 'llm_name', None)
            )

        # Get workers
        if hasattr(agent_registry, 'get_workers'):
            for name, worker in agent_registry.get_workers():
                # Get tool names for this worker
                tool_names = []
                if hasattr(worker, 'tool_ids') and tool_registry:
                    for tool_id in worker.tool_ids:
                        tool = tool_registry.get(tool_id)
                        if tool:
                            tool_names.append(tool.name)

                # Get skill names
                skill_names = []
                if hasattr(worker, 'skillset_name'):
                    skill_names = [worker.skillset_name] if worker.skillset_name else []

                workers.append(AgentInfo(
                    name=name,
                    kind="native_worker",
                    description=getattr(worker, 'description', None),
                    llm=getattr(worker, 'llm_name', None),
                    framework=getattr(worker, 'framework', None),
                    tools=tool_names,
                    skills=skill_names
                ))

        # Get external agents
        if hasattr(agent_registry, 'get_externals'):
            for name, external in agent_registry.get_externals():
                external_agents.append(AgentInfo(
                    name=name,
                    kind="external",
                    description=getattr(external, 'description', None),
                    llm=None,  # External agents don't expose their LLM
                    tools=[]  # External agent tools are opaque
                ))

    return AgentListResponse(
        agents=workers,
        supervisor=supervisor_info,
        external_agents=external_agents
    )


@router.get("/agents/{agent_name}", response_model=AgentInfo)
async def get_agent(
    agent_name: str,
    context: Dict[str, Any] = Depends(get_app_context)
) -> AgentInfo:
    """
    Get details about a specific agent.

    Args:
        agent_name: Name of the agent.

    Returns:
        Agent information.
    """
    from fastapi import HTTPException

    agent_registry = context.get("agent_registry")
    tool_registry = context.get("tool_registry")

    if not agent_registry:
        raise HTTPException(status_code=503, detail="Agent registry not available")

    # Check supervisor
    supervisor = agent_registry.get_supervisor() if hasattr(agent_registry, 'get_supervisor') else None
    if supervisor and supervisor.name == agent_name:
        return AgentInfo(
            name=supervisor.name,
            kind="supervisor",
            description=getattr(supervisor, 'description', None),
            llm=getattr(supervisor, 'llm_name', None)
        )

    # Check workers
    if hasattr(agent_registry, 'get_workers'):
        for name, worker in agent_registry.get_workers():
            if name == agent_name:
                tool_names = []
                if hasattr(worker, 'tool_ids') and tool_registry:
                    for tool_id in worker.tool_ids:
                        tool = tool_registry.get(tool_id)
                        if tool:
                            tool_names.append(tool.name)

                return AgentInfo(
                    name=name,
                    kind="native_worker",
                    description=getattr(worker, 'description', None),
                    llm=getattr(worker, 'llm_name', None),
                    framework=getattr(worker, 'framework', None),
                    tools=tool_names
                )

    # Check externals
    if hasattr(agent_registry, 'get_externals'):
        for name, external in agent_registry.get_externals():
            if name == agent_name:
                return AgentInfo(
                    name=name,
                    kind="external",
                    description=getattr(external, 'description', None)
                )

    raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")


@router.get("/roster")
async def get_roster(
    context: Dict[str, Any] = Depends(get_app_context)
) -> Dict[str, Any]:
    """
    Get the current agent roster.

    Returns the list of agent names available for task routing.
    """
    agent_registry = context.get("agent_registry")

    if not agent_registry:
        return {"roster": []}

    roster = agent_registry.get_roster() if hasattr(agent_registry, 'get_roster') else []

    return {"roster": roster}
