"""
MAOS Graph Factory.

Constructs LangGraph with supervisor, workers, and external nodes.
"""

from typing import Any

import structlog
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from maos.a2a.client import A2AClient
from maos.a2a.models import DiscoveredAgent
from maos.agents.registry import AgentRegistry
from maos.config.models import GraphConfig
from maos.graph.nodes.external import ExternalAgentNode
from maos.graph.nodes.supervisor import SupervisorNode
from maos.graph.nodes.worker import NativeWorkerNode
from maos.graph.state import GraphState
from maos.llm.registry import LLMRegistry

log = structlog.get_logger()


class GraphFactory:
    """Factory for building LangGraph."""

    def __init__(
        self,
        llm_registry: LLMRegistry,
        agent_registry: AgentRegistry,
        graph_config: GraphConfig,
        external_agents: list[DiscoveredAgent] | None = None,
        a2a_client: A2AClient | None = None,
    ):
        self._llm_registry = llm_registry
        self._agent_registry = agent_registry
        self._graph_config = graph_config
        self._external_agents = external_agents or []
        self._a2a_client = a2a_client

    def build(self, checkpointer: Any = None):
        """Build and compile the LangGraph.

        Args:
            checkpointer: Optional checkpointer for state persistence

        Returns:
            Compiled LangGraph
        """
        log.info("building_graph")

        # Create StateGraph
        graph = StateGraph(GraphState)

        # Get supervisor and workers
        supervisor = self._agent_registry.get_supervisor()
        workers = self._agent_registry.get_workers()

        if not supervisor:
            raise ValueError("No supervisor agent configured")

        # Build roster of all available workers
        roster = list(workers.keys())

        # Add external agents to roster
        for ext in self._external_agents:
            roster.append(f"ext::{ext.card.name}")

        log.debug("graph_roster", roster=roster)

        # Create supervisor node
        supervisor_llm = self._llm_registry.get_or_default(supervisor.llm_name)
        supervisor_node = SupervisorNode(
            llm=supervisor_llm,
            roster=roster,
            system_prompt=supervisor.system_prompt,
            max_iterations=self._graph_config.max_iterations,
        )

        # Add supervisor node
        graph.add_node("supervisor", supervisor_node.run)

        # Add native worker nodes
        for name, agent in workers.items():
            worker_node = NativeWorkerNode(
                agent=agent,
                timeout=self._graph_config.timeouts.worker_seconds,
            )
            graph.add_node(name, worker_node.run)
            log.debug("added_worker_node", name=name)

        # Add external agent nodes
        if self._a2a_client:
            for ext in self._external_agents:
                node_name = f"ext::{ext.card.name}"
                external_node = ExternalAgentNode(
                    agent=ext,
                    client=self._a2a_client,
                    timeout=self._graph_config.timeouts.external_agent_seconds,
                )
                graph.add_node(node_name, external_node.run)
                log.debug("added_external_node", name=node_name)

        # Create routing function
        def route_from_supervisor(state: GraphState) -> str:
            """Route from supervisor to next node."""
            next_node = state.get("next")

            if next_node == "END" or state.get("done"):
                return END

            if next_node and next_node in roster:
                return next_node

            # Default to END if no valid route
            return END

        # Add conditional edges from supervisor
        all_targets = {name: name for name in roster}
        all_targets[END] = END

        graph.add_conditional_edges(
            "supervisor",
            route_from_supervisor,
            all_targets,
        )

        # Add edges from all workers back to supervisor
        for name in workers:
            graph.add_edge(name, "supervisor")

        for ext in self._external_agents:
            node_name = f"ext::{ext.card.name}"
            graph.add_edge(node_name, "supervisor")

        # Set entry point
        graph.set_entry_point("supervisor")

        # Use provided checkpointer or create memory saver
        if checkpointer is None:
            checkpointer = MemorySaver()

        # Compile
        compiled = graph.compile(checkpointer=checkpointer)

        log.info(
            "graph_built",
            worker_count=len(workers),
            external_count=len(self._external_agents),
        )

        return compiled

    def build_roster_prompt(self) -> str:
        """Build roster string for supervisor prompt.

        Returns:
            Formatted roster string
        """
        lines = []

        # Native workers
        workers = self._agent_registry.get_workers()
        for name, agent in workers.items():
            desc = agent.description or f"Worker agent: {name}"
            tools = ", ".join(agent.get_tool_names()) if agent.tools else "No tools"
            lines.append(f"- {name}: {desc} (Tools: {tools})")

        # External agents
        for ext in self._external_agents:
            desc = ext.card.description or f"External agent: {ext.card.name}"
            skills = ", ".join(ext.card.skill_names) if ext.card.skills else "General"
            lines.append(f"- ext::{ext.card.name}: {desc} (Skills: {skills})")

        return "\n".join(lines)
