"""Supervisor node implementation."""

import json
from typing import Any, Dict, List, Optional

import structlog

from langgraph.types import interrupt

from maos.graph.state import GraphState, WorkerResult
from maos.llm.base import LLMAdapter, Message, ToolDefinition

logger = structlog.get_logger()


SUPERVISOR_SYSTEM_PROMPT_TEMPLATE = """You are a supervisor agent that routes tasks to specialist workers.

Your job is to:
1. Analyze the user's request
2. Decide which worker agent is best suited to handle it
3. Route the request to that worker
4. Evaluate worker results and decide if more work is needed or if the task is complete

Available workers:
{roster}

You MUST respond with a JSON object containing:
- "reasoning": Brief explanation of your decision
- "next": Either a worker name from the roster, or "END" if task is complete
- "message": Optional message to the user (only if you need to communicate something)

If the user's request is ambiguous or you need clarification, use the send_message tool to ask the user.

{custom_instructions}
"""


class SupervisorNode:
    """Supervisor node for routing decisions."""

    def __init__(
        self,
        llm: LLMAdapter,
        roster: List[str],
        system_prompt: str = "",
        max_iterations: int = 12
    ):
        """
        Initialize the supervisor node.

        Args:
            llm: LLM adapter for reasoning.
            roster: List of worker names.
            system_prompt: Custom system prompt additions.
            max_iterations: Maximum routing iterations.
        """
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

    async def run(self, state: GraphState) -> Dict[str, Any]:
        """
        Execute supervisor logic.

        Args:
            state: Current graph state.

        Returns:
            State updates.
        """
        iteration = state.get("iteration", 0) + 1

        # Check iteration limit
        if iteration > self._max_iterations:
            logger.warning(
                "max_iterations_exceeded",
                iterations=iteration,
                max=self._max_iterations
            )
            return {
                "next": "END",
                "done": True,
                "iteration": iteration,
                "messages": [{
                    "role": "assistant",
                    "content": "Maximum iterations reached. Stopping execution."
                }]
            }

        # Build the prompt
        messages = self._build_messages(state)

        # Invoke LLM
        try:
            response = await self._llm.invoke(messages, tools=self._tools)
        except Exception as e:
            logger.error("supervisor_llm_error", error=str(e))
            return {
                "next": "END",
                "done": True,
                "iteration": iteration,
                "messages": [{
                    "role": "assistant",
                    "content": f"Error in supervisor: {str(e)}"
                }]
            }

        # Check for tool calls (send_message)
        if response.has_tool_calls:
            for tc in response.tool_calls:
                if tc.name == "send_message":
                    # Interrupt the graph for user input
                    user_response = interrupt({
                        "type": "input_required",
                        "prompt": tc.arguments.get("message", ""),
                        "thread_id": state.get("thread_id")
                    })

                    # When resumed, add the conversation
                    return {
                        "iteration": iteration,
                        "messages": [
                            {"role": "assistant", "content": tc.arguments.get("message", "")},
                            {"role": "user", "content": user_response}
                        ]
                    }

        # Parse routing decision from response
        decision = self._parse_decision(response.content)

        logger.info(
            "supervisor_decision",
            next=decision["next"],
            reasoning=decision.get("reasoning", ""),
            iteration=iteration
        )

        # Build state updates
        updates: Dict[str, Any] = {
            "next": decision["next"],
            "iteration": iteration
        }

        if decision["next"] == "END":
            updates["done"] = True
            if decision.get("message"):
                updates["messages"] = [{
                    "role": "assistant",
                    "content": decision["message"]
                }]
        else:
            # Routing message
            if decision.get("message"):
                updates["messages"] = [{
                    "role": "assistant",
                    "content": decision["message"]
                }]

        return updates

    def _build_messages(self, state: GraphState) -> List[Message]:
        """Build message list for LLM."""
        # Create roster description
        roster_desc = "\n".join(f"- {name}" for name in self._roster)

        # System prompt
        system = SUPERVISOR_SYSTEM_PROMPT_TEMPLATE.format(
            roster=roster_desc,
            custom_instructions=self._system_prompt
        )

        messages = [Message.system(system)]

        # Add conversation history
        for msg in state.get("messages", []):
            if isinstance(msg, dict):
                messages.append(Message(
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                    name=msg.get("name")
                ))

        # Add last result context if available
        last_result = state.get("last_result")
        if last_result:
            if isinstance(last_result, WorkerResult):
                messages.append(Message(
                    role="assistant",
                    content=f"[Result from {last_result.from_agent}]: {last_result.content}",
                    name=last_result.from_agent
                ))
            elif isinstance(last_result, dict):
                messages.append(Message(
                    role="assistant",
                    content=f"[Result from {last_result.get('from_agent', 'worker')}]: {last_result.get('output', {}).get('content', '')}",
                    name=last_result.get('from_agent')
                ))

        return messages

    def _parse_decision(self, content: str) -> Dict[str, Any]:
        """Parse routing decision from LLM response."""
        # Try to parse as JSON
        try:
            # Find JSON in response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                decision = json.loads(json_str)
                return {
                    "next": decision.get("next", "END"),
                    "reasoning": decision.get("reasoning", ""),
                    "message": decision.get("message")
                }
        except json.JSONDecodeError:
            pass

        # Fall back to keyword detection
        content_lower = content.lower()

        # Check for END
        if "end" in content_lower or "complete" in content_lower or "done" in content_lower:
            return {"next": "END", "reasoning": content, "message": content}

        # Check for worker names
        for worker in self._roster:
            if worker.lower() in content_lower:
                return {"next": worker, "reasoning": content}

        # Default to first worker or END
        if self._roster:
            return {"next": self._roster[0], "reasoning": f"Defaulting to {self._roster[0]}"}

        return {"next": "END", "reasoning": "No workers available"}

    @property
    def roster(self) -> List[str]:
        """Get the current roster."""
        return self._roster

    def update_roster(self, roster: List[str]) -> None:
        """Update the roster."""
        self._roster = roster
