"""LangGraph-native factory using official langgraph-supervisor.

This module builds the orchestration graph using:
1. LangChain chat models (via langchain-openai, langchain-anthropic, etc.)
2. LangGraph's create_react_agent for tool-using workers
3. langgraph-supervisor's create_supervisor for automatic worker routing
4. A2A client for external agent communication
5. any-agent for multi-framework worker agents (openai, google, smolagents, etc.)

The supervisor automatically discovers workers from the agents list -
no need to hardcode worker names in system prompts.
"""

import os
from typing import Annotated, Any, TypedDict

import structlog
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from langgraph.types import interrupt
from langgraph_supervisor import create_supervisor

from maos.a2a.client import A2AClient
from maos.agents.models import ExternalAgent, WorkerAgent
from maos.agents.registry import AgentRegistry
from maos.config.models import Config, LLMConfig
from maos.llm.factory import LLMFactory
from maos.tools.registry import ToolRegistry

logger = structlog.get_logger()


def create_send_message_tool() -> BaseTool:
    """Create the send_message tool for human-in-the-loop."""

    def send_message(message: str) -> str:
        """Send a message to the user and wait for their response.

        Use this when you need clarification or user input before proceeding.
        The user will see your message and can respond.

        Args:
            message: The message to send to the user.

        Returns:
            The user's response.
        """
        # This triggers an interrupt - the actual handling is in the graph
        return str(
            interrupt(
                {
                    "type": "input_required",
                    "prompt": message,
                }
            )
        )

    return StructuredTool.from_function(
        func=send_message,
        name="send_message",
        description="Send a message to the user and wait for their response. Use when you need clarification or user input.",
    )


def create_external_agent_graph(external: ExternalAgent, a2a_client: A2AClient) -> StateGraph:
    """
    Create a LangGraph wrapper for an external A2A agent.

    This creates a simple graph that:
    1. Receives messages from the supervisor
    2. Calls the external agent via A2A protocol
    3. Returns the response

    Args:
        external: External agent configuration.
        a2a_client: A2A client for communication.

    Returns:
        Compiled graph that wraps the external agent.
    """
    from typing import TypedDict

    class ExternalState(TypedDict):
        messages: Annotated[list, add_messages]

    async def call_external(state: ExternalState) -> dict:
        """Call the external agent via A2A."""
        messages = state.get("messages", [])

        # Extract the task from the last human message
        task = ""
        for msg in reversed(messages):
            if hasattr(msg, "content") and hasattr(msg, "type"):
                if msg.type == "human":
                    task = msg.content
                    break
            elif isinstance(msg, dict) and msg.get("role") == "user":
                task = msg.get("content", "")
                break

        if not task:
            return {"messages": [AIMessage(content="No task provided to external agent.")]}

        try:
            # Call external agent via A2A
            response = await a2a_client.send_message(agent=external.discovered_agent, message=task)

            # Extract response content
            content = (
                response.result.message.text
                if response.result
                else "No response from external agent"
            )

            return {"messages": [AIMessage(content=content, name=external.name)]}

        except Exception as e:
            logger.error("external_agent_call_failed", agent=external.name, error=str(e))
            return {
                "messages": [
                    AIMessage(content=f"External agent '{external.name}' is currently unavailable.")
                ]
            }

    # Build simple graph
    graph = StateGraph(ExternalState)
    graph.add_node("call", call_external)
    graph.set_entry_point("call")
    graph.add_edge("call", END)

    return graph.compile(name=external.node_id)


# Maps MAOS framework names to any-agent framework identifiers
_ANYAGENT_FRAMEWORK_MAP: dict[str, str] = {
    "openai": "openai",
    "google": "google",
    "smolagents": "smolagents",
    "llamaindex": "llama_index",
    "agno": "agno",
    "tinyagent": "tinyagent",
}


