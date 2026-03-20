"""Factory for creating agents."""


import structlog

from maos.agents.models import Agent, SupervisorAgent, WorkerAgent
from maos.config.models import AgentConfig, AgentKind
from maos.llm.registry import LLMRegistry
from maos.skills.registry import SkillRegistry, SkillsetRegistry
from maos.tools.models import Tool
from maos.tools.registry import ToolRegistry

logger = structlog.get_logger()


class AgentFactory:
    """Factory for creating agents."""

    def __init__(
        self,
        llm_registry: LLMRegistry,
        skillset_registry: SkillsetRegistry,
        skill_registry: SkillRegistry,
        tool_registry: ToolRegistry
    ):
        """
        Initialize the agent factory.

        Args:
            llm_registry: Registry of LLM adapters.
            skillset_registry: Registry of skillsets.
            skill_registry: Registry of skills.
            tool_registry: Registry of tools.
        """
        self._llm_registry = llm_registry
        self._skillset_registry = skillset_registry
        self._skill_registry = skill_registry
        self._tool_registry = tool_registry

    def create_worker(
        self,
        name: str,
        config: AgentConfig
    ) -> WorkerAgent:
        """
        Create a native worker agent.

        Args:
            name: Agent name.
            config: Agent configuration.

        Returns:
            Configured WorkerAgent.
        """
        if config.kind != AgentKind.NATIVE_WORKER:
            raise ValueError(f"Expected native_worker, got {config.kind}")

        # Resolve tools from skillset
        tool_ids = []
        if config.skillset:
            tool_ids = self._skillset_registry.get(config.skillset)
            if tool_ids:
                tool_ids = tool_ids.get_all_tool_ids(self._skill_registry)
            else:
                tool_ids = []

        # Add direct tool references
        if config.tools:
            tool_ids.extend(config.tools)

        worker = WorkerAgent(
            name=name,
            description=config.description or "",
            system_prompt=config.system_prompt,
            framework=config.framework,
            timeout_seconds=config.timeout_seconds,
            skillset=config.skillset,
            tool_ids=list(set(tool_ids)),  # Dedupe
            llm_name=config.llm
        )

        logger.debug(
            "created_worker_agent",
            name=name,
            framework=config.framework,
            tools=len(worker.tool_ids)
        )

        return worker

    def create(self, name: str, config: AgentConfig, roster: list[str] | None = None) -> Agent:
        """
        Create an agent based on its kind.

        Args:
            name: Agent name.
            config: Agent configuration.
            roster: List of worker names (required for supervisor).

        Returns:
            Created agent.

        Raises:
            ValueError: If agent kind is invalid or supervisor missing roster.
        """
        if config.kind == AgentKind.NATIVE_WORKER:
            return self.create_worker(name, config)
        elif config.kind == AgentKind.SUPERVISOR:
            if roster is None:
                roster = []  # Will be populated later
            return self.create_supervisor(name, config, roster)
        elif config.kind == AgentKind.EXTERNAL:
            # External agents are created via A2A discovery, not factory
            raise ValueError("External agents should be created via A2A discovery")
        else:
            raise ValueError(f"Unknown agent kind: {config.kind}")

    def create_supervisor(
        self,
        name: str,
        config: AgentConfig,
        roster: list[str]
    ) -> SupervisorAgent:
        """
        Create the supervisor agent.

        Args:
            name: Agent name.
            config: Agent configuration.
            roster: List of worker names the supervisor can route to.

        Returns:
            Configured SupervisorAgent.
        """
        if config.kind != AgentKind.SUPERVISOR:
            raise ValueError(f"Expected supervisor, got {config.kind}")

        # Get LLM adapter
        llm = self._llm_registry.get_or_default(config.llm)

        supervisor = SupervisorAgent(
            name=name,
            description=config.description or "Supervisor agent",
            system_prompt=config.system_prompt,
            framework=config.framework,
            timeout_seconds=config.timeout_seconds,
            roster=roster,
            llm_name=config.llm,
            max_iterations=12  # Could be made configurable
        )
        supervisor.set_llm(llm)

        logger.debug(
            "created_supervisor_agent",
            name=name,
            roster=roster
        )

        return supervisor

    def get_tools_for_worker(self, worker: WorkerAgent) -> list[Tool]:
        """
        Get all tools for a worker agent.

        Args:
            worker: The worker agent.

        Returns:
            List of Tool objects.
        """
        tools = []
        for tool_id in worker.tool_ids:
            tool = self._tool_registry.get(tool_id)
            if tool:
                tools.append(tool)
        return tools
