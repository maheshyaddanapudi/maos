"""Critique round — structured debate among House MD team members.

Implements the cross-examination phase of the differential diagnosis protocol.
Each agent proposes, others challenge, proposers defend.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from maos.house_md.graphs.states import DiagnosticState
from maos.house_md.memory.whiteboard import Whiteboard


async def run_critique_round(
    state: DiagnosticState,
    agent_nodes: dict[str, Any],
) -> DiagnosticState:
    """Run a single round of critique/debate among active agents.

    Each agent reviews the current whiteboard and either supports,
    challenges, or adds new hypotheses. The result is an updated
    whiteboard with refined confidence scores.

    Args:
        state: Current diagnostic state with whiteboard and messages.
        agent_nodes: Dict mapping agent names to callable async functions
            that accept state and return updated state dicts.

    Returns:
        Updated DiagnosticState with critique results merged.
    """
    whiteboard = Whiteboard.from_dict(state["whiteboard"])
    active_team = state.get("active_team", [])
    new_hypotheses: list[dict[str, Any]] = []
    agent_beliefs: dict[str, Any] = dict(state.get("agent_beliefs", {}))
    new_messages: list[Any] = []

    for agent_name in active_team:
        if agent_name not in agent_nodes:
            continue

        critique_prompt = _build_critique_prompt(whiteboard, agent_name)
        critique_state = {
            **state,
            "messages": list(state["messages"]) + [
                HumanMessage(content=critique_prompt),
            ],
        }

        agent_fn = agent_nodes[agent_name]
        if hasattr(agent_fn, "ainvoke"):
            result = await agent_fn.ainvoke(critique_state)
        elif callable(agent_fn):
            result = await agent_fn(critique_state)
        else:
            continue

        response_messages = result.get("messages", [])
        if response_messages:
            last_msg = response_messages[-1]
            content = (
                last_msg.content
                if hasattr(last_msg, "content")
                else str(last_msg)
            )

            agent_beliefs[agent_name] = {
                "last_response": content[:500],
                "iteration": state.get("iteration", 0),
            }

            new_messages.append(
                AIMessage(
                    content=f"[{agent_name}] {content}",
                    name=agent_name,
                )
            )

    whiteboard.advance_phase("post_critique")

    return {
        **state,
        "messages": new_messages,
        "hypotheses": new_hypotheses,
        "agent_beliefs": agent_beliefs,
        "whiteboard": whiteboard.to_dict(),
    }


def _build_critique_prompt(whiteboard: Whiteboard, agent_name: str) -> str:
    """Build a critique prompt for a specific agent."""
    summary = whiteboard.summary()
    return (
        f"You are {agent_name} on the diagnostic team. "
        f"Review the current whiteboard state and provide your analysis.\n\n"
        f"{summary}\n\n"
        f"Based on your role and expertise:\n"
        f"1. Which hypotheses do you support or challenge? Why?\n"
        f"2. What evidence or tests would you recommend?\n"
        f"3. Are we missing anything?\n"
        f"Be specific and reference the hypotheses by name."
    )