def build_any_agent_model_id(llm_config: LLMConfig) -> str:
    """Build an any-agent model_id string from a MAOS LLMConfig.

    any-agent uses litellm-style model IDs like ``openai/gpt-4o`` or
    ``anthropic/claude-3-5-sonnet``.  We map our ``LLMProvider`` enum
    to the prefix any-agent expects.
    """
    prefix_map = {
        "openai": "openai/",
        "anthropic": "anthropic/",
        "google": "gemini/",
        "ollama": "ollama/",
        "openai_compatible": "openai/",
        "azure_openai": "azure/",
    }
    prefix = prefix_map.get(llm_config.provider, "")
    return f"{prefix}{llm_config.model}"


def _convert_langchain_tools_to_callables(tools: list[BaseTool]) -> list:
    """Convert LangChain ``BaseTool`` instances to plain callables.

    any-agent expects tools as Python callables with ``__name__`` and
    ``__doc__`` attributes.  We unwrap the underlying function from
    ``StructuredTool`` instances.
    """
    callables: list = []
    for tool in tools:
        # StructuredTool stores the underlying coroutine / function
        if hasattr(tool, "coroutine") and tool.coroutine is not None:
            func = tool.coroutine
        elif hasattr(tool, "func") and tool.func is not None:
            func = tool.func
        else:
            # Fallback — wrap the tool's ainvoke as a callable
            def _make_wrapper(t: BaseTool = tool) -> Any:
                async def _wrapper(**kwargs: Any) -> str:
                    return str(await t.ainvoke(kwargs))

                _wrapper.__name__ = t.name
                _wrapper.__doc__ = t.description
                return _wrapper

            func = _make_wrapper(tool)

        # Ensure introspection attributes any-agent relies on
        if not getattr(func, "__name__", None):
            try:
                func.__name__ = tool.name
            except AttributeError:
                pass
        if not getattr(func, "__doc__", None):
            try:
                func.__doc__ = tool.description
            except AttributeError:
                pass

        callables.append(func)
    return callables


class _StepLimitExceeded(Exception):
    """Raised when an any-agent worker exceeds its step limit."""


def _make_step_limit_callback(max_steps: int) -> Any:
    """Create a step-limiting callback for any-agent workers.

    Prevents runaway agents by counting LLM calls and raising
    ``_StepLimitExceeded`` when the limit is reached.  This is the
    recommended approach since any-agent removed ``max_turns`` in v1.2.1.
    """
    from any_agent.callbacks.base import Callback

    class StepLimitCallback(Callback):
        def before_llm_call(self, context: Any, *args: Any, **kwargs: Any) -> Any:
            count = context.shared.get("_step_count", 0) + 1
            context.shared["_step_count"] = count
            if count > max_steps:
                raise _StepLimitExceeded(
                    f"Agent exceeded step limit of {max_steps} LLM calls"
                )
            return context

    return StepLimitCallback()


# Default maximum LLM calls per any-agent worker invocation.
# Can be overridden via worker.timeout_seconds (we reuse it as a rough proxy).
_DEFAULT_MAX_STEPS = 25


