"""Critique round — structured debate among House MD team members.

Implements the cross-examination phase of the differential diagnosis protocol.
Each agent proposes, others challenge, proposers defend.
"""

from __future__ import annotations

import re
from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage

from maos.house_md.graphs.states import DiagnosticState
from maos.house_md.memory.whiteboard import Whiteboard
from maos.house_md.personalities.base import PersonalityWrapper, TeamContext

logger = structlog.get_logger()

# Maximum recent messages forwarded to agents during critique rounds.
_CRITIQUE_MAX_CONTEXT_MESSAGES = 10


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
    if not active_team:
        logger.warning("critique_round_empty_team", phase="differential")
    new_hypotheses: list[dict[str, Any]] = []
    agent_beliefs: dict[str, Any] = dict(state.get("agent_beliefs", {}))
    new_messages: list[Any] = []

    for agent_name in active_team:
        if agent_name not in agent_nodes:
            continue

        # Build a per-invocation TeamContext instead of mutating the
        # shared wrapper's team_context (Issue 55: thread-safety).
        agent_fn = agent_nodes[agent_name]
        team_context = TeamContext(
            active_agents=active_team,
            hypotheses=[
                h.to_dict() for h in whiteboard.get_active_hypotheses()
            ],
            current_phase=state.get("current_phase", "differential"),
            whiteboard=whiteboard,
        )

        critique_prompt = _build_critique_prompt(whiteboard, agent_name)

        # Trim message history to avoid unbounded token growth, mirroring
        # the trimming logic in _invoke_agent.
        all_messages = list(state["messages"])
        max_ctx = _CRITIQUE_MAX_CONTEXT_MESSAGES
        if len(all_messages) > max_ctx + 1:
            trimmed = [all_messages[0]] + all_messages[-max_ctx:]
        else:
            trimmed = all_messages

        # Copy mutable fields from state to prevent agents from mutating
        # shared references (Issue 91: shallow spread).
        critique_state = {
            **state,
            "messages": trimmed + [
                HumanMessage(content=critique_prompt),
            ],
            "symptoms": list(state.get("symptoms", [])),
            "evidence": dict(state.get("evidence", {})),
            "active_team": list(state.get("active_team", [])),
            "agent_beliefs": dict(state.get("agent_beliefs", {})),
        }

        try:
            if isinstance(agent_fn, PersonalityWrapper):
                result = await agent_fn.ainvoke(
                    critique_state, team_context=team_context
                )
            elif hasattr(agent_fn, "ainvoke"):
                result = await agent_fn.ainvoke(critique_state)
            elif callable(agent_fn):
                result = await agent_fn(critique_state)
            else:
                continue
        except Exception as e:
            logger.error(
                "critique_agent_failed",
                agent=agent_name,
                error=str(e),
            )
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

            # Extract challenges/rule-outs and apply counter-evidence
            challenges = extract_challenges(content, agent_name)
            for ch in challenges:
                target = _find_existing_hypothesis(
                    whiteboard, ch["target"]
                )
                if target:
                    if ch["action"] == "rule_out":
                        target.rule_out(
                            f"{agent_name}: {ch.get('reason', 'disproved')}"
                        )
                        logger.debug(
                            "hypothesis_ruled_out",
                            hypothesis=target.hypothesis,
                            by=agent_name,
                        )
                    else:
                        target.add_counter_evidence(
                            f"{agent_name} challenges: "
                            f"{ch.get('reason', 'disagrees')}"
                        )
                        logger.debug(
                            "hypothesis_challenged",
                            hypothesis=target.hypothesis,
                            challenger=agent_name,
                        )

            # Extract hypotheses from agent response and add to whiteboard
            extracted = extract_hypotheses(content, agent_name)
            for hyp in extracted:
                existing = _find_existing_hypothesis(whiteboard, hyp["hypothesis"])
                if existing:
                    # Existing hypothesis — add supporting evidence
                    existing.add_supporting_evidence(
                        f"{agent_name} supports: {hyp.get('evidence', 'agrees')}"
                    )
                    logger.debug(
                        "hypothesis_supported",
                        hypothesis=existing.hypothesis,
                        supporter=agent_name,
                    )
                else:
                    # New hypothesis
                    entry = whiteboard.add_hypothesis(
                        hypothesis=hyp["hypothesis"],
                        proposer=agent_name,
                        confidence=hyp.get("confidence", 0.5),
                    )
                    if hyp.get("evidence"):
                        entry.add_supporting_evidence(hyp["evidence"])
                    new_hypotheses.append(entry.to_dict())
                    logger.debug(
                        "hypothesis_added",
                        hypothesis=hyp["hypothesis"],
                        proposer=agent_name,
                    )

    whiteboard.advance_phase(
        "post_critique", iteration=state.get("iteration", 0)
    )

    # Explicitly copy mutable fields from state to avoid shared references
    # that could violate LangGraph's "never mutate state in place" rule.
    return {
        **state,
        "messages": new_messages,
        "hypotheses": new_hypotheses,
        "agent_beliefs": agent_beliefs,
        "whiteboard": whiteboard.to_dict(),
        "symptoms": list(state.get("symptoms", [])),
        "evidence": dict(state.get("evidence", {})),
        "active_team": list(state.get("active_team", [])),
    }


