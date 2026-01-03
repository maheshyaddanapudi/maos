"""Factory for building LangGraph."""

from typing import Any, Callable, Dict, List, Optional

import structlog
from langgraph.graph import END, StateGraph

from maos.config.models import Config, GraphConfig
from maos.agents.registry import AgentRegistry
from maos.agents.models import ExternalAgent
from maos.llm.registry import LLMRegistry
from maos.tools.registry import ToolRegistry
from maos.a2a.client import A2AClient
from maos.graph.state import GraphState
from maos.graph.nodes.supervisor import SupervisorNode
from maos.graph.nodes.worker import NativeWorkerNode
from maos.graph.nodes.external import ExternalAgentNode

logger = structlog.get_logger()


class GraphFactory:
    """Factory for building LangGraph."""

    def __init__(
        self,
        agent_registry: AgentRegistry,
        llm_registry: LLMRegistry,
        tool_registry: ToolRegistry,
        graph_config: GraphConfig,
        a2a_client: Optional[A2AClient] = None
    ):
        """
        Initialize the graph factory.

        Args:
            agent_registry: Registry of all agents.
            llm_registry: Registry of LLM adapters.
            tool_registry: Registry of tools.
            graph_config: Graph configuration.
            a2a_client: A2A client for external agents.
        """
        self._agent_registry = agent_registry
        self._llm_registry = llm_registry
        self._tool_registry = tool_registry
        self._graph_config = graph_config
        self._a2a_client = a2a_client or A2AClient()

        # Node instances
        self._supervisor_node: Optional[SupervisorNode] = None
        self._worker_nodes: Dict[str, NativeWorkerNode] = {}
        self._external_nodes: Dict[str, ExternalAgentNode] = {}

    def build(self) -> StateGraph:
        """
        Build and compile the LangGraph.

        Returns:
            Compiled StateGraph.
        """
        # Create state graph
        graph = StateGraph(GraphState)

        # Get all worker names for roster
        roster = self._agent_registry.get_roster()

        # Create and add supervisor node
        supervisor = self._agent_registry.get_supervisor()
        if supervisor is None:
            raise ValueError("No supervisor agent configured")

        self._supervisor_node = SupervisorNode(
            llm=supervisor.llm,
            roster=roster,
            system_prompt=supervisor.system_prompt,
            max_iterations=self._graph_config.max_iterations
        )

        async def supervisor_fn(state: GraphState) -> Dict[str, Any]:
            return await self._supervisor_node.run(state)

        graph.add_node("supervisor", supervisor_fn)

        # Create and add native worker nodes
        for name, worker in self._agent_registry.get_workers():
            llm = self._llm_registry.get_or_default(worker.llm_name)

            # Get tools for this worker
            tools = []
            for tool_id in worker.tool_ids:
                tool = self._tool_registry.get(tool_id)
                if tool:
                    tools.append(tool)

            worker_node = NativeWorkerNode(
                agent=worker,
                llm=llm,
                tools=tools,
                timeout=worker.timeout_seconds
            )
            self._worker_nodes[name] = worker_node

            # Create node function with closure
            async def worker_fn(state: GraphState, node=worker_node) -> Dict[str, Any]:
                return await node.run(state)

            graph.add_node(name, worker_fn)
            logger.debug("added_worker_node", name=name)

        # Create and add external agent nodes
        for name, external in self._agent_registry.get_externals():
            if external.import_mode == "node":
                external_node = ExternalAgentNode(
                    agent=external,
                    a2a_client=self._a2a_client,
                    timeout=self._graph_config.timeouts.external_agent_call_seconds
                )
                self._external_nodes[external.node_id] = external_node

                async def external_fn(state: GraphState, node=external_node) -> Dict[str, Any]:
                    return await node.run(state)

                graph.add_node(external.node_id, external_fn)
                logger.debug("added_external_node", name=external.node_id)

        # Add conditional edges from supervisor
        routing_map = {name: name for name in self._worker_nodes}
        routing_map.update({node_id: node_id for node_id in self._external_nodes})
        routing_map["END"] = END

        def route_from_supervisor(state: GraphState) -> str:
            next_node = state.get("next", "END")
            if next_node in routing_map:
                return next_node
            return "END"

        graph.add_conditional_edges(
            "supervisor",
            route_from_supervisor,
            routing_map
        )

        # Add edges from workers back to supervisor
        for name in self._worker_nodes:
            graph.add_edge(name, "supervisor")

        for node_id in self._external_nodes:
            graph.add_edge(node_id, "supervisor")

        # Set entry point
        graph.set_entry_point("supervisor")

        logger.info(
            "built_langgraph",
            workers=len(self._worker_nodes),
            externals=len(self._external_nodes),
            max_iterations=self._graph_config.max_iterations
        )

        return graph

    def compile(self, checkpointer=None) -> Any:
        """
        Build and compile the graph.

        Args:
            checkpointer: Optional checkpointer for persistence.

        Returns:
            Compiled graph.
        """
        graph = self.build()
        return graph.compile(checkpointer=checkpointer)

    @property
    def supervisor_node(self) -> Optional[SupervisorNode]:
        """Get the supervisor node instance."""
        return self._supervisor_node

    @property
    def worker_nodes(self) -> Dict[str, NativeWorkerNode]:
        """Get all worker node instances."""
        return self._worker_nodes

    @property
    def external_nodes(self) -> Dict[str, ExternalAgentNode]:
        """Get all external node instances."""
        return self._external_nodes
