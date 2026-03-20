"""House MD graph factory — builds the diagnostic graph with real agents.

Wires together:
- LangGraph react agents (create_react_agent) for each team member
- PersonalityWrapper for cognitive bias injection
- DiagnosticState graph with phase-based routing
- Critique rounds for structured team debate
- Whiteboard for shared hypothesis tracking

This factory is invoked by GraphFactory when config.graph.mode == "house_md".
In default "supervisor" mode, GraphFactory uses langgraph-supervisor instead.
"""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent

from maos.house_md.graphs.critique_round import run_critique_round
from maos.house_md.graphs.states import DiagnosticPhase, DiagnosticState
from maos.house_md.memory.whiteboard import Whiteboard
from maos.house_md.personalities.base import PersonalityWrapper, TeamContext
from maos.house_md.personalities.team import PERSONALITY_CONFIGS

logger = structlog.get_logger()

MAX_ITERATIONS = 5


class HouseMDGraphFactory:
    """Builds the diagnostic graph with real LLM-backed agents.

    Unlike the standalone ``create_diagnostic_graph()`` which uses stub
    messages, this factory:

    1. Creates ``create_react_agent`` workers for each team member
    2. Wraps them with ``PersonalityWrapper`` (cognitive biases, Big Five)
    3. Builds a ``StateGraph[DiagnosticState]`` where nodes invoke real agents
    4. Runs ``critique_round`` during the differential phase
    5. Uses ``Whiteboard`` for shared hypothesis tracking
    """

    def __init__(
        self,
        config,
        agent_registry,
        llm_factory,
        tool_registry,
    ):
        self._config = config
        self._agent_registry = agent_registry
        self._llm_factory = llm_factory
        self._tool_registry = tool_registry
        self._max_iterations = config.graph.max_iterations or MAX_ITERATIONS

    def build(self) -> StateGraph:
        """Build the House MD diagnostic StateGraph with real agents."""
        # Create LLM-backed agent runnables and wrap with personalities
        agent_runnables = self._create_agent_runnables()
        personality_agents = self._wrap_with_personalities(agent_runnables)

        # Build the diagnostic graph with closures over real agents
        workflow = StateGraph(DiagnosticState)

        max_iterations = self._max_iterations

        # ── Node: intake ─────────────────────────────────────────────
        async def intake_node(state: DiagnosticState) -> dict[str, Any]:
            """House analyzes the case and records initial symptoms."""
            whiteboard = Whiteboard.from_dict(state["whiteboard"])
            iteration = state.get("iteration", 0)
            whiteboard.advance_phase(DiagnosticPhase.INTAKE.value, iteration)

            messages = list(state["messages"])
            last_user_msg = ""
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    last_user_msg = msg.content
                    break
                if isinstance(msg, dict) and msg.get("role") == "user":
                    last_user_msg = msg["content"]
                    break

            symptoms = list(state.get("symptoms", []))
            if last_user_msg and last_user_msg not in symptoms:
                symptoms.append(last_user_msg)
                whiteboard.add_symptom(last_user_msg)

            # Call House agent for intake analysis
            house = personality_agents.get("house")
            if house:
                intake_prompt = (
                    f"New case presented. Analyze these symptoms and record "
                    f"your initial assessment. Remember: everybody lies.\n\n"
                    f"Symptoms: {', '.join(symptoms)}"
                )
                result = await _invoke_agent(
                    house, state, intake_prompt, "house"
                )
                response_content = _extract_content(result)
                intake_msg = AIMessage(
                    content=f"[House - Intake] {response_content}",
                    name="house",
                )
            else:
                intake_msg = AIMessage(
                    content=(
                        f"[House - Intake] Case presented. Initial symptoms "
                        f"recorded. Symptoms: {', '.join(symptoms)}"
                    ),
                    name="house",
                )

            return {
                "messages": [intake_msg],
                "symptoms": symptoms,
                "current_phase": DiagnosticPhase.INTAKE.value,
                "whiteboard": whiteboard.to_dict(),
            }

        # ── Node: differential ───────────────────────────────────────
        async def differential_node(state: DiagnosticState) -> dict[str, Any]:
            """Team brainstorms hypotheses via critique round."""
            whiteboard = Whiteboard.from_dict(state["whiteboard"])
            iteration = state.get("iteration", 0)
            whiteboard.advance_phase(
                DiagnosticPhase.DIFFERENTIAL.value, iteration
            )

            # Run structured critique round with real agents
            critique_result = await run_critique_round(
                state, personality_agents
            )

            # Merge critique results into whiteboard
            new_whiteboard = Whiteboard.from_dict(
                critique_result.get("whiteboard", state["whiteboard"])
            )

            return {
                "messages": critique_result.get("messages", []),
                "hypotheses": critique_result.get("hypotheses", []),
                "agent_beliefs": critique_result.get("agent_beliefs", {}),
                "current_phase": DiagnosticPhase.DIFFERENTIAL.value,
                "whiteboard": new_whiteboard.to_dict(),
            }

        # ── Node: provocation ────────────────────────────────────────
        async def provocation_node(
            state: DiagnosticState,
        ) -> dict[str, Any]:
            """House challenges, synthesizes, and provokes."""
            whiteboard = Whiteboard.from_dict(state["whiteboard"])
            iteration = state.get("iteration", 0) + 1
            whiteboard.advance_phase(
                DiagnosticPhase.PROVOCATION.value, iteration
            )

            active = whiteboard.get_active_hypotheses()
            top = whiteboard.get_top_hypothesis()

            # Build provocation prompt based on whiteboard state
            if not active:
                context = (
                    "Nothing on the board yet. Challenge the team to propose "
                    "differentials. Be provocative."
                )
            elif len(active) == 1 and top:
                context = (
                    f"Only one hypothesis: '{top.hypothesis}'. "
                    f"It's never the obvious answer. Provoke the team to "
                    f"think of alternatives."
                )
            elif top and top.confidence > 0.8:
                context = (
                    f"Everyone seems confident about '{top.hypothesis}' "
                    f"({top.confidence:.0%}). Too confident. Challenge this. "
                    f"What are we NOT seeing?"
                )
            else:
                hyp_summary = "; ".join(
                    f"'{h.hypothesis}' ({h.confidence:.0%})"
                    for h in active[:3]
                )
                context = (
                    f"Current differentials: {hyp_summary}. "
                    f"Iteration {iteration}. Which can we rule out? "
                    f"What tests do we need?"
                )

            house = personality_agents.get("house")
            if house:
                result = await _invoke_agent(
                    house, state, context, "house"
                )
                response_content = _extract_content(result)
                prov_msg = AIMessage(
                    content=f"[House - Provocation] {response_content}",
                    name="house",
                )
            else:
                prov_msg = AIMessage(
                    content=f"[House - Provocation] {context}",
                    name="house",
                )

            return {
                "messages": [prov_msg],
                "current_phase": DiagnosticPhase.PROVOCATION.value,
                "whiteboard": whiteboard.to_dict(),
                "iteration": iteration,
            }

        # ── Node: testing ────────────────────────────────────────────
        async def testing_node(state: DiagnosticState) -> dict[str, Any]:
            """Chase runs tests to validate/rule out hypotheses."""
            whiteboard = Whiteboard.from_dict(state["whiteboard"])
            iteration = state.get("iteration", 0)
            whiteboard.advance_phase(
                DiagnosticPhase.TESTING.value, iteration
            )

            active = whiteboard.get_active_hypotheses()
            test_summary = ", ".join(h.hypothesis for h in active[:3])

            chase = personality_agents.get("chase")
            if chase:
                prompt = (
                    f"Run tests against these hypotheses: {test_summary}. "
                    f"For each, explain what test you'd run and the expected "
                    f"result. Rule out what you can."
                )
                result = await _invoke_agent(
                    chase, state, prompt, "chase"
                )
                response_content = _extract_content(result)
                test_msg = AIMessage(
                    content=f"[Chase - Testing] {response_content}",
                    name="chase",
                )
            else:
                test_msg = AIMessage(
                    content=(
                        f"[Chase - Testing] Running tests against: "
                        f"{test_summary}."
                    ),
                    name="chase",
                )

            return {
                "messages": [test_msg],
                "current_phase": DiagnosticPhase.TESTING.value,
                "whiteboard": whiteboard.to_dict(),
            }

        # ── Node: environmental ──────────────────────────────────────
        async def environmental_node(
            state: DiagnosticState,
        ) -> dict[str, Any]:
            """Thirteen investigates beyond reported symptoms."""
            whiteboard = Whiteboard.from_dict(state["whiteboard"])
            iteration = state.get("iteration", 0)
            whiteboard.advance_phase(
                DiagnosticPhase.ENVIRONMENTAL.value, iteration
            )

            thirteen = personality_agents.get("thirteen")
            if thirteen:
                prompt = (
                    "Investigate beyond the reported symptoms. Examine the "
                    "codebase context, deployment environment, git history, "
                    "and any environmental factors. What isn't the 'patient' "
                    "telling us?"
                )
                result = await _invoke_agent(
                    thirteen, state, prompt, "thirteen"
                )
                response_content = _extract_content(result)
                env_msg = AIMessage(
                    content=(
                        f"[Thirteen - Environmental] {response_content}"
                    ),
                    name="thirteen",
                )
            else:
                env_msg = AIMessage(
                    content=(
                        "[Thirteen - Environmental] Investigating beyond "
                        "the reported symptoms."
                    ),
                    name="thirteen",
                )

            return {
                "messages": [env_msg],
                "current_phase": DiagnosticPhase.ENVIRONMENTAL.value,
                "whiteboard": whiteboard.to_dict(),
            }

        # ── Node: wilson_consult ─────────────────────────────────────
        async def wilson_consult_node(
            state: DiagnosticState,
        ) -> dict[str, Any]:
            """Wilson provides cross-domain insight to unlock the case."""
            whiteboard = Whiteboard.from_dict(state["whiteboard"])
            iteration = state.get("iteration", 0)
            whiteboard.advance_phase(
                DiagnosticPhase.WILSON_CONSULT.value, iteration
            )

            symptoms = state.get("symptoms", [])
            wilson = personality_agents.get("wilson")
            if wilson:
                prompt = (
                    "House is stuck. The team has been going in circles. "
                    "Provide a cross-domain perspective. Start with "
                    "something seemingly unrelated, then make a connection "
                    "the team hasn't considered. Trigger a breakthrough.\n\n"
                    f"Current symptoms: {', '.join(symptoms)}\n"
                    f"Whiteboard: {whiteboard.summary()}"
                )
                result = await _invoke_agent(
                    wilson, state, prompt, "wilson"
                )
                response_content = _extract_content(result)
                wilson_msg = AIMessage(
                    content=f"[Wilson - Consult] {response_content}",
                    name="wilson",
                )
            else:
                wilson_msg = AIMessage(
                    content=(
                        "[Wilson - Consult] What if the problem isn't about "
                        "what you think? Look at the context."
                    ),
                    name="wilson",
                )

            return {
                "messages": [wilson_msg],
                "current_phase": DiagnosticPhase.WILSON_CONSULT.value,
                "whiteboard": whiteboard.to_dict(),
            }

        # ── Node: resolution ─────────────────────────────────────────
        async def resolution_node(
            state: DiagnosticState,
        ) -> dict[str, Any]:
            """House makes the final diagnostic call."""
            whiteboard = Whiteboard.from_dict(state["whiteboard"])
            iteration = state.get("iteration", 0)
            whiteboard.advance_phase(
                DiagnosticPhase.RESOLUTION.value, iteration
            )

            confirmed = whiteboard.get_confirmed()
            top = whiteboard.get_top_hypothesis()
            diagnosis = confirmed or top

            house = personality_agents.get("house")
            if house and diagnosis:
                prompt = (
                    f"Make your final diagnostic call. The top hypothesis "
                    f"is '{diagnosis.hypothesis}' "
                    f"(confidence: {diagnosis.confidence:.0%}). "
                    f"Evidence for: {', '.join(diagnosis.evidence_for) or 'clinical judgment'}. "
                    f"Evidence against: {', '.join(diagnosis.evidence_against) or 'none'}. "
                    f"Deliver the diagnosis and prescribe the treatment."
                )
                result = await _invoke_agent(
                    house, state, prompt, "house"
                )
                response_content = _extract_content(result)
                resolution_msg = AIMessage(
                    content=f"[House - Resolution] {response_content}",
                    name="house",
                )
                if diagnosis:
                    diagnosis.confirm()
                final_diagnosis = diagnosis.hypothesis
                confidence = diagnosis.confidence
            elif diagnosis:
                diagnosis.confirm()
                resolution_msg = AIMessage(
                    content=(
                        f"[House - Resolution] Diagnosis: "
                        f"{diagnosis.hypothesis}. "
                        f"Confidence: {diagnosis.confidence:.0%}. "
                        f"Chase, implement the fix."
                    ),
                    name="house",
                )
                final_diagnosis = diagnosis.hypothesis
                confidence = diagnosis.confidence
            else:
                resolution_msg = AIMessage(
                    content=(
                        "[House - Resolution] Inconclusive. No hypothesis "
                        "reached sufficient confidence. Recommending further "
                        "investigation."
                    ),
                    name="house",
                )
                final_diagnosis = None
                confidence = 0.0

            return {
                "messages": [resolution_msg],
                "current_phase": DiagnosticPhase.RESOLUTION.value,
                "whiteboard": whiteboard.to_dict(),
                "final_diagnosis": final_diagnosis,
                "confidence": confidence,
            }

        # ── Routing ──────────────────────────────────────────────────
        def route_after_provocation(state: DiagnosticState) -> str:
            iteration = state.get("iteration", 0)
            if iteration >= max_iterations:
                return "resolution"

            whiteboard = Whiteboard.from_dict(state["whiteboard"])
            top = whiteboard.get_top_hypothesis()

            if top and top.confidence > 0.85:
                return "resolution"

            active = whiteboard.get_active_hypotheses()
            if not active:
                return "wilson_consult"

            if not whiteboard.environmental_findings and iteration >= 2:
                return "environmental"

            return "testing"

        # ── Assemble graph ───────────────────────────────────────────
        workflow.add_node("intake", intake_node)
        workflow.add_node("differential", differential_node)
        workflow.add_node("provocation", provocation_node)
        workflow.add_node("testing", testing_node)
        workflow.add_node("environmental", environmental_node)
        workflow.add_node("wilson_consult", wilson_consult_node)
        workflow.add_node("resolution", resolution_node)

        workflow.add_edge(START, "intake")
        workflow.add_edge("intake", "differential")
        workflow.add_edge("differential", "provocation")
        workflow.add_conditional_edges(
            "provocation",
            route_after_provocation,
            {
                "testing": "testing",
                "environmental": "environmental",
                "wilson_consult": "wilson_consult",
                "resolution": "resolution",
            },
        )
        workflow.add_edge("testing", "provocation")
        workflow.add_edge("environmental", "provocation")
        workflow.add_edge("wilson_consult", "differential")
        workflow.add_edge("resolution", END)

        logger.info(
            "built_house_md_graph",
            agents=list(personality_agents.keys()),
            max_iterations=max_iterations,
        )

        return workflow

    def compile(self, checkpointer=None):
        """Build and compile the diagnostic graph."""
        workflow = self.build()
        return workflow.compile(checkpointer=checkpointer)

    def _create_agent_runnables(self) -> dict[str, Any]:
        """Create LangGraph react agent runnables for each worker."""
        from maos.graph.factory import GraphFactory

        runnables = {}

        # Create a temporary GraphFactory to reuse tool conversion logic
        graph_factory = GraphFactory(
            config=self._config,
            agent_registry=self._agent_registry,
            llm_factory=self._llm_factory,
            tool_registry=self._tool_registry,
        )

        for name, worker in self._agent_registry.get_workers():
            worker_llm_config = self._config.llms.get(
                worker.llm_name or "default"
            )
            if not worker_llm_config:
                worker_llm_config = self._config.llms.get("default")
            if not worker_llm_config:
                logger.warning(
                    "skipping_worker_no_llm", worker=name
                )
                continue

            worker_model = self._llm_factory.create_chat_model(
                worker_llm_config
            )
            tools = graph_factory._get_worker_tools(worker.tool_ids)

            agent = create_react_agent(
                model=worker_model,
                tools=tools if tools else [],
                name=name,
                prompt=worker.system_prompt,
            )
            runnables[name] = agent
            logger.debug("created_house_md_agent", name=name)

        # Also create for supervisor (House) — used in intake/provocation/resolution
        supervisor = self._agent_registry.get_supervisor()
        if supervisor:
            sup_llm_config = self._config.llms.get(
                supervisor.llm_name or "default"
            )
            if sup_llm_config:
                sup_model = self._llm_factory.create_chat_model(
                    sup_llm_config
                )
                house_agent = create_react_agent(
                    model=sup_model,
                    tools=[],
                    name=supervisor.name,
                    prompt=supervisor.system_prompt,
                )
                runnables[supervisor.name] = house_agent

        return runnables

    def _wrap_with_personalities(
        self, runnables: dict[str, Any]
    ) -> dict[str, PersonalityWrapper]:
        """Wrap each agent runnable with its House MD personality."""
        wrapped = {}
        for name, runnable in runnables.items():
            personality = PERSONALITY_CONFIGS.get(name)
            if personality:
                wrapped[name] = PersonalityWrapper(
                    base_agent=runnable,
                    personality=personality,
                )
                logger.debug(
                    "wrapped_personality",
                    agent=name,
                    biases=[
                        b.value for b in personality.cognitive_biases
                    ],
                )
            else:
                # No personality defined — wrap with minimal config
                wrapped[name] = PersonalityWrapper(
                    base_agent=runnable,
                    personality=PERSONALITY_CONFIGS.get(
                        "chase", list(PERSONALITY_CONFIGS.values())[0]
                    ),
                )
        return wrapped