async def create_any_agent_worker_graph(
    name: str,
    framework: str,
    model_id: str,
    system_prompt: str,
    tools: list[BaseTool] | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    model_args: dict | None = None,
    max_steps: int = _DEFAULT_MAX_STEPS,
) -> Any:
    """Create a LangGraph-compatible wrapper for an any-agent worker.

    The returned compiled graph has the same ``messages``-based state
    interface as ``create_react_agent``, so the supervisor treats it
    identically to a native LangChain worker.

    This is an async function that uses ``AnyAgent.create_async()`` to
    avoid nested-event-loop issues when called from within an async
    context (GitHub issue mozilla-ai/any-agent#807).

    Args:
        name: Worker agent name.
        framework: any-agent framework identifier (e.g. ``"openai"``).
        model_id: Model identifier in litellm format.
        system_prompt: Agent system prompt / instructions.
        tools: Optional LangChain tools (converted to callables).
        api_key: Optional API key for the LLM provider.
        api_base: Optional custom API base URL.
        model_args: Optional generation kwargs (temperature, etc.).
        max_steps: Maximum LLM calls before the agent is stopped.

    Returns:
        A compiled StateGraph usable as a worker in ``create_supervisor``.
    """
    from any_agent import AgentCancel as AnyAgentCancel
    from any_agent import AgentConfig as AnyAgentConfig
    from any_agent import AnyAgent

    any_framework = _ANYAGENT_FRAMEWORK_MAP.get(framework, framework)
    tool_callables = _convert_langchain_tools_to_callables(tools) if tools else []

    step_callback = _make_step_limit_callback(max_steps)

    agent_config = AnyAgentConfig(
        model_id=model_id,
        name=name,
        instructions=system_prompt,
        tools=tool_callables,
        callbacks=[step_callback],
        api_key=api_key,
        api_base=api_base,
        model_args=model_args or {},
    )

    try:
        # Use create_async to avoid nested-event-loop issues (#807)
        any_agent_instance = await AnyAgent.create_async(any_framework, agent_config)
    except (ImportError, NameError, ModuleNotFoundError) as e:
        raise ImportError(
            f"Framework '{framework}' requires additional dependencies. "
            f"Install with: pip install 'any-agent[{framework}]'\n"
            f"Original error: {e}"
        ) from e

    class AnyAgentState(TypedDict):
        messages: Annotated[list, add_messages]

    async def call_any_agent(state: AnyAgentState) -> dict:
        """Forward messages to the any-agent worker."""
        messages = state.get("messages", [])

        # Extract task — same logic as create_external_agent_graph
        task = ""
        for msg in reversed(messages):
            if hasattr(msg, "content") and hasattr(msg, "type"):
                if msg.type == "human":
                    task = msg.content
                    break
            elif isinstance(msg, dict) and msg.get("role") == "user":
                task = msg.get("content", "")
                break

        if not task:
            return {"messages": [AIMessage(content="No task provided.", name=name)]}

        try:
            trace = await any_agent_instance.run_async(task)
            content = str(trace.final_output) if trace.final_output else "No response."
            return {"messages": [AIMessage(content=content, name=name)]}
        except AnyAgentCancel as e:
            # Intentional stop (e.g. step limit) — report partial results if available
            partial = ""
            if hasattr(e, "trace") and e.trace and e.trace.final_output:
                partial = f" Partial result: {e.trace.final_output}"
            logger.warning(
                "any_agent_worker_cancelled",
                agent=name,
                framework=framework,
                reason=str(e),
            )
            return {
                "messages": [
                    AIMessage(
                        content=f"Agent '{name}' was stopped: {e}.{partial}",
                        name=name,
                    )
                ]
            }
        except Exception as e:
            logger.error(
                "any_agent_worker_failed", agent=name, framework=framework, error=str(e)
            )
            return {
                "messages": [AIMessage(content=f"Agent '{name}' encountered an error.", name=name)]
            }

    graph = StateGraph(AnyAgentState)
    graph.add_node("call", call_any_agent)
    graph.set_entry_point("call")
    graph.add_edge("call", END)

    return graph.compile(name=name)


