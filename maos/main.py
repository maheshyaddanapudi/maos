"""Main entry point for MAOS."""

import argparse
import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from langgraph.checkpoint.memory import MemorySaver

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


async def _wait_for_server(
    server,
    timeout: float = 30.0,
    poll_interval: float = 0.2,
) -> bool:
    """Wait for an external agent server to become ready.

    Args:
        server: The server instance (must have an ``endpoint``).
        timeout: Maximum seconds to wait.
        poll_interval: Seconds between readiness checks.

    Returns:
        True if the server is ready within the timeout.
    """
    import time as _time

    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        # Check if the server has a port assigned and is serving
        if getattr(server, "port", None) is not None:
            try:
                import httpx

                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{server.endpoint}/.well-known/agent.json",
                        timeout=2.0,
                    )
                    if resp.status_code < 500:
                        return True
            except Exception:
                pass
        await asyncio.sleep(poll_interval)
    return False


async def _start_external_agent(
    name: str,
    agent_config,
    llm_registry,
    llm_factory,
):
    """
    Start an external A2A agent server.

    Args:
        name: Agent name.
        agent_config: Agent configuration.
        llm_registry: LLM registry for getting adapters.
        llm_factory: LLM factory for creating adapters.

    Returns:
        The running ExternalAgentServer instance, or None if failed.
    """
    from maos.a2a.agents import TitleGeneratorAgent

    server_config = agent_config.server
    if server_config is None:
        # Use defaults
        host = "127.0.0.1"
        port = None  # Random
        implementation = "title_generator"
    else:
        host = server_config.host
        port = server_config.port
        implementation = server_config.implementation

    # Get LLM adapter for the external agent
    llm_adapter = llm_registry.get_or_default(agent_config.llm)

    # Create the appropriate server implementation
    if implementation == "title_generator":
        server = TitleGeneratorAgent(
            name=name,
            description=agent_config.description or "Generates titles for conversations",
            host=host,
            port=port,
            llm_adapter=llm_adapter,
            system_prompt=agent_config.system_prompt if agent_config.system_prompt else None,
        )
    else:
        # Could support custom implementations via module path
        logger.warning(
            "unknown_external_agent_implementation", name=name, implementation=implementation
        )
        return None

    # Start the server in background
    try:
        await server.start_background()
        logger.info("external_agent_started", name=name, endpoint=server.endpoint, port=server.port)
        return server
    except Exception as e:
        logger.error("failed_to_start_external_agent", name=name, error=str(e))
        return None