async def _invoke_agent(
    agent: PersonalityWrapper,
    state: DiagnosticState,
    phase_prompt: str,
    agent_name: str,
) -> dict[str, Any]:
    """Invoke a personality-wrapped agent with phase context.

    Builds a minimal message list with whiteboard context and the
    phase-specific prompt, then invokes the wrapped agent.
    """
    whiteboard = Whiteboard.from_dict(state["whiteboard"])

    # Update team context on the wrapper
    agent.team_context = TeamContext(
        active_agents=state.get("active_team", []),
        hypotheses=[h.to_dict() for h in whiteboard.get_active_hypotheses()],
        current_phase=state.get("current_phase", "intake"),
        whiteboard=whiteboard,
    )

    # Build invocation state: original messages + phase prompt
    invoke_state = {
        "messages": list(state["messages"]) + [
            HumanMessage(content=phase_prompt),
        ],
    }

    try:
        result = await agent.invoke(invoke_state)
        return result
    except Exception as e:
        logger.error(
            "agent_invocation_failed",
            agent=agent_name,
            error=str(e),
        )
        return {
            "messages": [
                AIMessage(
                    content=f"[{agent_name}] Error: {e}",
                    name=agent_name,
                )
            ]
        }


def _extract_content(result: dict[str, Any]) -> str:
    """Extract the last AI message content from an agent result."""
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return msg.content
        if hasattr(msg, "content") and hasattr(msg, "type"):
            if msg.type == "ai":
                return msg.content
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            return msg.get("content", "")
    return str(result)
