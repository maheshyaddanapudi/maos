"""Main entry point for MAOS."""

import asyncio
import argparse
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

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
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


async def initialize_system(config_path: str, checkpointer=None):
    """
    Initialize all MAOS components from configuration.

    Args:
        config_path: Path to the configuration file.
        checkpointer: Optional LangGraph checkpointer.

    Returns:
        Tuple of (compiled_graph, app_context_dict)
    """
    from maos.config.loader import ConfigLoader
    from maos.llm.registry import LLMRegistry
    from maos.llm.factory import LLMFactory
    from maos.mcp.registry import MCPRegistry
    from maos.tools.registry import ToolRegistry
    from maos.skills.registry import SkillRegistry, SkillsetRegistry
    from maos.agents.registry import AgentRegistry
    from maos.agents.factory import AgentFactory
    from maos.a2a.discovery import A2ADiscovery
    from maos.a2a.client import A2AClient
    from maos.graph.factory import GraphFactory

    logger.info("initializing_maos", config_path=config_path)

    # Load configuration
    loader = ConfigLoader()
    config = loader.load(config_path)
    logger.info("config_loaded", agents=len(config.agents), llms=len(config.llms))

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
        discovery = A2ADiscovery(
            seed_urls=config.a2a.discovery.seeds,
            import_policy=config.a2a.import_policy,
            timeout=config.a2a.discovery.timeout_seconds
        )
        discovered_agents = await discovery.discover()
        logger.info("a2a_discovery_complete", count=len(discovered_agents))
    else:
        discovered_agents = []

    # Initialize Agent factory and registry
    agent_factory = AgentFactory(
        llm_registry=llm_registry,
        skillset_registry=skillset_registry,
        skill_registry=skill_registry,
        tool_registry=tool_registry,
    )
    agent_registry = AgentRegistry(factory=agent_factory)

    # Build all agents from config (handles supervisor/worker ordering)
    agent_registry.build(config)
    logger.info("agent_registry_initialized", count=len(config.agents))

    # Register discovered A2A agents
    for discovered in discovered_agents:
        agent_registry.add_external(discovered)

    # Build the graph using LangGraph native factory
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
        "checkpointer": checkpointer
    }

    return compiled_graph, context


async def shutdown_system(context: dict):
    """
    Gracefully shutdown all MAOS components.

    Args:
        context: Application context dictionary.
    """
    logger.info("shutting_down_maos")

    # Disconnect MCP servers
    mcp_registry = context.get("mcp_registry")
    if mcp_registry:
        await mcp_registry.disconnect_all()

    logger.info("maos_shutdown_complete")


async def run_server(config_path: str, host: str, port: int):
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
        checkpointer=checkpointer
    )

    # Run server
    import uvicorn
    config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def run_interactive(config_path: str):
    """
    Run MAOS in interactive CLI mode.

    Args:
        config_path: Path to configuration file.
    """
    from maos.graph.state import create_initial_state

    # Initialize system
    graph, context = await initialize_system(config_path)
    agent_registry = context["agent_registry"]

    print("\n=== MAOS Interactive Mode ===")
    print("Type your message and press Enter. Type 'quit' to exit.\n")

    roster = agent_registry.get_roster()
    print(f"Available agents: {', '.join(roster)}\n")

    thread_id = "interactive-session"
    messages = []

    try:
        while True:
            try:
                user_input = input("You: ").strip()
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
                messages=messages,
                roster=roster,
                thread_id=thread_id
            )

            config = {"configurable": {"thread_id": thread_id}}

            # Run graph
            try:
                result = await graph.ainvoke(initial_state, config=config)

                # Get last assistant message
                for msg in reversed(result.get("messages", [])):
                    if isinstance(msg, dict) and msg.get("role") == "assistant":
                        print(f"\nAssistant: {msg.get('content', '')}\n")
                        messages.append(msg)
                        break

            except Exception as e:
                print(f"\nError: {str(e)}\n")

    finally:
        await shutdown_system(context)
        print("\nGoodbye!")


async def validate_config(config_path: str):
    """
    Validate a configuration file.

    Args:
        config_path: Path to configuration file.
    """
    from maos.config.loader import ConfigLoader

    loader = ConfigLoader()

    try:
        config = loader.load(config_path)
        print(f"✓ Configuration is valid")
        print(f"  - LLMs: {len(config.llms)}")
        print(f"  - MCP Servers: {len(config.mcp_servers)}")
        print(f"  - Tools: {len(config.tools)}")
        print(f"  - Skills: {len(config.skills)}")
        print(f"  - Skillsets: {len(config.skillsets)}")
        print(f"  - Agents: {len(config.agents)}")
        return True
    except Exception as e:
        print(f"✗ Configuration is invalid: {str(e)}")
        return False


def main():
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
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start the API server")
    serve_parser.add_argument(
        "-c", "--config",
        required=True,
        help="Path to configuration file"
    )
    serve_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=7777,
        help="Port to listen on (default: 7777)"
    )

    # Interactive command
    interactive_parser = subparsers.add_parser(
        "interactive",
        help="Run in interactive CLI mode"
    )
    interactive_parser.add_argument(
        "-c", "--config",
        required=True,
        help="Path to configuration file"
    )

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate configuration file"
    )
    validate_parser.add_argument(
        "-c", "--config",
        required=True,
        help="Path to configuration file"
    )

    # Version
    parser.add_argument(
        "--version",
        action="version",
        version="MAOS 0.1.0"
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    # Validate config path exists
    if hasattr(args, 'config') and not Path(args.config).exists():
        print(f"Error: Configuration file not found: {args.config}")
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