def extract_hypotheses(
    content: str, agent_name: str
) -> list[dict[str, Any]]:
    """Extract hypotheses from an agent's response text.

    Looks for structured markers first (``HYPOTHESIS:`` lines), then
    falls back to heuristic extraction from sentences that propose a
    root cause.

    Returns:
        List of dicts with keys: hypothesis, confidence (optional),
        evidence (optional).
    """
    hypotheses: list[dict[str, Any]] = []

    # Strategy 1: Structured markers
    # Matches: "HYPOTHESIS: ...", "**Hypothesis**: ...", "- Hypothesis: ...",
    # "1. Hypothesis: ...", "Diagnosis: ..."
    structured_pattern = re.compile(
        r"(?:^|\n)\s*(?:[-*\d.)\]]*\s*)?(?:\*{0,2})"
        r"(?:HYPOTHESIS|Hypothesis|hypothesis|DIAGNOSIS|Diagnosis|diagnosis)"
        r"(?:\*{0,2})\s*[:]\s*(.+?)(?=\n|$)",
        re.IGNORECASE,
    )
    for match in structured_pattern.finditer(content):
        hyp_text = match.group(1).strip().rstrip(".")
        if hyp_text and len(hyp_text) > 5:
            conf = _extract_confidence_from_context(content, hyp_text)
            hypotheses.append({
                "hypothesis": hyp_text,
                "confidence": conf,
                "evidence": f"Proposed by {agent_name}",
            })

    if hypotheses:
        return hypotheses

    # Strategy 2: Heuristic — sentences with causal/diagnostic language
    causal_patterns = [
        # "root cause is X", "cause could be X"
        r"(?:root cause|cause)[^.]*?(?:is|could be|might be|appears to be)\s+(.+?)(?:\.|$)",
        # "likely caused by X", "probably due to X"
        r"(?:this is likely|most likely|probably)\s+(?:caused by|due to|a)\s+(.+?)(?:\.|$)",
        # "I believe X", "I suspect X", "diagnosis: X"
        r"(?:I (?:believe|think|suspect)|diagnosis)\s*(?::|is)?\s*(.+?)(?:\.|$)",
        # "the issue is X", "the problem stems from X"
        r"(?:the (?:issue|problem|bug|error|failure))\s+(?:is|stems from|comes from|originates from)\s+(.+?)(?:\.|$)",
        # "caused by X", "due to X", "attributed to X"
        r"(?:^|[.;])\s*(?:this (?:is|was) )?(?:caused by|due to|attributed to|triggered by)\s+(.+?)(?:\.|$)",
        # "points to X", "suggests X", "indicates X" (with subject)
        r"(?:evidence|data|analysis|investigation)\s+(?:points to|suggests|indicates)\s+(.+?)(?:\.|$)",
        # "recommend investigating X", "should check X"
        r"(?:recommend|suggest)\s+(?:investigating|checking|looking at|examining)\s+(.+?)(?:\.|$)",
    ]
    for pattern in causal_patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            hyp_text = match.group(1).strip().rstrip(".")
            if hyp_text and 5 < len(hyp_text) < 200:
                # Avoid duplicates within this extraction
                if not any(
                    _hypothesis_similarity(h["hypothesis"], hyp_text)
                    >= _SIMILARITY_THRESHOLD
                    for h in hypotheses
                ):
                    hypotheses.append({
                        "hypothesis": hyp_text,
                        "confidence": 0.5,
                        "evidence": f"Inferred from {agent_name}'s analysis",
                    })

    return hypotheses