async def initialize_system(config_path: str, checkpointer=None) -> tuple:
    """
    Initialize all MAOS components from configuration.

    Args:
        config_path: Path to the configuration file.
        checkpointer: Optional LangGraph checkpointer.

    Returns:
        Tuple of (compiled_graph, app_context_dict)
    """
    from maos.a2a.client import A2AClient
    from maos.a2a.discovery import A2ADiscovery
    from maos.agents.factory import AgentFactory
    from maos.agents.registry import AgentRegistry
    from maos.config.loader import ConfigLoader
    from maos.graph.factory import GraphFactory
    from maos.llm.factory import LLMFactory
    from maos.llm.registry import LLMRegistry
    from maos.mcp.registry import MCPRegistry
    from maos.skills.registry import SkillRegistry, SkillsetRegistry
    from maos.tools.registry import ToolRegistry

    logger.info("initializing_maos", config_path=config_path)

    # Load configuration
    loader = ConfigLoader()
    config = loader.load(config_path)
    logger.info(
        "config_loaded",
        agents=len(config.agents),
        llms=len(config.llms),
    )

    # Validate cross-references
    errors = config.validate_references()
    if errors:
        for err in errors:
            logger.error("config_validation_error", error=err)
        raise ValueError(f"Config validation failed: {len(errors)} errors")

    # Initialize LLM registry
    llm_registry = LLMRegistry()
    llm_factory = LLMFactory()
    for name, llm_config in config.llms.items():
        adapter = llm_factory.create(llm_config)
        llm_registry.register_adapter(name, adapter)
    logger.info("llm_registry_initialized", count=len(config.llms))

    # Initialize MCP registry and register server configs
    mcp_registry = MCPRegistry()
    for name, server_config in config.mcp_servers.items():
        await mcp_registry.register(name, server_config)

    # Connect to all MCP servers
    if config.mcp_servers:
        await mcp_registry.connect_all()
    logger.info("mcp_registry_initialized", count=len(mcp_registry))

    # Initialize Tool registry and materialize tools from config
    tool_registry = ToolRegistry(mcp_registry=mcp_registry)
    await tool_registry.materialize(config.tools)
    logger.info("tool_registry_initialized", count=len(tool_registry))

    # Initialize Skill and Skillset registries
    skill_registry = SkillRegistry(tool_registry=tool_registry)
    skill_registry.build(config.skills)
    logger.info("skill_registry_initialized", count=len(skill_registry))

    skillset_registry = SkillsetRegistry(skill_registry=skill_registry, tool_registry=tool_registry)
    skillset_registry.build(config.skillsets)
    logger.info("skillset_registry_initialized", count=len(skillset_registry))

    # Initialize A2A components
    a2a_client = A2AClient()
    if config.a2a.discovery.seeds:
        discovery = A2ADiscovery()
        discovered_agents = await discovery.discover(config.a2a)
        logger.info(
            "a2a_discovery_complete",
            count=len(discovered_agents),
        )
    else:
        discovered_agents = []

    # Start managed external agents BEFORE building agent registry
    # so they are verified running when the graph is compiled.
    external_servers = []
    external_configs = {name: ac for name, ac in config.agents.items() if ac.kind == "external"}

    startup_timeout = float(config.graph.timeouts.external_agent_call_seconds)

    for name, agent_config in external_configs.items():
        server = await _start_external_agent(
            name=name,
            agent_config=agent_config,
            llm_registry=llm_registry,
            llm_factory=llm_factory,
        )
        if server:
            # Wait for the server to be ready with timeout
            ready = await _wait_for_server(server, timeout=startup_timeout)
            if ready:
                external_servers.append(server)
                logger.info(
                    "external_agent_ready",
                    name=name,
                    endpoint=server.endpoint,
                )
            else:
                logger.error(
                    "external_agent_not_ready",
                    name=name,
                    timeout=startup_timeout,
                )
                try:
                    await server.stop()
                except Exception:
                    pass

    if external_servers:
        logger.info(
            "started_external_agents",
            count=len(external_servers),
        )

    # Initialize Agent factory and registry
    agent_factory = AgentFactory(
        llm_registry=llm_registry,
        skillset_registry=skillset_registry,
        skill_registry=skill_registry,
        tool_registry=tool_registry,
        graph_config=config.graph,
    )
    agent_registry = AgentRegistry(factory=agent_factory)

    # Build all agents from config (handles supervisor/worker ordering)
    agent_registry.build(config)
    logger.info(
        "agent_registry_initialized",
        count=len(config.agents),
    )

    # Register successfully started external agents
    for server in external_servers:
        name = server.name
        if name in external_configs:
            agent_registry.register_managed_external(name, external_configs[name], server)

    # Register discovered A2A agents (from external discovery)
    for discovered in discovered_agents:
        agent_registry.add_external(discovered)

    # Build the graph AFTER all external agents are verified
    graph_factory = GraphFactory(
        config=config,
        agent_registry=agent_registry,
        llm_factory=llm_factory,
        tool_registry=tool_registry,
        a2a_client=a2a_client,
    )

    # Use provided checkpointer or create memory saver
    if checkpointer is None:
        checkpointer = MemorySaver()

    compiled_graph = graph_factory.compile(checkpointer=checkpointer)
    logger.info("graph_compiled")

    # Return context
    context = {
        "config": config,
        "llm_registry": llm_registry,
        "mcp_registry": mcp_registry,
        "tool_registry": tool_registry,
        "skill_registry": skill_registry,
        "skillset_registry": skillset_registry,
        "agent_registry": agent_registry,
        "graph": compiled_graph,
        "checkpointer": checkpointer,
        "external_servers": external_servers,
    }

    return compiled_graph, context


async def shutdown_system(context: dict) -> None:
    """
    Gracefully shutdown all MAOS components.

    Args:
        context: Application context dictionary.
    """
    logger.info("shutting_down_maos")

    # Stop external agent servers
    external_servers = context.get("external_servers", [])
    for server in external_servers:
        try:
            await server.stop()
        except Exception as e:
            logger.warning("failed_to_stop_external_agent", error=str(e))

    # Disconnect MCP servers
    mcp_registry = context.get("mcp_registry")
    if mcp_registry:
        await mcp_registry.disconnect_all()

    logger.info("maos_shutdown_complete")


