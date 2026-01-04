"""
MAOS Agent Factory.

Creates agent instances from configuration.
"""


import structlog

from maos.agents.models import Agent, ResultMetadata, ToolCallRecord, WorkerResult
from maos.config.models import AgentConfig, AgentKind
from maos.errors import AgentError
from maos.llm.base import LLMAdapter, Message, ToolDefinition
from maos.llm.registry import LLMRegistry
from maos.skills.registry import SkillRegistry, SkillsetRegistry
from maos.tools.models import Tool
from maos.tools.registry import ToolRegistry

log = structlog.get_logger()


class AgentFactory:
    """Factory for creating agents."""

    def __init__(
        self,
        llm_registry: LLMRegistry,
        skillset_registry: SkillsetRegistry,
        skill_registry: SkillRegistry,
        tool_registry: ToolRegistry,
    ):
        self._llm_registry = llm_registry
        self._skillset_registry = skillset_registry
        self._skill_registry = skill_registry
        self._tool_registry = tool_registry

    async def create_agent(self, name: str, config: AgentConfig) -> Agent:
        """Create an agent from configuration.

        Args:
            name: Agent name
            config: Agent configuration

        Returns:
            Configured Agent instance
        """
        log.debug("creating_agent", name=name, kind=config.kind)

        # Resolve LLM
        llm = self._llm_registry.get_or_default(config.llm)

        # Resolve tools from skillset
        tools: list[Tool] = []
        if config.skillset:
            tools = self._skillset_registry.get_all_tools(config.skillset)

        # Add any directly specified tools
        if config.tools:
            for tool_id in config.tools:
                tool = self._tool_registry.get(tool_id)
                if tool and tool not in tools:
                    tools.append(tool)

        # Create agent
        agent = Agent(
            name=name,
            kind=config.kind,
            description=config.description or "",
            framework=config.framework,
            llm_name=config.llm,
            skillset_name=config.skillset,
            system_prompt=config.system_prompt,
            tools=tools,
            timeout_seconds=config.timeout_seconds,
        )

        # Set up execution function based on kind
        if config.kind == AgentKind.NATIVE_WORKER:
            execute_func = self._create_worker_executor(agent, llm)
            agent.set_execute_func(execute_func)

        log.info(
            "agent_created",
            name=name,
            kind=config.kind,
            tool_count=len(tools),
        )

        return agent

    def _create_worker_executor(
        self,
        agent: Agent,
        llm: LLMAdapter,
    ):
        """Create execution function for a worker agent.

        This creates a simple ReAct-style agent that can use tools.
        """
        async def execute(task: str) -> WorkerResult:
            import time
            start_time = time.time()

            try:
                # Build messages
                messages = [
                    Message(role="system", content=agent.system_prompt),
                    Message(role="user", content=task),
                ]

                # Convert tools to LLM format
                tool_defs = [
                    ToolDefinition(
                        name=t.id,
                        description=t.description,
                        parameters=t.input_schema,
                    )
                    for t in agent.tools
                ]

                tool_records: list[ToolCallRecord] = []
                max_iterations = 5
                iteration = 0

                while iteration < max_iterations:
                    iteration += 1

                    # Invoke LLM
                    response = await llm.invoke(messages, tool_defs if tool_defs else None)

                    # If no tool calls, we're done
                    if not response.has_tool_calls:
                        duration_ms = int((time.time() - start_time) * 1000)
                        return WorkerResult.success(
                            from_agent=agent.name,
                            content=response.content or "",
                            tool_calls=tool_records,
                            metadata=ResultMetadata(
                                tokens_used=response.usage.get("total_tokens", 0),
                                duration_ms=duration_ms,
                                tools_invoked=[tr.tool_name for tr in tool_records],
                                model_used=llm.model_name,
                            ),
                        )

                    # Process tool calls
                    from maos.llm.base import ToolCall as LLMToolCall
                    tool_call_message = Message(
                        role="assistant",
                        content=response.content or "",
                        tool_calls=[
                            LLMToolCall(id=tc.id, name=tc.name, arguments=tc.arguments)
                            for tc in response.tool_calls
                        ],
                    )
                    messages.append(tool_call_message)

                    for tc in response.tool_calls:
                        # Execute tool
                        tool_result = await self._tool_registry.invoke_tool(
                            tc.name,
                            tc.arguments,
                        )

                        # Record tool call
                        tool_records.append(ToolCallRecord(
                            tool_id=tc.id,
                            tool_name=tc.name,
                            input_args=tc.arguments,
                            output=tool_result.output,
                            success=tool_result.success,
                            error_message=tool_result.error,
                            duration_ms=tool_result.duration_ms,
                        ))

                        # Add tool result to messages
                        messages.append(Message(
                            role="tool",
                            content=str(tool_result.output) if tool_result.success else f"Error: {tool_result.error}",
                            tool_call_id=tc.id,
                        ))

                # Max iterations reached
                duration_ms = int((time.time() - start_time) * 1000)
                return WorkerResult.error(
                    from_agent=agent.name,
                    error_message="Max iterations reached without completing task",
                    metadata=ResultMetadata(duration_ms=duration_ms),
                )

            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                log.error("agent_execution_error", agent=agent.name, error=str(e))
                return WorkerResult.error(
                    from_agent=agent.name,
                    error_message=str(e),
                    metadata=ResultMetadata(duration_ms=duration_ms),
                )

        return execute

    async def create_all(self, agent_configs: dict[str, AgentConfig]) -> dict[str, Agent]:
        """Create all agents from configuration.

        Args:
            agent_configs: Dictionary of agent configurations

        Returns:
            Dictionary of created agents
        """
        agents = {}
        for name, config in agent_configs.items():
            try:
                agent = await self.create_agent(name, config)
                agents[name] = agent
            except Exception as e:
                log.error("agent_creation_failed", name=name, error=str(e))
                raise AgentError(f"Failed to create agent '{name}': {e}")

        return agents
