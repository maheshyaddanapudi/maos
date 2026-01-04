"""LangGraph-native factory using official langgraph-supervisor.

This module builds the orchestration graph using:
1. LangChain chat models (via langchain-openai, langchain-anthropic, etc.)
2. LangGraph's create_react_agent for tool-using workers
3. langgraph-supervisor's create_supervisor for automatic worker routing
4. A2A client for external agent communication

The supervisor automatically discovers workers from the agents list -
no need to hardcode worker names in system prompts.
"""

from typing import Any, Callable, Dict, List, Optional, Annotated

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langgraph.types import interrupt

from maos.config.models import Config, GraphConfig
from maos.agents.registry import AgentRegistry
from maos.agents.models import ExternalAgent
from maos.llm.factory import LLMFactory
from maos.tools.registry import ToolRegistry
from maos.graph.state import GraphState
from maos.a2a.client import A2AClient

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
        return interrupt({
            "type": "input_required",
            "prompt": message,
        })

    return StructuredTool.from_function(
        func=send_message,
        name="send_message",
        description="Send a message to the user and wait for their response. Use when you need clarification or user input.",
    )


def create_external_agent_graph(
    external: ExternalAgent,
    a2a_client: A2AClient
) -> StateGraph:
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
            response = await a2a_client.send_message(
                agent=external.discovered_agent,
                message=task
            )

            # Extract response content
            content = response.result.message.text if response.result else "No response from external agent"

            return {"messages": [AIMessage(content=content, name=external.name)]}

        except Exception as e:
            logger.error("external_agent_call_failed", agent=external.name, error=str(e))
            return {"messages": [AIMessage(content=f"Error calling {external.name}: {e}")]}

    # Build simple graph
    graph = StateGraph(ExternalState)
    graph.add_node("call", call_external)
    graph.set_entry_point("call")
    graph.add_edge("call", END)

    return graph.compile(name=external.node_id)


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
        a2a_client: Optional[A2AClient] = None,
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

    def build(self) -> StateGraph:
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

            worker_model = self._llm_factory.create_chat_model(worker_llm_config)

            # Get tools for this worker
            tools = self._get_worker_tools(worker.tool_ids)

            # Create worker agent using create_react_agent
            worker_agent = create_react_agent(
                model=worker_model,
                tools=tools if tools else [],
                name=name,
                prompt=worker.system_prompt,
            )

            worker_agents.append(worker_agent)
            logger.debug("created_worker_agent", name=name, has_tools=bool(tools))

        # Build external agent wrappers
        external_agents = []
        for name, external in self._agent_registry.get_externals():
            if external.import_mode == "node":
                # Create wrapper graph for external agent
                external_graph = create_external_agent_graph(
                    external=external,
                    a2a_client=self._a2a_client
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

    def compile(self, checkpointer=None):
        """Build and compile the graph."""
        workflow = self.build()
        return workflow.compile(checkpointer=checkpointer)

    def _get_worker_tools(self, tool_ids: Optional[List[str]]) -> List[BaseTool]:
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

    def _convert_to_langchain_tool(self, tool) -> BaseTool:
        """Convert a MAOS tool to a LangChain tool."""
        async def invoke_tool(**kwargs) -> str:
            try:
                result = await tool.invoke(kwargs)
                return str(result)
            except Exception as e:
                return f"Error: {e}"

        return StructuredTool.from_function(
            coroutine=invoke_tool,
            name=tool.name,
            description=tool.description or f"Tool: {tool.name}",
        )