def _extract_confidence_from_context(content: str, hypothesis: str) -> float:
    """Try to extract a confidence value near the hypothesis text."""
    # Look for percentage patterns near the hypothesis
    hyp_idx = content.lower().find(hypothesis.lower())
    if hyp_idx == -1:
        return 0.5

    # Search in a window around the hypothesis
    window = content[max(0, hyp_idx - 50):hyp_idx + len(hypothesis) + 100]
    conf_match = re.search(r"(\d{1,3})\s*%", window)
    if conf_match:
        return min(float(conf_match.group(1)) / 100.0, 1.0)

    # High/low confidence keywords
    low_keywords = ["unlikely", "low confidence", "doubtful", "weak"]
    high_keywords = ["confident", "high confidence", "very likely", "strong"]
    window_lower = window.lower()
    for kw in high_keywords:
        if kw in window_lower:
            return 0.7
    for kw in low_keywords:
        if kw in window_lower:
            return 0.3
    return 0.5


_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
    "it", "its", "this", "that", "and", "or", "but", "not", "so",
    "if", "then", "than", "do", "does", "did", "has", "have", "had",
    "may", "might", "can", "could", "will", "would", "should",
    "due", "caused", "causing", "likely", "possible", "probably",
})

# Minimum word-overlap ratio to consider two hypotheses the same.
# 0.6 provides better discrimination for domain-specific terms
# (e.g. "thread pool" vs "connection pool" share only "pool").
_SIMILARITY_THRESHOLD = 0.6


def _tokenize(text: str) -> set[str]:
    """Split text into a set of meaningful lowercase words."""
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    return words - _STOPWORDS


def _hypothesis_similarity(a: str, b: str) -> float:
    """Compute word-overlap similarity between two hypothesis strings.

    Returns a value in [0, 1].  1 means every significant word in one
    string appears in the other.
    """
    words_a = _tokenize(a)
    words_b = _tokenize(b)
    if not words_a or not words_b:
        return 0.0
    overlap = len(words_a & words_b)
    # Jaccard-like: overlap / size of the *smaller* set so that a short
    # hypothesis can still match a long one if all its words appear.
    return overlap / min(len(words_a), len(words_b))


def _find_existing_hypothesis(whiteboard: Whiteboard, hypothesis_text: str):
    """Find an existing whiteboard entry that matches a hypothesis.

    Uses word-overlap similarity to avoid false positives from naive
    substring matching (e.g. "pool" matching "thread pool" *and*
    "connection pool").
    """
    best_entry = None
    best_score = 0.0
    for entry in whiteboard.get_active_hypotheses():
        score = _hypothesis_similarity(entry.hypothesis, hypothesis_text)
        if score > best_score:
            best_score = score
            best_entry = entry
    if best_score >= _SIMILARITY_THRESHOLD:
        return best_entry
    return None


