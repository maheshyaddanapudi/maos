"""Base personality wrapper that can wrap any existing agent.

Compatible with: LangGraph agents, MAOS workers, A2A external agents.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from langchain_core.messages import SystemMessage


class CognitiveBias(Enum):
    """Known cognitive biases that shape agent behavior."""

    CONSERVATIVE = "conservative"
    CONTRARIAN = "contrarian"
    PATTERN_MATCHING = "pattern_matching"
    RISK_TOLERANT = "risk_tolerant"
    EMPATHY_DRIVEN = "empathy_driven"
    ACTION_ORIENTED = "action_oriented"
    BY_THE_BOOK = "by_the_book"
    EVERYBODY_LIES = "everybody_lies"


BIAS_DESCRIPTIONS: dict[CognitiveBias, str] = {
    CognitiveBias.CONSERVATIVE: (
        "You prefer proven, battle-tested approaches. Question novel solutions."
    ),
    CognitiveBias.CONTRARIAN: (
        "You instinctively challenge the majority view. Play devil's advocate."
    ),
    CognitiveBias.PATTERN_MATCHING: (
        "You look for similarities to past cases. Reference precedents."
    ),
    CognitiveBias.RISK_TOLERANT: (
        "You're willing to try approaches others consider too risky."
    ),
    CognitiveBias.EMPATHY_DRIVEN: (
        "You prioritize user impact and experience above technical elegance."
    ),
    CognitiveBias.ACTION_ORIENTED: (
        "You prefer building and testing over extended analysis."
    ),
    CognitiveBias.BY_THE_BOOK: (
        "You follow established protocols and flag violations."
    ),
    CognitiveBias.EVERYBODY_LIES: (
        "You assume all inputs are incomplete or misleading. Verify everything."
    ),
}


@dataclass
class PersonalityConfig:
    """Configuration for an agent personality."""

    name: str
    role_description: str
    system_prompt_additions: str
    cognitive_biases: list[CognitiveBias] = field(default_factory=list)
    challenge_threshold: float = 0.5
    compliance_threshold: float = 0.5
    manipulation_enabled: bool = False
    big_five: dict[str, float] = field(
        default_factory=lambda: {
            "openness": 0.5,
            "conscientiousness": 0.5,
            "extraversion": 0.5,
            "agreeableness": 0.5,
            "neuroticism": 0.5,
        }
    )


class PersonalityWrapper:
    """Wraps any existing agent with a House MD personality.

    Injects persona-specific system prompts and behavioral modifiers
    into the agent's invocation flow.

    Usage::

        existing_agent = YourExistingCoderAgent()
        chase = PersonalityWrapper(
            base_agent=existing_agent,
            personality=CHASE_PERSONALITY,
        )
        result = await chase.invoke(state)
    """

    def __init__(
        self,
        base_agent: Any,
        personality: PersonalityConfig,
        team_context: TeamContext | None = None,
    ):
        self.base_agent = base_agent
        self.personality = personality
        self.team_context = team_context
        self._invocation_count = 0
        self._challenge_history: list[dict[str, Any]] = []

    def build_enhanced_prompt(self, original_prompt: str) -> str:
        """Inject personality into the agent's prompt."""
        biases_text = "\n".join(
            f"- {BIAS_DESCRIPTIONS[bias]}"
            for bias in self.personality.cognitive_biases
        )
        team_section = ""
        if self.team_context:
            agents = ", ".join(self.team_context.active_agents)
            team_section = f"\nACTIVE TEAM: {agents}\n"

        return (
            f"<house_md_personality>\n"
            f"You are {self.personality.name}, operating as part of a diagnostic team.\n\n"
            f"ROLE: {self.personality.role_description}\n\n"
            f"BEHAVIORAL GUIDELINES:\n"
            f"{self.personality.system_prompt_additions}\n\n"
            f"COGNITIVE TENDENCIES:\n{biases_text}\n\n"
            f"INTERACTION STYLE:\n"
            f"- Challenge threshold: {self.personality.challenge_threshold} "
            f"(higher = more likely to challenge)\n"
            f"- When you disagree, express it clearly with reasoning\n"
            f"- When others challenge you, defend with evidence or concede gracefully\n"
            f"- Your perspective is valuable precisely because it differs from others\n"
            f"{team_section}"
            f"Remember: The goal is correct diagnosis (solution), not consensus. "
            f"Productive disagreement improves outcomes.\n"
            f"</house_md_personality>\n\n"
            f"{original_prompt}"
        )

    def enhance_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Add personality context to state."""
        enhanced = state.copy()
        if "messages" not in enhanced:
            return enhanced

        messages = list(enhanced["messages"])
        system_enhanced = False

        for i, msg in enumerate(messages):
            if isinstance(msg, SystemMessage):
                messages[i] = SystemMessage(
                    content=self.build_enhanced_prompt(msg.content)
                )
                system_enhanced = True
                break
            if isinstance(msg, dict) and msg.get("role") == "system":
                messages[i] = {
                    "role": "system",
                    "content": self.build_enhanced_prompt(msg["content"]),
                }
                system_enhanced = True
                break

        if not system_enhanced:
            messages.insert(0, SystemMessage(content=self.build_enhanced_prompt("")))

        enhanced["messages"] = messages

        if self.team_context:
            enhanced["team_context"] = {
                "other_agents": self.team_context.active_agents,
                "current_hypotheses": self.team_context.hypotheses,
                "my_role": self.personality.name,
            }

        return enhanced

    async def ainvoke(
        self, state: dict[str, Any], config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Async invoke the wrapped agent with personality injection.

        This is the primary entry point, matching LangGraph's ``ainvoke``
        convention so the wrapper can be used anywhere a LangGraph runnable
        is expected (e.g., in ``run_critique_round``).
        """
        return await self.invoke(state, config)

    async def invoke(
        self, state: dict[str, Any], config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Invoke the wrapped agent with personality injection."""
        enhanced_state = self.enhance_state(state)

        if hasattr(self.base_agent, "ainvoke"):
            result = await self.base_agent.ainvoke(enhanced_state, config)
        elif hasattr(self.base_agent, "invoke"):
            result = self.base_agent.invoke(enhanced_state, config)
        elif callable(self.base_agent):
            result = await self.base_agent(enhanced_state)
        else:
            raise TypeError(
                f"Base agent {type(self.base_agent)} is not invocable"
            )

        if isinstance(result, dict):
            result.setdefault("metadata", {})
            result["metadata"]["personality"] = self.personality.name
            result["metadata"]["biases"] = [
                b.value for b in self.personality.cognitive_biases
            ]

        self._invocation_count += 1
        return result

    def should_challenge(self, proposal: dict[str, Any], proposer: str) -> bool:
        """Determine if this personality should challenge a proposal."""
        base_prob = self.personality.challenge_threshold

        if CognitiveBias.CONTRARIAN in self.personality.cognitive_biases:
            base_prob += 0.2
        if CognitiveBias.CONSERVATIVE in self.personality.cognitive_biases:
            if proposal.get("novelty", 0) > 0.5 or proposal.get("risk", 0) > 0.5:
                base_prob += 0.3

        return random.random() < min(base_prob, 1.0)

    @property
    def invocation_count(self) -> int:
        return self._invocation_count


@dataclass
class TeamContext:
    """Shared context visible to all team members during a diagnostic session."""

    active_agents: list[str] = field(default_factory=list)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    current_phase: str = "intake"
    whiteboard: Any | None = None