async def run_server(config_path: str, host: str, port: int) -> None:
    """
    Run the MAOS API server.

    Args:
        config_path: Path to configuration file.
        host: Host to bind to.
        port: Port to listen on.
    """
    from maos.api.server import create_app, set_app_context

    # Initialize system
    checkpointer = MemorySaver()
    graph, context = await initialize_system(config_path, checkpointer)

    # Create FastAPI lifespan
    @asynccontextmanager
    async def lifespan(app):
        logger.info("maos_server_starting", host=host, port=port)
        yield
        await shutdown_system(context)

    # Create app
    app = create_app(config=context["config"], lifespan=lifespan)

    # Set app context
    set_app_context(
        llm_registry=context["llm_registry"],
        mcp_registry=context["mcp_registry"],
        tool_registry=context["tool_registry"],
        skill_registry=context["skill_registry"],
        skillset_registry=context["skillset_registry"],
        agent_registry=context["agent_registry"],
        graph=graph,
        checkpointer=checkpointer,
    )

    # Run server
    import uvicorn

    config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def run_interactive(config_path: str) -> None:
    """
    Run MAOS in interactive CLI mode.

    Args:
        config_path: Path to configuration file.
    """
    from maos.graph.state import create_initial_state

    # Initialize system
    graph, context = await initialize_system(config_path)
    agent_registry = context["agent_registry"]

    sys.stdout.write("\n=== MAOS Interactive Mode ===\n")
    sys.stdout.write("Type your message and press Enter. Type 'quit' to exit.\n\n")

    roster = agent_registry.get_roster()
    sys.stdout.write(f"Available agents: {', '.join(roster)}\n\n")

    thread_id = "interactive-session"
    messages = []

    try:
        while True:
            try:
                user_input = (await asyncio.to_thread(input, "You: ")).strip()
            except EOFError:
                break

            if user_input.lower() in ("quit", "exit", "q"):
                break

            if not user_input:
                continue

            # Add user message
            messages.append({"role": "user", "content": user_input})

            # Create state
            initial_state = create_initial_state(
                messages=messages, roster=roster, thread_id=thread_id
            )

            config = {"configurable": {"thread_id": thread_id}}

            # Run graph
            try:
                result = await graph.ainvoke(initial_state, config=config)

                # Get last assistant message
                for msg in reversed(result.get("messages", [])):
                    if isinstance(msg, dict) and msg.get("role") == "assistant":
                        sys.stdout.write(f"\nAssistant: {msg.get('content', '')}\n\n")
                        messages.append(msg)
                        break

            except Exception as e:
                logger.error("interactive_error", error=str(e))
                sys.stdout.write("\nError: An error occurred while processing your request.\n\n")

    finally:
        await shutdown_system(context)
        sys.stdout.write("\nGoodbye!\n")


async def validate_config(config_path: str) -> bool:
    """
    Validate a configuration file.

    Args:
        config_path: Path to configuration file.
    """
    from maos.config.loader import ConfigLoader

    loader = ConfigLoader()

    try:
        config = loader.load(config_path)
        logger.info(
            "config_valid",
            llms=len(config.llms),
            mcp_servers=len(config.mcp_servers),
            tools=len(config.tools),
            skills=len(config.skills),
            skillsets=len(config.skillsets),
            agents=len(config.agents),
        )
        return True
    except Exception as e:
        logger.error("config_invalid", error=str(e))
        return False


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="MAOS - Multi-Agent Orchestration System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  maos serve -c config.yaml                    # Start the API server
  maos serve -c config.yaml --port 8080        # Start on port 8080
  maos interactive -c config.yaml              # Interactive CLI mode
  maos validate -c config.yaml                 # Validate configuration
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start the API server")
    serve_parser.add_argument("-c", "--config", required=True, help="Path to configuration file")
    serve_parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )
    serve_parser.add_argument(
        "--port", type=int, default=7777, help="Port to listen on (default: 7777)"
    )

    # Interactive command
    interactive_parser = subparsers.add_parser("interactive", help="Run in interactive CLI mode")
    interactive_parser.add_argument(
        "-c", "--config", required=True, help="Path to configuration file"
    )

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate configuration file")
    validate_parser.add_argument("-c", "--config", required=True, help="Path to configuration file")

    # Version
    parser.add_argument("--version", action="version", version="MAOS 0.1.0")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    # Validate config path exists
    if hasattr(args, "config") and not Path(args.config).exists():
        logger.error("config_file_not_found", path=args.config)
        sys.exit(1)

    # Run the appropriate command
    if args.command == "serve":
        asyncio.run(run_server(args.config, args.host, args.port))
    elif args.command == "interactive":
        asyncio.run(run_interactive(args.config))
    elif args.command == "validate":
        valid = asyncio.run(validate_config(args.config))
        sys.exit(0 if valid else 1)


if __name__ == "__main__":
    main()