def extract_challenges(
    content: str, agent_name: str
) -> list[dict[str, Any]]:
    """Extract challenges and rule-outs from an agent's response.

    Looks for structured markers (``RULE OUT:``, ``CHALLENGE:``) and
    heuristic patterns indicating disagreement with a hypothesis.

    Returns:
        List of dicts with keys: target (hypothesis text), action
        ("challenge" or "rule_out"), reason (optional).
    """
    challenges: list[dict[str, Any]] = []

    # Strategy 1: Structured markers
    rule_out_pattern = re.compile(
        r"(?:^|\n)\s*(?:[-*\d.)\]]*\s*)?(?:\*{0,2})"
        r"(?:RULE\s*OUT|Rule\s*out|RULED\s*OUT|Ruled\s*out)"
        r"(?:\*{0,2})\s*[:]\s*(.+?)(?=\n|$)",
        re.IGNORECASE,
    )
    for match in rule_out_pattern.finditer(content):
        text = match.group(1).strip().rstrip(".")
        if text and len(text) > 5:
            challenges.append({
                "target": text,
                "action": "rule_out",
                "reason": f"Ruled out by {agent_name}",
            })

    challenge_pattern = re.compile(
        r"(?:^|\n)\s*(?:[-*\d.)\]]*\s*)?(?:\*{0,2})"
        r"(?:CHALLENGE|Challenge)"
        r"(?:\*{0,2})\s*[:]\s*(.+?)(?=\n|$)",
        re.IGNORECASE,
    )
    for match in challenge_pattern.finditer(content):
        text = match.group(1).strip().rstrip(".")
        if text and len(text) > 5:
            challenges.append({
                "target": text,
                "action": "challenge",
                "reason": f"Challenged by {agent_name}",
            })

    if challenges:
        return challenges

    # Strategy 2: Heuristic patterns
    counter_patterns = [
        (r"(?:rule out|ruled out|can rule out|should rule out)\s+['\"]?(.+?)['\"]?(?:\.|,|$)",
         "rule_out"),
        (r"(?:disagree with|against|disproves?|contradicts?|refutes?)\s+['\"]?(.+?)['\"]?(?:\.|,|$)",
         "challenge"),
        (r"(?:unlikely|improbable|doesn't explain|does not explain)\s+['\"]?(.+?)['\"]?(?:\.|,|$)",
         "challenge"),
    ]
    for pattern, action in counter_patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            text = match.group(1).strip().rstrip(".")
            if text and 5 < len(text) < 200:
                if not any(
                    _hypothesis_similarity(c["target"], text)
                    >= _SIMILARITY_THRESHOLD
                    for c in challenges
                ):
                    challenges.append({
                        "target": text,
                        "action": action,
                        "reason": f"{agent_name}: {match.group(0).strip()[:100]}",
                    })

    return challenges


def extract_environmental_findings(content: str) -> list[str]:
    """Extract environmental findings from an agent's response text.

    Looks for structured ``FINDING:`` markers first, then falls back to
    heuristic patterns that identify contextual discoveries.

    Returns:
        List of finding strings.
    """
    findings: list[str] = []

    # Strategy 1: Structured markers
    structured = re.compile(
        r"(?:^|\n)\s*(?:[-*\d.)\]]*\s*)?(?:\*{0,2})"
        r"(?:FINDING|Finding|finding|ENVIRONMENTAL|Environmental)"
        r"(?:\*{0,2})\s*[:]\s*(.+?)(?=\n|$)",
        re.IGNORECASE,
    )
    for match in structured.finditer(content):
        text = match.group(1).strip().rstrip(".")
        if text and len(text) > 5:
            findings.append(text)

    if findings:
        return findings

    # Strategy 2: Heuristic patterns
    env_patterns = [
        r"(?:found|discovered|noticed|observed)\s+(?:that\s+)?(.+?)(?:\.|$)",
        r"(?:git (?:history|log|blame)|deployment|environment|config(?:uration)?)\s+"
        r"(?:shows?|reveals?|indicates?)\s+(.+?)(?:\.|$)",
        r"(?:the (?:patient|system|codebase) (?:isn't|is not|wasn't) telling us)\s+(.+?)(?:\.|$)",
        r"(?:hidden|unreported|overlooked)\s+(?:factor|issue|change)[:]\s*(.+?)(?:\.|$)",
    ]
    for pattern in env_patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            text = match.group(1).strip().rstrip(".")
            if text and 5 < len(text) < 300:
                if text not in findings:
                    findings.append(text)

    return findings


def _build_critique_prompt(whiteboard: Whiteboard, agent_name: str) -> str:
    """Build a critique prompt for a specific agent.

    Instructs agents to use structured ``HYPOTHESIS:`` markers so
    that :func:`extract_hypotheses` can reliably parse them.
    """
    summary = whiteboard.summary()
    return (
        f"You are {agent_name} on the diagnostic team. "
        f"Review the current whiteboard state and provide your analysis.\n\n"
        f"{summary}\n\n"
        f"Based on your role and expertise:\n"
        f"1. Which hypotheses do you support or challenge? Why?\n"
        f"2. What evidence or tests would you recommend?\n"
        f"3. Are we missing anything?\n\n"
        f"IMPORTANT: When proposing a new hypothesis, use this format:\n"
        f"HYPOTHESIS: <your hypothesis here>\n\n"
        f"Be specific and reference the hypotheses by name."
    )
