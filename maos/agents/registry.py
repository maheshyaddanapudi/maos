"""Registry for agents."""

from typing import Any

import structlog

from maos.agents.factory import AgentFactory
from maos.agents.models import Agent, ExternalAgent, SupervisorAgent, WorkerAgent
from maos.config.models import AgentConfig, AgentKind, Config

logger = structlog.get_logger()


class ManagedExternalAgent:
    """An external agent managed by the registry (started with the app)."""

    def __init__(
        self,
        name: str,
        config: AgentConfig,
        server: Any,  # ExternalAgentServer instance
    ):
        self.name = name
        self.config = config
        self.server = server

    @property
    def endpoint(self) -> str:
        return self.server.endpoint

    @property
    def port(self) -> int:
        return self.server.port


class AgentRegistry:
    """Registry of all agents (native, external, and managed external)."""

    def __init__(self, factory: AgentFactory):
        """
        Initialize the agent registry.

        Args:
            factory: Agent factory for creating agents.
        """
        self._factory = factory
        self._supervisor: SupervisorAgent | None = None
        self._workers: dict[str, WorkerAgent] = {}
        self._externals: dict[str, ExternalAgent] = {}
        # Managed external agents (started with the app)
        self._managed_externals: dict[str, ManagedExternalAgent] = {}
        # Configs for external agents to be started
        self._external_configs: dict[str, AgentConfig] = {}

    def build(self, config: Config) -> None:
        """
        Build registry from configuration.

        Args:
            config: Full system configuration.
        """
        # First, collect all agent names by type
        worker_names = []
        external_names = []
        supervisor_name = None
        supervisor_config = None

        for name, agent_config in config.agents.items():
            if agent_config.kind == AgentKind.SUPERVISOR:
                supervisor_name = name
                supervisor_config = agent_config
            elif agent_config.kind == AgentKind.NATIVE_WORKER:
                if name not in config.native_workers.ignore_workers:
                    worker_names.append(name)
            elif agent_config.kind == AgentKind.EXTERNAL:
                external_names.append(name)
                self._external_configs[name] = agent_config

        # Create workers
        for name in worker_names:
            agent_config = config.agents[name]
            worker = self._factory.create_worker(name, agent_config)
            self._workers[name] = worker

        # Create supervisor with full roster (including external agents)
        if supervisor_name and supervisor_config:
            # Roster includes workers; externals will be added when they start
            roster = list(worker_names) + external_names
            self._supervisor = self._factory.create_supervisor(
                supervisor_name, supervisor_config, roster
            )

        logger.info(
            "built_agent_registry",
            supervisor=supervisor_name,
            workers=len(self._workers),
            external_configs=len(self._external_configs),
        )

    def get_external_configs(self) -> dict[str, AgentConfig]:
        """Get configs for external agents that need to be started."""
        return self._external_configs

    def register_managed_external(self, name: str, config: AgentConfig, server: Any) -> None:
        """
        Register a managed external agent that was started with the app.

        Args:
            name: Agent name.
            config: Agent configuration.
            server: The running ExternalAgentServer instance.
        """
        managed = ManagedExternalAgent(name, config, server)
        self._managed_externals[name] = managed

        # Also create an ExternalAgent entry for graph building
        external = ExternalAgent(
            name=name,
            description=config.description or "",
            endpoint=server.endpoint,
            import_mode="node",
        )
        # Store the server reference for later use
        external._server = server
        self._externals[name] = external

        logger.info(
            "registered_managed_external", name=name, endpoint=server.endpoint, port=server.port
        )

    def get_managed_externals(self) -> list[ManagedExternalAgent]:
        """Get all managed external agents."""
        return list(self._managed_externals.values())

    def add_external(self, agent: ExternalAgent) -> None:
        """
        Add an external agent to the registry.

        Args:
            agent: External agent to add.
        """
        self._externals[agent.name] = agent

        # Update supervisor roster if importing as node
        if self._supervisor and agent.import_mode == "node":
            self._supervisor.roster.append(agent.node_id)

        logger.debug("added_external_agent", name=agent.name, mode=agent.import_mode)

    def get_supervisor(self) -> SupervisorAgent | None:
        """Get the supervisor agent."""
        return self._supervisor

    def get_worker(self, name: str) -> WorkerAgent | None:
        """Get a worker by name."""
        return self._workers.get(name)

    def get_external(self, name: str) -> ExternalAgent | None:
        """Get an external agent by name."""
        return self._externals.get(name)

    def get_agent(self, name: str) -> Agent | None:
        """
        Get any agent by name.

        Checks workers first, then externals, then supervisor.
        """
        if name in self._workers:
            return self._workers[name]
        if name in self._externals:
            return self._externals[name]
        if self._supervisor and self._supervisor.name == name:
            return self._supervisor
        # Check for external node IDs
        for ext in self._externals.values():
            if ext.node_id == name:
                return ext
        return None

    def get_workers(self) -> list[tuple[str, WorkerAgent]]:
        """Get all workers as (name, agent) pairs."""
        return list(self._workers.items())

    def get_externals(self) -> list[tuple[str, ExternalAgent]]:
        """Get all externals as (name, agent) pairs."""
        return list(self._externals.items())

    def get_roster(self) -> list[str]:
        """Get the full roster for the supervisor."""
        roster = list(self._workers.keys())
        for ext in self._externals.values():
            if ext.import_mode == "node":
                roster.append(ext.node_id)
        return roster

    def list_worker_names(self) -> list[str]:
        """List all worker names."""
        return list(self._workers.keys())

    def list_external_names(self) -> list[str]:
        """List all external agent names."""
        return list(self._externals.keys())

    def __contains__(self, name: str) -> bool:
        """Check if an agent exists."""
        return (
            name in self._workers
            or name in self._externals
            or (self._supervisor is not None and self._supervisor.name == name)
        )

    def __len__(self) -> int:
        """Get total number of agents."""
        count = len(self._workers) + len(self._externals)
        if self._supervisor:
            count += 1
        return count
