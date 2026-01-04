"""LangGraph-native factory using prebuilt components.

This module builds the orchestration graph using:
1. LangChain chat models (via langchain-openai, langchain-anthropic, etc.)
2. LangGraph's create_react_agent for tool-using workers
3. Conditional edges for supervisor routing

This is the recommended approach as it uses battle-tested LangGraph
patterns rather than custom implementations.
"""

from typing import Any, Callable, Dict, List, Optional, Sequence

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent, ToolNode
from langgraph.types import interrupt

from maos.config.models import Config, GraphConfig
from maos.agents.registry import AgentRegistry
from maos.llm.factory import LLMFactory
from maos.tools.registry import ToolRegistry
from maos.graph.state import GraphState

logger = structlog.get_logger()


def create_langchain_tool(
    name: str,
    description: str,
    func: Callable,
    args_schema: Optional[dict] = None
) -> BaseTool:
    """Create a LangChain-compatible tool from a function."""
    return StructuredTool.from_function(
        func=func,
        name=name,
        description=description,
    )


class GraphFactory:
    """Factory that builds graphs using LangGraph prebuilt components.

    This factory leverages:
    - LangChain chat models for unified LLM access
    - create_react_agent for tool-using worker agents
    - Standard LangGraph patterns for supervisor routing

    Benefits:
    - Battle-tested code from LangGraph team
    - Native streaming support
    - Built-in tool calling
    - Proper state management
    """

    def __init__(
        self,
        config: Config,
        agent_registry: AgentRegistry,
        llm_factory: LLMFactory,
        tool_registry: ToolRegistry,
    ):
        """
        Initialize the factory.

        Args:
            config: Full application configuration.
            agent_registry: Registry of configured agents.
            llm_factory: Factory for creating LLM instances.
            tool_registry: Registry of available tools.
        """
        self._config = config
        self._agent_registry = agent_registry
        self._llm_factory = llm_factory
        self._tool_registry = tool_registry
        self._graph_config = config.graph

    def build(self) -> StateGraph:
        """
        Build the LangGraph state graph.

        Returns:
            Configured StateGraph ready for compilation.
        """
        graph = StateGraph(GraphState)

        # Get supervisor config
        supervisor = self._agent_registry.get_supervisor()
        if supervisor is None:
            raise ValueError("No supervisor agent configured")

        # Get supervisor LLM as LangChain chat model
        supervisor_llm_config = self._config.llms.get(supervisor.llm_name or "default")
        if not supervisor_llm_config:
            raise ValueError(f"LLM config not found: {supervisor.llm_name}")

        supervisor_model = self._llm_factory.create_chat_model(supervisor_llm_config)

        # Build roster of workers
        roster = self._agent_registry.get_roster()

        # Create supervisor node
        supervisor_node = self._create_supervisor_node(
            model=supervisor_model,
            roster=roster,
            system_prompt=supervisor.system_prompt,
            max_iterations=self._graph_config.max_iterations
        )
        graph.add_node("supervisor", supervisor_node)

        # Create worker nodes
        for name, worker in self._agent_registry.get_workers():
            # Get worker LLM
            worker_llm_config = self._config.llms.get(worker.llm_name or "default")
            if not worker_llm_config:
                logger.warning(f"LLM config not found for worker {name}, using default")
                worker_llm_config = self._config.llms.get("default")

            worker_model = self._llm_factory.create_chat_model(worker_llm_config)

            # Get tools for this worker
            tools = self._get_worker_tools(worker.tool_ids)

            # Create worker node using create_react_agent if it has tools
            if tools:
                worker_agent = create_react_agent(
                    model=worker_model,
                    tools=tools,
                    prompt=worker.system_prompt,
                )
                # Wrap in a function that adapts state
                worker_node = self._wrap_react_agent(name, worker_agent)
            else:
                # Simple worker without tools
                worker_node = self._create_simple_worker(
                    name=name,
                    model=worker_model,
                    system_prompt=worker.system_prompt
                )

            graph.add_node(name, worker_node)
            graph.add_edge(name, "supervisor")
            logger.debug("added_worker_node", name=name, has_tools=bool(tools))

        # Add conditional routing from supervisor
        routing_map = {name: name for name in roster}
        routing_map["END"] = END

        def route_from_supervisor(state: GraphState) -> str:
            next_node = state.get("next", "END")
            if next_node in routing_map:
                return next_node
            return "END"

        graph.add_conditional_edges("supervisor", route_from_supervisor, routing_map)
        graph.set_entry_point("supervisor")

        logger.info(
            "built_langgraph_native",
            workers=len(roster),
            max_iterations=self._graph_config.max_iterations
        )

        return graph

    def compile(self, checkpointer=None):
        """Build and compile the graph."""
        graph = self.build()
        return graph.compile(checkpointer=checkpointer)

    def _create_supervisor_node(
        self,
        model: BaseChatModel,
        roster: List[str],
        system_prompt: str,
        max_iterations: int
    ) -> Callable:
        """Create the supervisor node function."""

        # Create the send_message tool for human-in-the-loop
        def send_message(message: str) -> str:
            """Send a message to the user and wait for response."""
            # This will be handled by interrupt() in the actual call
            return message

        send_message_tool = StructuredTool.from_function(
            func=send_message,
            name="send_message",
            description="Send a message to the user and wait for their response. Use when you need clarification or user input.",
        )

        # Create routing tools (one per worker + END)
        routing_tools = []
        for worker_name in roster:
            def make_route_func(name: str):
                def route_to_worker(reason: str = "") -> str:
                    """Route to this worker."""
                    return name
                route_to_worker.__name__ = f"route_to_{name}"
                route_to_worker.__doc__ = f"Route the task to {name} worker. Provide reasoning."
                return route_to_worker

            routing_tools.append(StructuredTool.from_function(
                func=make_route_func(worker_name),
                name=f"route_to_{worker_name}",
                description=f"Route the task to the {worker_name} worker.",
            ))

        def finish_task(final_response: str) -> str:
            """Mark the task as complete with a final response."""
            return "END"

        routing_tools.append(StructuredTool.from_function(
            func=finish_task,
            name="finish_task",
            description="Mark the task as complete. Use this when the task is done.",
        ))

        all_tools = [send_message_tool] + routing_tools

        # Bind tools to model
        model_with_tools = model.bind_tools(all_tools)

        async def supervisor_node(state: GraphState) -> Dict[str, Any]:
            """Supervisor routing logic."""
            iteration = state.get("iteration", 0) + 1

            # Check iteration limit
            if iteration > max_iterations:
                return {
                    "next": "END",
                    "done": True,
                    "iteration": iteration,
                }

            # Build messages
            messages = [
                SystemMessage(content=f"{system_prompt}\n\nAvailable workers: {', '.join(roster)}")
            ]

            for msg in state.get("messages", []):
                if isinstance(msg, dict):
                    # Handle dict-format messages
                    if msg.get("role") == "user":
                        messages.append(HumanMessage(content=msg.get("content", "")))
                    elif msg.get("role") == "assistant":
                        messages.append(AIMessage(content=msg.get("content", "")))
                elif isinstance(msg, HumanMessage):
                    messages.append(msg)
                elif isinstance(msg, AIMessage):
                    messages.append(msg)
                elif hasattr(msg, 'type') and hasattr(msg, 'content'):
                    # Handle any LangChain-style message
                    if msg.type == "human":
                        messages.append(HumanMessage(content=msg.content))
                    elif msg.type == "ai":
                        messages.append(AIMessage(content=msg.content))

            # Add last result context
            last_result = state.get("last_result")
            if last_result:
                content = last_result.get("output", {}).get("content", "") if isinstance(last_result, dict) else str(last_result)
                from_agent = last_result.get("from_agent", "worker") if isinstance(last_result, dict) else "worker"
                messages.append(AIMessage(content=f"[Result from {from_agent}]: {content}"))

            # Invoke model
            response = await model_with_tools.ainvoke(messages)

            # Check for tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tc in response.tool_calls:
                    tool_name = tc.get("name", "")

                    if tool_name == "send_message":
                        # Human-in-the-loop interrupt
                        user_response = interrupt({
                            "type": "input_required",
                            "prompt": tc.get("args", {}).get("message", ""),
                            "thread_id": state.get("thread_id")
                        })
                        return {
                            "iteration": iteration,
                            "messages": [
                                {"role": "assistant", "content": tc.get("args", {}).get("message", "")},
                                {"role": "user", "content": user_response}
                            ]
                        }

                    elif tool_name.startswith("route_to_"):
                        worker_name = tool_name.replace("route_to_", "")
                        return {
                            "next": worker_name,
                            "iteration": iteration,
                        }

                    elif tool_name == "finish_task":
                        return {
                            "next": "END",
                            "done": True,
                            "iteration": iteration,
                        }

            # Default: end if no routing decision
            return {
                "next": "END",
                "done": True,
                "iteration": iteration,
            }

        return supervisor_node

    def _wrap_react_agent(self, name: str, agent) -> Callable:
        """Wrap a react agent to work with our state format."""

        async def worker_node(state: GraphState) -> Dict[str, Any]:
            """Execute the react agent."""
            from maos.graph.state import WorkerResult, ResultOutput, ResultType

            task = state.get("task", "")

            try:
                # Invoke the react agent
                result = await agent.ainvoke({
                    "messages": [HumanMessage(content=task)]
                })

                # Extract final message
                messages = result.get("messages", [])
                final_content = ""
                if messages:
                    last_msg = messages[-1]
                    if hasattr(last_msg, 'content'):
                        final_content = last_msg.content

                worker_result = WorkerResult(
                    from_agent=name,
                    output=ResultOutput(
                        type=ResultType.TEXT,
                        content=final_content
                    )
                )

                return {
                    "last_result": worker_result,
                    "messages": [worker_result.to_message()]
                }

            except Exception as e:
                logger.error("worker_execution_failed", worker=name, error=str(e))
                return {
                    "last_result": WorkerResult(
                        from_agent=name,
                        output=ResultOutput(
                            type=ResultType.ERROR,
                            content=f"Error: {str(e)}"
                        )
                    )
                }

        return worker_node

    def _create_simple_worker(
        self,
        name: str,
        model: BaseChatModel,
        system_prompt: str
    ) -> Callable:
        """Create a simple worker without tools."""

        async def worker_node(state: GraphState) -> Dict[str, Any]:
            """Simple worker that just uses the LLM."""
            from maos.graph.state import WorkerResult, ResultOutput, ResultType

            task = state.get("task", "")

            try:
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=task)
                ]

                response = await model.ainvoke(messages)
                content = response.content if isinstance(response.content, str) else ""

                worker_result = WorkerResult(
                    from_agent=name,
                    output=ResultOutput(
                        type=ResultType.TEXT,
                        content=content
                    )
                )

                return {
                    "last_result": worker_result,
                    "messages": [worker_result.to_message()]
                }

            except Exception as e:
                logger.error("worker_execution_failed", worker=name, error=str(e))
                return {
                    "last_result": WorkerResult(
                        from_agent=name,
                        output=ResultOutput(
                            type=ResultType.ERROR,
                            content=f"Error: {str(e)}"
                        )
                    )
                }

        return worker_node

    def _get_worker_tools(self, tool_ids: List[str]) -> List[BaseTool]:
        """Get LangChain tools for a worker."""
        tools = []
        for tool_id in tool_ids:
            tool = self._tool_registry.get(tool_id)
            if tool:
                # Convert our tool to LangChain tool
                lc_tool = StructuredTool.from_function(
                    func=lambda **kwargs: tool.execute(**kwargs),
                    name=tool.name,
                    description=tool.description,
                    coroutine=lambda **kwargs: tool.execute_async(**kwargs) if hasattr(tool, 'execute_async') else None,
                )
                tools.append(lc_tool)
        return tools