class GraphFactory:
    """Factory that builds graphs using official langgraph-supervisor.

    This factory leverages:
    - LangChain chat models for unified LLM access
    - create_react_agent for tool-using worker agents
    - create_supervisor for automatic worker discovery and routing
    - A2A client for external agent communication

    The supervisor automatically:
    - Discovers all workers from the agents list (native + external)
    - Creates handoff tools for each worker (transfer_to_<worker>)
    - Routes tasks to appropriate workers
    - No need to hardcode worker names in prompts!
    """

    def __init__(
        self,
        config: Config,
        agent_registry: AgentRegistry,
        llm_factory: LLMFactory,
        tool_registry: ToolRegistry,
        a2a_client: A2AClient | None = None,
    ):
        """
        Initialize the factory.

        Args:
            config: Full application configuration.
            agent_registry: Registry of configured agents.
            llm_factory: Factory for creating LLM instances.
            tool_registry: Registry of available tools.
            a2a_client: Optional A2A client for external agents.
        """
        self._config = config
        self._agent_registry = agent_registry
        self._llm_factory = llm_factory
        self._tool_registry = tool_registry
        self._graph_config = config.graph
        self._a2a_client = a2a_client or A2AClient()
        # Track any-agent instances for cleanup
        self._any_agent_instances: list[Any] = []

    async def cleanup_any_agents(self) -> None:
        """Clean up any-agent instances (e.g. MCP connections).

        Call this when the application is shutting down.
        """
        for instance in self._any_agent_instances:
            try:
                await instance.cleanup_async()
            except Exception as e:
                logger.warning("any_agent_cleanup_failed", error=str(e))
        self._any_agent_instances.clear()

    async def build(self) -> StateGraph:
        """
        Build the LangGraph state graph using create_supervisor.

        Returns:
            Configured StateGraph ready for compilation.
        """
        # Get supervisor config
        supervisor = self._agent_registry.get_supervisor()
        if supervisor is None:
            raise ValueError("No supervisor agent configured")

        # Get supervisor LLM
        supervisor_llm_config = self._config.llms.get(supervisor.llm_name or "default")
        if not supervisor_llm_config:
            raise ValueError(f"LLM config not found: {supervisor.llm_name}")

        supervisor_model = self._llm_factory.create_chat_model(supervisor_llm_config)

        # Build worker agents as compiled graphs
        worker_agents = []
        for name, worker in self._agent_registry.get_workers():
            # Get worker LLM
            worker_llm_config = self._config.llms.get(worker.llm_name or "default")
            if not worker_llm_config:
                logger.warning(f"LLM config not found for worker {name}, using default")
                worker_llm_config = self._config.llms.get("default")

            if not worker_llm_config:
                raise ValueError(f"No LLM config found for worker {name}")

            # Get tools for this worker
            tools = self._get_worker_tools(worker.tool_ids)

            if worker.framework == "langchain":
                # Native LangGraph path — unchanged
                worker_model = self._llm_factory.create_chat_model(worker_llm_config)
                worker_agent = create_react_agent(
                    model=worker_model,
                    tools=tools if tools else [],
                    name=name,
                    prompt=worker.system_prompt,
                )
            else:
                # Multi-framework path via any-agent
                worker_agent = await self._create_any_agent_worker(
                    name=name,
                    worker=worker,
                    llm_config=worker_llm_config,
                    tools=tools,
                )

            worker_agents.append(worker_agent)
            logger.debug(
                "created_worker_agent",
                name=name,
                framework=worker.framework,
                has_tools=bool(tools),
            )

        # Build external agent wrappers
        external_agents = []
        for name, external in self._agent_registry.get_externals():
            if external.import_mode == "node":
                # Create wrapper graph for external agent
                external_graph = create_external_agent_graph(
                    external=external, a2a_client=self._a2a_client
                )
                external_agents.append(external_graph)
                logger.debug("created_external_agent", name=external.node_id)

        # Combine native workers and external agents
        all_agents = worker_agents + external_agents

        # Create supervisor with automatic worker discovery
        # The supervisor will automatically create handoff tools for each agent
        supervisor_tools = [create_send_message_tool()]

        workflow = create_supervisor(
            agents=all_agents,
            model=supervisor_model,
            tools=supervisor_tools,
            prompt=supervisor.system_prompt,  # No need to list workers here!
            supervisor_name="supervisor",
            output_mode="full_history",
        )

        logger.info(
            "built_supervisor_graph",
            native_workers=len(worker_agents),
            external_agents=len(external_agents),
            total_agents=len(all_agents),
        )

        return workflow

    async def compile(self, checkpointer: Any = None) -> Any:
        """Build and compile the graph."""
        workflow = await self.build()
        return workflow.compile(checkpointer=checkpointer)

    def _get_worker_tools(self, tool_ids: list[str] | None) -> list[BaseTool]:
        """Get LangChain tools for a worker."""
        if not tool_ids:
            return []

        tools = []
        for tool_id in tool_ids:
            tool = self._tool_registry.get(tool_id)
            if tool:
                # Convert to LangChain tool
                lc_tool = self._convert_to_langchain_tool(tool)
                tools.append(lc_tool)
            else:
                logger.warning("tool_not_found", tool_id=tool_id)

        return tools

    def _convert_to_langchain_tool(self, tool: Any) -> BaseTool:
        """Convert a MAOS tool to a LangChain tool."""
        from pydantic import Field, create_model

        # Build Pydantic model from tool's JSON schema
        field_definitions = {}
        schema = tool.input_schema
        properties = schema.properties if hasattr(schema, "properties") else {}
        required = schema.required if hasattr(schema, "required") else []

        for prop_name, prop_schema in properties.items():
            prop_type: type = str  # Default to string
            if isinstance(prop_schema, dict):
                json_type = prop_schema.get("type", "string")
                if json_type == "integer":
                    prop_type = int
                elif json_type == "number":
                    prop_type = float
                elif json_type == "boolean":
                    prop_type = bool
                elif json_type == "array":
                    prop_type = list
                elif json_type == "object":
                    prop_type = dict

                description = prop_schema.get("description", "")
                default = prop_schema.get("default", ...)

                if prop_name in required:
                    field_definitions[prop_name] = (prop_type, Field(description=description))
                else:
                    field_definitions[prop_name] = (
                        prop_type,
                        Field(default=default, description=description),
                    )

        # Create dynamic Pydantic model for args
        if field_definitions:
            args_model = create_model(f"{tool.name}Args", **field_definitions)
        else:
            args_model = None

        async def invoke_tool(**kwargs: Any) -> str:
            try:
                result = await tool.call(kwargs)
                return str(result)
            except Exception as e:
                logger.error("tool_invocation_failed", tool=tool.name, error=str(e))
                return f"Tool '{tool.name}' encountered an error."

        tool_kwargs = {
            "coroutine": invoke_tool,
            "name": tool.name,
            "description": tool.description or f"Tool: {tool.name}",
        }

        if args_model:
            tool_kwargs["args_schema"] = args_model

        return StructuredTool.from_function(**tool_kwargs)

    async def _create_any_agent_worker(
        self,
        name: str,
        worker: WorkerAgent,
        llm_config: LLMConfig,
        tools: list[BaseTool],
    ) -> Any:
        """Create a worker agent via any-agent, wrapped in a compiled StateGraph.

        Args:
            name: Worker name.
            worker: Worker agent model.
            llm_config: LLM configuration for this worker.
            tools: LangChain tools resolved for this worker.

        Returns:
            A compiled StateGraph wrapping the any-agent worker.

        Raises:
            ImportError: If any-agent or the required framework extra is not installed.
        """
        try:
            from any_agent import AnyAgent  # noqa: F401
        except ImportError:
            raise ImportError(
                f"Agent '{name}' uses framework '{worker.framework}' which requires "
                f"any-agent. Install with: pip install 'any-agent[{worker.framework}]'"
            )

        model_id = build_any_agent_model_id(llm_config)
        api_key = os.environ.get(llm_config.api_key_env) if llm_config.api_key_env else None

        result = await create_any_agent_worker_graph(
            name=name,
            framework=worker.framework,
            model_id=model_id,
            system_prompt=worker.system_prompt,
            tools=tools,
            api_key=api_key,
            api_base=llm_config.base_url,
            model_args={"temperature": llm_config.temperature},
        )
        return result
