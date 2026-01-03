"""
MAOS API Server.

FastAPI application factory and server setup.
"""

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from maos.api.routes import agents, chat, health, openai_compat
from maos.config.models import Config, ServingConfig

log = structlog.get_logger()

# Global app state (set during create_app)
_app_state: dict = {}


def create_app(
    config: Config | None = None,
    llm_registry=None,
    mcp_registry=None,
    tool_registry=None,
    skill_registry=None,
    skillset_registry=None,
    agent_registry=None,
    graph=None,
    external_agents=None,
) -> FastAPI:
    """Create FastAPI application.

    Args:
        config: System configuration
        llm_registry: LLM registry instance
        mcp_registry: MCP registry instance
        tool_registry: Tool registry instance
        skill_registry: Skill registry instance
        skillset_registry: Skillset registry instance
        agent_registry: Agent registry instance
        graph: Compiled LangGraph instance
        external_agents: List of discovered external agents

    Returns:
        FastAPI application
    """
    global _app_state

    # Get serving config
    serving_config = config.serving if config else ServingConfig()

    # Create FastAPI app
    app = FastAPI(
        title="MAOS - Multi-Agent Orchestration System",
        description="Config-driven multi-agent orchestration with LangGraph, MCP, and A2A",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=serving_config.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store state
    _app_state = {
        "config": config,
        "llm_registry": llm_registry,
        "mcp_registry": mcp_registry,
        "tool_registry": tool_registry,
        "skill_registry": skill_registry,
        "skillset_registry": skillset_registry,
        "agent_registry": agent_registry,
        "graph": graph,
        "external_agents": external_agents or [],
        "roster": [],
    }

    # Build roster
    if agent_registry:
        _app_state["roster"] = agent_registry.get_worker_names()

    if external_agents:
        for ext in external_agents:
            _app_state["roster"].append(f"ext::{ext.card.name}")

    # Include routers
    app.include_router(chat.router)
    app.include_router(agents.router)
    app.include_router(health.router)

    if serving_config.api.openai_compatible:
        app.include_router(openai_compat.router)

    log.info(
        "api_created",
        cors_origins=serving_config.api.cors_origins,
        openai_compat=serving_config.api.openai_compatible,
    )

    return app


async def create_app_from_config(config: Config) -> FastAPI:
    """Create fully initialized FastAPI app from configuration.

    This is the main entry point that initializes all components.

    Args:
        config: System configuration

    Returns:
        Fully initialized FastAPI application
    """
    from maos.a2a.client import A2AClient
    from maos.a2a.discovery import A2ADiscovery
    from maos.agents.factory import AgentFactory
    from maos.agents.registry import AgentRegistry
    from maos.graph.factory import GraphFactory
    from maos.llm.registry import LLMRegistry
    from maos.mcp.registry import MCPRegistry
    from maos.skills.registry import SkillRegistry, SkillsetRegistry
    from maos.tools.registry import ToolRegistry

    log.info("initializing_system")

    # Initialize LLM registry
    llm_registry = LLMRegistry()
    llm_registry.build(config.llms)

    # Initialize MCP registry
    mcp_registry = MCPRegistry()
    await mcp_registry.connect_all(config.mcp_servers)

    # Initialize tool registry
    tool_registry = ToolRegistry(mcp_registry)
    await tool_registry.materialize(config.tools)

    # Initialize skill registries
    skill_registry = SkillRegistry(tool_registry)
    skill_registry.build(config.skills)

    skillset_registry = SkillsetRegistry(skill_registry, tool_registry)
    skillset_registry.build(config.skillsets)

    # Initialize agent factory and registry
    agent_factory = AgentFactory(
        llm_registry=llm_registry,
        skillset_registry=skillset_registry,
        skill_registry=skill_registry,
        tool_registry=tool_registry,
    )

    agents = await agent_factory.create_all(config.agents)
    agent_registry = AgentRegistry()
    agent_registry.register_all(agents)

    # Discover external agents
    external_agents = []
    a2a_client = None

    if config.a2a.import_policy.enabled and config.a2a.discovery.seeds:
        discovery = A2ADiscovery()
        try:
            external_agents = await discovery.discover(config.a2a)
            if external_agents:
                a2a_client = A2AClient()
            log.info("external_agents_discovered", count=len(external_agents))
        except Exception as e:
            log.warning("a2a_discovery_failed", error=str(e))
        finally:
            await discovery.close()

    # Build graph
    graph_factory = GraphFactory(
        llm_registry=llm_registry,
        agent_registry=agent_registry,
        graph_config=config.graph,
        external_agents=external_agents,
        a2a_client=a2a_client,
    )

    graph = graph_factory.build()

    log.info(
        "system_initialized",
        llms=len(llm_registry),
        tools=len(tool_registry),
        agents=len(agent_registry),
        external_agents=len(external_agents),
    )

    # Create app
    return create_app(
        config=config,
        llm_registry=llm_registry,
        mcp_registry=mcp_registry,
        tool_registry=tool_registry,
        skill_registry=skill_registry,
        skillset_registry=skillset_registry,
        agent_registry=agent_registry,
        graph=graph,
        external_agents=external_agents,
    )
