"""Registry for agents."""

from typing import Dict, List, Optional, Tuple

import structlog

from maos.config.models import AgentConfig, AgentKind, Config
from maos.agents.models import Agent, WorkerAgent, SupervisorAgent, ExternalAgent
from maos.agents.factory import AgentFactory

logger = structlog.get_logger()


class AgentRegistry:
    """Registry of all agents (native and external)."""

    def __init__(self, factory: AgentFactory):
        """
        Initialize the agent registry.

        Args:
            factory: Agent factory for creating agents.
        """
        self._factory = factory
        self._supervisor: Optional[SupervisorAgent] = None
        self._workers: Dict[str, WorkerAgent] = {}
        self._externals: Dict[str, ExternalAgent] = {}

    def build(self, config: Config) -> None:
        """
        Build registry from configuration.

        Args:
            config: Full system configuration.
        """
        # First, collect all worker names for the roster
        worker_names = []
        supervisor_name = None
        supervisor_config = None

        for name, agent_config in config.agents.items():
            if agent_config.kind == AgentKind.SUPERVISOR:
                supervisor_name = name
                supervisor_config = agent_config
            elif agent_config.kind == AgentKind.NATIVE_WORKER:
                if name not in config.native_workers.ignore_workers:
                    worker_names.append(name)

        # Create workers
        for name in worker_names:
            agent_config = config.agents[name]
            worker = self._factory.create_worker(name, agent_config)
            self._workers[name] = worker

        # Create supervisor with full roster
        if supervisor_name and supervisor_config:
            # Roster includes workers and will later include externals
            roster = list(worker_names)
            self._supervisor = self._factory.create_supervisor(
                supervisor_name,
                supervisor_config,
                roster
            )

        logger.info(
            "built_agent_registry",
            supervisor=supervisor_name,
            workers=len(self._workers)
        )

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

        logger.debug(
            "added_external_agent",
            name=agent.name,
            mode=agent.import_mode
        )

    def get_supervisor(self) -> Optional[SupervisorAgent]:
        """Get the supervisor agent."""
        return self._supervisor

    def get_worker(self, name: str) -> Optional[WorkerAgent]:
        """Get a worker by name."""
        return self._workers.get(name)

    def get_external(self, name: str) -> Optional[ExternalAgent]:
        """Get an external agent by name."""
        return self._externals.get(name)

    def get_agent(self, name: str) -> Optional[Agent]:
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

    def get_workers(self) -> List[Tuple[str, WorkerAgent]]:
        """Get all workers as (name, agent) pairs."""
        return list(self._workers.items())

    def get_externals(self) -> List[Tuple[str, ExternalAgent]]:
        """Get all externals as (name, agent) pairs."""
        return list(self._externals.items())

    def get_roster(self) -> List[str]:
        """Get the full roster for the supervisor."""
        roster = list(self._workers.keys())
        for ext in self._externals.values():
            if ext.import_mode == "node":
                roster.append(ext.node_id)
        return roster

    def list_worker_names(self) -> List[str]:
        """List all worker names."""
        return list(self._workers.keys())

    def list_external_names(self) -> List[str]:
        """List all external agent names."""
        return list(self._externals.keys())

    def __contains__(self, name: str) -> bool:
        """Check if an agent exists."""
        return (
            name in self._workers or
            name in self._externals or
            (self._supervisor is not None and self._supervisor.name == name)
        )

    def __len__(self) -> int:
        """Get total number of agents."""
        count = len(self._workers) + len(self._externals)
        if self._supervisor:
            count += 1
        return count
