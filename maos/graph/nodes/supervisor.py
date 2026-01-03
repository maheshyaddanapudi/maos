"""
MAOS Supervisor Node.

Implements the supervisor routing logic and send_message tool.
"""

import json
from typing import Any

import structlog
from langgraph.types import interrupt

from maos.graph.state import GraphState
from maos.llm.base import LLMAdapter, Message, ToolDefinition

log = structlog.get_logger()

# System prompt template for supervisor
SUPERVISOR_SYSTEM_PROMPT = """You are a supervisor agent that routes tasks to specialist workers.

Available workers:
{roster}

Your job is to:
1. Analyze the user's request
2. Decide which worker is best suited to handle it
3. Route to that worker OR complete the task if done

You have access to these tools:
- send_message: Send a message to the user and wait for their response. Use when you need clarification.

IMPORTANT:
- If the task is complete and you have a final answer, respond with next="END"
- If you need more information from the user, use the send_message tool
- Otherwise, route to the most appropriate worker

Respond with a JSON object:
{{
    "reasoning": "Brief explanation of your decision",
    "next": "worker_name" or "END",
    "message": "Optional message to include"
}}
"""


class SupervisorNode:
    """Supervisor node implementation."""

    def __init__(
        self,
        llm: LLMAdapter,
        roster: list[str],
        system_prompt: str | None = None,
        max_iterations: int = 12,
    ):
        self._llm = llm
        self._roster = roster
        self._system_prompt = system_prompt
        self._max_iterations = max_iterations
        self._tools = [self._create_send_message_tool()]

    def _create_send_message_tool(self) -> ToolDefinition:
        """Create the send_message tool for human-in-the-loop."""
        return ToolDefinition(
            name="send_message",
            description="Send a message to the user and wait for their response. Use when you need clarification or user input.",
            parameters={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message to send to the user"
                    }
                },
                "required": ["message"]
            }
        )

    def _build_prompt(self, state: GraphState) -> str:
        """Build the system prompt with roster."""
        roster_str = "\n".join(f"- {name}" for name in self._roster)

        if self._system_prompt:
            return self._system_prompt + f"\n\nAvailable workers:\n{roster_str}"

        return SUPERVISOR_SYSTEM_PROMPT.format(roster=roster_str)

    async def run(self, state: GraphState) -> dict[str, Any]:
        """Execute supervisor logic.

        1. Check iteration limit
        2. Build prompt with roster
        3. Invoke LLM for routing decision
        4. Handle send_message if used
        5. Return updated state with next node
        """
        iteration = state.get("iteration", 0) + 1

        log.debug(
            "supervisor_run",
            iteration=iteration,
            max_iterations=self._max_iterations,
        )

        # Check iteration limit
        if iteration > self._max_iterations:
            log.warning("max_iterations_reached", iteration=iteration)
            return {
                "next": "END",
                "done": True,
                "iteration": iteration,
                "messages": [
                    {
                        "role": "assistant",
                        "content": "I apologize, but I've reached my processing limit. Here's a summary of what we accomplished so far."
                    }
                ],
            }

        # Build messages for LLM
        system_prompt = self._build_prompt(state)
        messages = [Message(role="system", content=system_prompt)]

        # Add conversation history
        for msg in state.get("messages", []):
            if isinstance(msg, dict):
                messages.append(Message.from_dict(msg))
            elif hasattr(msg, "content"):
                messages.append(Message(
                    role=getattr(msg, "type", "user"),
                    content=msg.content,
                ))

        # Add context about last result if available
        last_result = state.get("last_result")
        if last_result:
            messages.append(Message(
                role="system",
                content=f"Previous worker '{last_result.from_agent}' returned:\n{last_result.content}"
            ))

        # Invoke LLM
        response = await self._llm.invoke(messages, self._tools)

        # Check for send_message tool call
        if response.has_tool_calls:
            for tc in response.tool_calls:
                if tc.name == "send_message":
                    return await self._handle_send_message(
                        tc.arguments.get("message", ""),
                        state,
                        iteration,
                    )

        # Parse routing decision
        decision = self._parse_routing_decision(response.content or "")

        log.info(
            "supervisor_decision",
            next=decision.get("next"),
            reasoning=decision.get("reasoning"),
        )

        # Validate next node
        next_node = decision.get("next", "END")
        if next_node != "END" and next_node not in self._roster:
            log.warning("invalid_routing_target", target=next_node)
            # Try to find closest match or default to first worker
            next_node = self._roster[0] if self._roster else "END"

        # Build response
        result: dict[str, Any] = {
            "next": next_node,
            "done": next_node == "END",
            "iteration": iteration,
        }

        # Add routing message if provided
        if decision.get("message"):
            result["messages"] = [
                {"role": "assistant", "content": decision["message"]}
            ]

        return result

    async def _handle_send_message(
        self,
        message: str,
        state: GraphState,
        iteration: int,
    ) -> dict[str, Any]:
        """Handle human-in-the-loop request using LangGraph interrupt."""
        log.info("supervisor_send_message", message=message)

        # INTERRUPT - this pauses the graph and waits for user input
        user_response = interrupt({
            "type": "input_required",
            "prompt": message,
            "thread_id": state.get("thread_id"),
        })

        # When resumed, user_response contains their input
        return {
            "messages": [
                {"role": "assistant", "content": message},
                {"role": "user", "content": user_response},
            ],
            "next": None,  # Will go back to supervisor
            "done": False,
            "iteration": iteration,
        }

    def _parse_routing_decision(self, content: str) -> dict[str, Any]:
        """Parse LLM response to extract routing decision."""
        # Try to parse as JSON
        try:
            # Find JSON in the response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # Fallback: look for worker names in content
        content_lower = content.lower()

        for worker in self._roster:
            if worker.lower() in content_lower:
                return {
                    "next": worker,
                    "reasoning": "Extracted from response",
                    "message": None,
                }

        # Check for completion indicators
        if any(word in content_lower for word in ["complete", "done", "finished", "end"]):
            return {
                "next": "END",
                "reasoning": "Task appears complete",
                "message": content,
            }

        # Default: try first worker or END
        if self._roster:
            return {
                "next": self._roster[0],
                "reasoning": "Defaulting to first worker",
                "message": None,
            }

        return {
            "next": "END",
            "reasoning": "No workers available",
            "message": content,
        }
