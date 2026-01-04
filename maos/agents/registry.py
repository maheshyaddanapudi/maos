"""
MAOS Agent Registry.

Manages agent instances.
"""

import structlog

from maos.agents.models import Agent

log = structlog.get_logger()


class AgentRegistry:
    """Registry of agent instances."""

    def __init__(self):
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        """Register an agent.

        Args:
            agent: Agent to register
        """
        self._agents[agent.name] = agent
        log.debug("agent_registered", name=agent.name, kind=agent.kind)

    def register_all(self, agents: dict[str, Agent]) -> None:
        """Register multiple agents.

        Args:
            agents: Dictionary of agents keyed by name
        """
        for name, agent in agents.items():
            self._agents[name] = agent
        log.info("agents_registered", count=len(agents))

    def get(self, name: str) -> Agent | None:
        """Get agent by name.

        Args:
            name: Agent name

        Returns:
            Agent or None if not found
        """
        return self._agents.get(name)

    def get_or_raise(self, name: str) -> Agent:
        """Get agent by name or raise error.

        Args:
            name: Agent name

        Returns:
            Agent

        Raises:
            KeyError: If agent not found
        """
        agent = self.get(name)
        if agent is None:
            raise KeyError(f"Agent not found: {name}")
        return agent

    def get_supervisor(self) -> Agent | None:
        """Get the supervisor agent.

        Returns:
            Supervisor agent or None
        """
        for agent in self._agents.values():
            if agent.is_supervisor:
                return agent
        return None

    def get_workers(self) -> dict[str, Agent]:
        """Get all worker agents.

        Returns:
            Dictionary of worker agents
        """
        return {
            name: agent
            for name, agent in self._agents.items()
            if agent.is_worker
        }

    def get_worker_names(self) -> list[str]:
        """Get names of all worker agents.

        Returns:
            List of worker names
        """
        return [name for name, agent in self._agents.items() if agent.is_worker]

    def list_all(self) -> list[Agent]:
        """List all registered agents.

        Returns:
            List of agents
        """
        return list(self._agents.values())

    def list_names(self) -> list[str]:
        """List all agent names.

        Returns:
            List of agent names
        """
        return list(self._agents.keys())

    def get_roster(self) -> list[str]:
        """Get the roster of available workers for routing.

        Returns:
            List of worker names with descriptions
        """
        roster = []
        for name, agent in self._agents.items():
            if agent.is_worker:
                desc = agent.description or f"Worker agent: {name}"
                roster.append(f"- {name}: {desc}")
        return roster

    def __len__(self) -> int:
        return len(self._agents)

    def __contains__(self, name: str) -> bool:
        return name in self._agents

    def __iter__(self):
        return iter(self._agents.items())
