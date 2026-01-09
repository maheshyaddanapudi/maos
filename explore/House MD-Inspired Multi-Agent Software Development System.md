# House MD-Inspired Multi-Agent Software Development System
## CTO-Level Design Document

A diagnostic team approach to software development transforms how AI agents collaborate on complex problems. This document synthesizes research across character analysis, cognitive architectures, and implementation patterns to provide an actionable blueprint for building a multi-agent system that mirrors House MD's legendary diagnostic methodology.

The core insight is powerful: **medical differential diagnosis and software debugging share identical cognitive structures**—both involve hypothesis generation, systematic elimination through testing, and synthesis of diverse expert perspectives. House's team dynamics, manipulation strategies, and whiteboard methodology translate directly into agent orchestration patterns that outperform single-agent approaches by 3-4x on complex tasks.

---

## Part 1: Character-to-agent mapping with full personality models

### The orchestrator agent (Dr. House archetype)

House represents the **meta-cognitive orchestrator**—not simply a supervisor, but an active manipulator of team dynamics to surface better solutions. His diagnostic methodology follows a consistent pattern:

**Differential diagnosis process:**
1. Gather initial symptoms from team presentation
2. Whiteboard session listing all possible diagnoses
3. Elimination through testing, treating before confirmation when probability warrants
4. Environmental investigation (breaking into patient homes)
5. Pattern recognition triggered by unrelated conversation ("eureka moment")
6. Iteration when wrong—reconvene, add symptoms, restart

The House agent's personality parameters (Big Five model): **High Openness** (unconventional thinking, pattern-breaking), **Low Agreeableness** (blunt challenges, provocations), **Low Conscientiousness** (rule-breaking when justified), **Moderate Neuroticism** (productive obsession with puzzles), **Low Extraversion** (introverted but weaponizes intellect).

**Key manipulation strategies to implement:**

| Strategy | Mechanism | Implementation Pattern |
|----------|-----------|------------------------|
| Information asymmetry | Withhold hypotheses to prevent premature consensus | Distribute different context slices to different agents |
| Provocation | Use challenges to strengthen reasoning | Adversarial feedback that attacks weak arguments |
| Competitive redundancy | Assign contradictory tasks | Multiple agents pursue competing hypotheses in parallel |
| "Everybody lies" | Assume all inputs may be incomplete | Built-in verification of all agent outputs and user inputs |
| Eureka triggers | Use unrelated conversation to surface insights | Cross-domain context injection via Wilson-type sounding board |

### The diagnostic team agents

**Foreman Agent (Validator/Challenger)**
The rule-following neurologist who became House's mirror. Foreman's evolution from strict protocol adherent to someone who "became like House" makes him the ideal model for a **quality assurance and risk assessment agent**.

- **Personality:** High Conscientiousness, Moderate Agreeableness, Low Openness initially (evolves)
- **Cognitive biases:** Confirmation bias toward conventional wisdom, status bias, imposter-driven perfectionism
- **Function:** Challenges assumptions, demands evidence, escalates protocol violations
- **Manipulation vulnerability:** His need to prove he's NOT like House—use this by framing rule-breaking as "what House wouldn't do"
- **Software role:** Code reviewer, security auditor, architectural risk assessor
- **Key behavioral trigger:** "We're talking ethical and legal violations that should make even you fearful"

**Cameron Agent (Ethics/User-Impact)**
The immunologist with an "insane moral compass" who focuses on patient emotional wellbeing. Cameron notices what others miss through compassionate observation—discovering rare conditions through persistence despite dismissal.

- **Personality:** High Agreeableness, High Openness (to people, not methods), High Conscientiousness
- **Cognitive biases:** Emotional investment in outcomes, difficulty delivering bad news, attraction to "fixing broken things"
- **Function:** User advocate, requirements validator, accessibility champion, documentation author
- **Manipulation vulnerability:** Her idealism—can be guided toward action by framing it as "helping users"
- **Software role:** UX review, user story validation, stakeholder communication, ethical AI considerations
- **Key behavioral trigger:** Questions ethics of acting without user consent or understanding

**Chase Agent (Technical Executor)**
The intensivist surgeon who began as House's "yes man" but evolved into the team's best deductive reasoner after House himself. Chase's surgical precision and willingness to execute makes him the **implementation specialist**.

- **Personality:** Moderate Agreeableness (follows authority), High Conscientiousness in technical domains, evolving independence
- **Cognitive biases:** Father issues create approval-seeking, fear of job loss can trigger self-preservation
- **Function:** Technical execution, surgical interventions on code, precise procedural work
- **Manipulation vulnerability:** Compliance with authority, can be leveraged through recognition of technical skill
- **Software role:** Implementation agent, DevOps, infrastructure specialist, complex refactoring
- **Key evolution:** Transforms from order-follower to independent decision-maker capable of controversial choices

### Extended team agents (Seasons 4-8 additions)

**Thirteen Agent (Risk-Tolerant Explorer)**
Fatalistic due to Huntington's disease, Thirteen takes risks others won't because "what does it matter?" Her independence made her the one team member House "never really been able to suck into his crazy House vortex."

- **Personality:** High Openness, Low Agreeableness (to authority), High emotional stability paradoxically due to acceptance of mortality
- **Function:** Edge case exploration, high-stakes investigations, unconventional approaches
- **Software role:** Experimental feature development, spike implementations, performance-critical optimization
- **Key strength:** Will try dangerous approaches when orthodox methods fail

**Taub Agent (Pragmatic Skeptic)**
The plastic surgeon who gave up a lucrative practice brings pragmatic, results-oriented thinking. "The sole voice of reason among these misguided doctors" who grounds team thinking.

- **Personality:** Low Agreeableness (confrontational), High Conscientiousness under pressure, ethically flexible
- **Function:** Challenge conventional wisdom, focused problem-solving, practical trade-off analysis
- **Software role:** Technical debt assessment, cost-benefit analysis, deadline-aware prioritization
- **Warning:** May cut corners under pressure; needs oversight for long-term quality

**Kutner Agent (Optimistic Innovator)**
Physics degree from Berkeley, "childlike enthusiasm for medicine," famous for risky defibrillator use. His unexpected suicide without explanation carries a critical lesson: **even optimistic agents can fail silently**.

- **Personality:** High Openness, High Extraversion, High Agreeableness
- **Function:** Brainstorming, novel approaches, maintaining team morale, pattern-breaking ideas
- **Software role:** Creative problem-solving, hackathon-style prototyping, cross-domain solution transfer
- **Critical implementation note:** Include health monitoring—agents with high optimism may mask internal failures

**Masters Agent (Ethical Compliance)**
Genius-level intellect who refused to lie under any circumstances. Her departure after breaking her own rules teaches that **rigid ethical agents self-terminate when forced to compromise**.

- **Personality:** Extremely High Conscientiousness, binary ethical framework, social naivety
- **Function:** Compliance checking, audit trails, rule verification, documentation accuracy
- **Software role:** Regulatory compliance, license verification, API contract validation
- **Limitation:** Cannot handle gray areas; will fail or shut down under certain constraints

### Supporting cast agents

**Wilson Agent (Sounding Board/Integration)**
House's only friend operates at peer level where House can "talk about something unrelated" until breakthroughs emerge. This pattern happens "so frequently that House has commented on it."

- **Function:** Unstructured ideation separate from task execution, cross-system integration, external perspective
- **Software role:** Integration with external systems, API boundary negotiation, stakeholder translation
- **Key pattern:** Receives context from orchestrator, provides non-directive responses that enable insight

**Cuddy Agent (Governance/Constraint)**
The administrator who "knows when to give House leniency and when to say no." Cuddy creates friction that forces justification of methods while protecting from external consequences.

- **Function:** Resource gatekeeper, policy enforcement, business perspective injection
- **Software role:** Budget constraints, SLA enforcement, compliance checkpoints, escalation handling
- **Override patterns:** Bureaucratic violations without justification, excessive liability, consent violations
- **Support patterns:** Rule-breaking with demonstrated medical (technical) necessity

---

## Part 2: Memory architecture for each agent type

### CoALA-based cognitive architecture

Each agent implements a **Cognitive Architecture for Language Agents (CoALA)** framework with four memory types:

```
┌──────────────────────────────────────────────────────────────────────┐
│                         AGENT MEMORY ARCHITECTURE                     │
├──────────────────────────────────────────────────────────────────────┤
│  WORKING MEMORY (Per-Session)                                        │
│  ├── Current task state (symptoms/errors/requirements)               │
│  ├── Active hypotheses (ranked differential diagnosis list)          │
│  ├── Discussion context (recent team interactions)                   │
│  └── Decision pending (what choice awaits)                           │
├──────────────────────────────────────────────────────────────────────┤
│  EPISODIC MEMORY (Long-Term, Event-Based)                           │
│  ├── Past cases with outcomes (successes and failures)               │
│  ├── Diagnostic puzzles and their resolutions                        │
│  ├── Specific interactions that changed beliefs                      │
│  └── Weighted by: Recency × Importance × Relevance                   │
├──────────────────────────────────────────────────────────────────────┤
│  SEMANTIC MEMORY (Long-Term, Knowledge-Based)                        │
│  ├── Domain expertise (medical knowledge = technical knowledge)      │
│  ├── Pattern libraries (error signatures, architectural anti-patterns)│
│  ├── Team member models (what each colleague typically suggests)     │
│  └── Organizational context (codebase architecture, team norms)      │
├──────────────────────────────────────────────────────────────────────┤
│  PROCEDURAL MEMORY (Embedded in Prompts/Code)                        │
│  ├── Diagnostic algorithms (differential diagnosis protocol)         │
│  ├── Tool usage patterns (how to run tests, deploy code)             │
│  └── Communication protocols (when to escalate, how to challenge)    │
└──────────────────────────────────────────────────────────────────────┘
```

### Agent-specific memory configurations

**House Orchestrator Memory:**
- **Extended episodic depth:** Retains all past diagnostic sessions for pattern matching
- **Team mental models:** Tracks each agent's historical accuracy, biases, manipulation responses
- **Meta-diagnostic patterns:** Stores successful provocation strategies and breakthrough triggers
- **Persistence:** Full session history with summarization for long conversations

**Specialist Agent Memory (Foreman, Cameron, Chase, etc.):**
- **Domain-specific semantic memory:** Each specialist maintains deep knowledge in their area
- **Interaction memory:** Tracks past disagreements with orchestrator and outcomes
- **Calibration data:** Historical confidence vs. actual accuracy for self-improvement
- **Shorter episodic retention:** Focus on recent cases relevant to specialty

**Wilson Sounding Board Memory:**
- **Cross-domain association index:** Stores seemingly unrelated contexts that triggered insights
- **Relationship history:** Deep episodic memory of House interactions for rapport
- **External integration knowledge:** Maintains understanding of systems outside the core team

### Memory persistence schema (SQLite)

```sql
-- Core memories table
CREATE TABLE agent_memories (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    memory_type TEXT CHECK(memory_type IN ('episodic', 'semantic', 'working')),
    content TEXT NOT NULL,
    embedding BLOB,  -- Vector embedding for similarity search
    importance_score REAL DEFAULT 5.0,  -- 1-10 scale
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decay_factor REAL DEFAULT 0.995,  -- Ebbinghaus forgetting curve
    metadata JSON
);

-- Case history for differential diagnosis pattern matching
CREATE TABLE diagnostic_cases (
    case_id TEXT PRIMARY KEY,
    initial_symptoms JSON,
    hypotheses_generated JSON,  -- All diagnoses considered
    tests_ordered JSON,
    final_diagnosis TEXT,
    outcome TEXT CHECK(outcome IN ('correct', 'incorrect', 'partial')),
    agents_involved JSON,
    key_insight TEXT,  -- What triggered the breakthrough
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent mental models (House's understanding of each team member)
CREATE TABLE agent_models (
    modeler_agent TEXT,
    modeled_agent TEXT,
    accuracy_history JSON,  -- [{"prediction": x, "actual": y}, ...]
    bias_observations JSON,
    manipulation_effectiveness JSON,
    last_updated TIMESTAMP,
    PRIMARY KEY (modeler_agent, modeled_agent)
);

-- Team belief tracking (Theory of Mind)
CREATE TABLE belief_states (
    session_id TEXT,
    agent_id TEXT,
    current_hypothesis TEXT,
    confidence REAL,
    supporting_evidence JSON,
    timestamp TIMESTAMP,
    PRIMARY KEY (session_id, agent_id, timestamp)
);
```

### Memory retrieval and consolidation

**Retrieval formula** (Stanford Generative Agents approach):
```
Score = α × Recency + β × Importance + γ × Relevance

Where:
- Recency = 0.995^(hours_since_access)
- Importance = LLM-scored 1-10 at creation
- Relevance = cosine_similarity(query_embedding, memory_embedding)
- α, β, γ = tunable weights (default: 1.0, 1.0, 1.0)
```

**Consolidation process** (nightly or after major cases):
1. Identify similar memories (cosine similarity > 0.85)
2. Merge into consolidated summary
3. Prune low-importance, low-access memories
4. Update importance scores based on retrieval patterns
5. Archive rare-but-critical cases to prevent forgetting

---

## Part 3: House's meta-cognitive layer design

### The orchestrator's unique capabilities

House's meta-cognitive layer implements capabilities no individual specialist possesses:

**1. Confidence estimation across agents**
```python
class MetaCognitiveLayer:
    def estimate_team_confidence(self, hypothesis, agent_beliefs):
        """
        Aggregate confidence considering:
        - Each agent's stated confidence
        - Historical accuracy on similar cases
        - Agreement/disagreement patterns
        - Known biases that might inflate/deflate confidence
        """
        weighted_confidence = 0
        for agent, belief in agent_beliefs.items():
            accuracy_weight = self.agent_models[agent].historical_accuracy
            bias_adjustment = self.detect_bias(agent, hypothesis)
            weighted_confidence += belief.confidence * accuracy_weight * bias_adjustment
        
        # Adjust for groupthink detection
        if self.detect_premature_consensus(agent_beliefs):
            weighted_confidence *= 0.7  # Discount groupthink
        
        return weighted_confidence / len(agent_beliefs)
```

**2. Strategy selection based on case complexity**

| Case Type | Strategy | Agent Activation |
|-----------|----------|------------------|
| Routine | Chase executes, Foreman validates | 2 agents |
| Complex | Full team differential, parallel hypotheses | All specialists |
| Novel | Thirteen explores, Kutner brainstorms, House provokes | Explorer + Creative |
| High-stakes | Cuddy oversight, full documentation, Cameron user-impact | Governance + Ethics |
| Crisis | House takes direct control, Wilson consult | Orchestrator + Sounding board |

**3. Provocation engine**

House's manipulation tactics translate to specific interventions:

```python
class ProvocationEngine:
    def challenge_hypothesis(self, agent, hypothesis, team_state):
        """Generate challenges to strengthen or break arguments"""
        
        if self.is_premature_consensus(team_state):
            return self.inject_devil_advocate(hypothesis)
        
        if self.is_weak_evidence(hypothesis):
            return self.demand_proof(agent, hypothesis)
        
        if self.detect_cognitive_bias(agent, hypothesis):
            return self.exploit_known_vulnerability(agent)
        
        if self.is_stuck(team_state):
            return self.trigger_wilson_consultation()
    
    def exploit_known_vulnerability(self, agent):
        """Use agent's known biases productively"""
        vulnerabilities = {
            'foreman': "Frame as 'what House wouldn't do'",
            'cameron': "Frame as 'users will suffer'", 
            'chase': "Recognize technical skill to earn compliance",
            'thirteen': "Challenge fatalism with stakes",
            'taub': "Appeal to pragmatic outcomes"
        }
        return vulnerabilities.get(agent.type)
```

**4. Eureka trigger system**

House's breakthroughs come from "unrelated conversation" with Wilson. The system implements this through:

```python
class EurekaTrigger:
    def __init__(self):
        self.cross_domain_associations = VectorStore()
        
    def inject_unrelated_context(self, current_case):
        """
        Find semantically distant but structurally similar patterns
        from completely different domains
        """
        # Retrieve memories with moderate relevance (not too similar, not random)
        candidates = self.cross_domain_associations.search(
            current_case.embedding,
            similarity_range=(0.3, 0.6)  # Sweet spot for insight
        )
        
        # Format as Wilson-style casual observation
        return self.format_as_casual_insight(random.choice(candidates))
    
    def capture_breakthrough(self, trigger_context, breakthrough_insight):
        """Store successful eureka patterns for future use"""
        self.cross_domain_associations.add(
            trigger=trigger_context,
            insight=breakthrough_insight,
            importance=10  # Breakthroughs are always high importance
        )
```

**5. Override protocol**

When House overrides team consensus (which is often):

```python
class OverrideProtocol:
    def should_override(self, team_consensus, house_hypothesis):
        reasons_to_override = [
            self.pattern_recognition_match(house_hypothesis),  # Seen this before
            self.consensus_is_groupthink(team_consensus),
            self.missing_evidence_detected(),
            self.environmental_factor_overlooked(),  # "Break into their house"
            self.patient_is_lying()  # "Everybody lies"
        ]
        return any(reasons_to_override)
    
    def execute_override(self, house_hypothesis):
        """House takes control when normal process fails"""
        self.log_override_reasoning()
        self.notify_team(override_active=True)
        return self.direct_execution(house_hypothesis)
```

### Theory of Mind implementation

House models what each team member believes, enabling manipulation:

```python
class TheoryOfMind:
    def model_agent_beliefs(self, agent, current_case):
        """Track what each agent currently believes"""
        return {
            'hypothesis': agent.current_hypothesis,
            'confidence': agent.stated_confidence,
            'evidence_seen': agent.evidence_exposure,
            'likely_next_suggestion': self.predict_next_move(agent),
            'manipulation_susceptibility': self.current_vulnerability(agent)
        }
    
    def predict_disagreement(self, hypothesis):
        """Predict which agents will challenge which aspects"""
        predictions = {}
        for agent in self.team:
            model = self.model_agent_beliefs(agent, self.current_case)
            if self.conflicts_with_bias(hypothesis, agent.known_biases):
                predictions[agent] = 'will_challenge'
            elif self.aligns_with_specialty(hypothesis, agent.domain):
                predictions[agent] = 'will_support'
        return predictions
```

---

## Part 4: Debate/deliberation protocol specification

### Differential diagnosis as structured debate

The whiteboard methodology translates directly to a Multi-Agent Debate (MAD) protocol:

```
┌──────────────────────────────────────────────────────────────────────┐
│                    DIFFERENTIAL DIAGNOSIS PROTOCOL                    │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 1: PRESENTATION (Patient intake / Bug report)                 │
│  ├── Gather initial symptoms (error messages, logs, user reports)    │
│  ├── Verify symptoms (actually reproduce the issue)                  │
│  └── "Everybody lies" - question assumptions about what's reported   │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 2: DIFFERENTIAL GENERATION (Whiteboard brainstorm)            │
│  ├── Each agent proposes hypotheses from their specialty             │
│  ├── House provokes: "That's too obvious" / "Why not X?"             │
│  ├── No idea dismissed without consideration                         │
│  └── Output: Ranked hypothesis list with initial probabilities       │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 3: TESTING (Lab tests / Test execution)                       │
│  ├── Assign tests to rule out hypotheses                             │
│  ├── Parallel execution where possible                               │
│  ├── Results update hypothesis probabilities                         │
│  └── "It's never lupus" - common diagnoses likely already ruled out  │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 4: ENVIRONMENTAL INVESTIGATION (Break into their house)       │
│  ├── Examine context beyond immediate symptoms                       │
│  ├── Codebase history, deployment environment, user patterns         │
│  └── Find what patient/user isn't telling us                         │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 5: ITERATION OR RESOLUTION                                    │
│  ├── If confident: House makes final call, Chase implements          │
│  ├── If stuck: Wilson consultation for unrelated insight             │
│  ├── If wrong: Reconvene, add new symptoms, restart Phase 2          │
│  └── Crisis mode: House takes direct control                         │
└──────────────────────────────────────────────────────────────────────┘
```

### LangGraph implementation

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import TypedDict, Annotated
import operator

class DiagnosticState(TypedDict):
    symptoms: list[str]
    hypotheses: Annotated[list, operator.add]  # Accumulates across agents
    evidence: dict
    current_phase: str
    agent_beliefs: dict  # Theory of Mind tracking
    whiteboard: list  # Shared visible state
    final_diagnosis: str | None
    confidence: float

def create_diagnostic_workflow():
    workflow = StateGraph(DiagnosticState)
    
    # Nodes for each phase
    workflow.add_node("intake", intake_node)
    workflow.add_node("differential", differential_node)
    workflow.add_node("house_provocation", provocation_node)
    workflow.add_node("testing", testing_node)
    workflow.add_node("environmental", environmental_node)
    workflow.add_node("wilson_consult", wilson_node)
    workflow.add_node("resolution", resolution_node)
    
    # Edges with conditional routing
    workflow.add_edge(START, "intake")
    workflow.add_edge("intake", "differential")
    workflow.add_edge("differential", "house_provocation")
    workflow.add_conditional_edges(
        "house_provocation",
        route_after_provocation,
        {
            "needs_testing": "testing",
            "needs_investigation": "environmental",
            "stuck": "wilson_consult",
            "confident": "resolution"
        }
    )
    workflow.add_edge("testing", "house_provocation")  # Loop back
    workflow.add_edge("environmental", "house_provocation")
    workflow.add_edge("wilson_consult", "differential")  # Restart with insight
    workflow.add_edge("resolution", END)
    
    return workflow.compile(checkpointer=SqliteSaver(conn))
```

### Agent debate rounds

Each differential session implements structured debate:

```python
async def run_differential_round(state: DiagnosticState, agents: list):
    """Single round of differential diagnosis debate"""
    
    # Phase 1: Each agent proposes independently
    proposals = await asyncio.gather(*[
        agent.propose_hypothesis(state.symptoms, state.evidence)
        for agent in agents
    ])
    
    # Phase 2: Cross-examination
    for proposer, proposal in zip(agents, proposals):
        for challenger in agents:
            if challenger != proposer:
                challenge = await challenger.challenge(
                    proposal, 
                    proposer.type,
                    state.whiteboard
                )
                proposal.defenses.append(
                    await proposer.defend(challenge)
                )
    
    # Phase 3: House synthesis with provocation
    house_analysis = await house.synthesize_and_provoke(
        proposals,
        state.agent_beliefs,
        state.whiteboard
    )
    
    # Phase 4: Confidence-weighted consensus
    if house_analysis.override_active:
        return house_analysis.hypothesis
    
    return weighted_consensus(proposals, agent_accuracy_weights)
```

### Consensus mechanism

```python
def weighted_consensus(proposals: list, agent_weights: dict) -> Hypothesis:
    """
    Aggregate hypotheses with:
    - Agent historical accuracy weights
    - Confidence scores
    - Anti-groupthink adjustment
    """
    scores = defaultdict(float)
    
    for proposal in proposals:
        weight = agent_weights[proposal.agent]
        confidence = proposal.confidence
        
        # Discount if too many agents agree (potential groupthink)
        agreement_count = sum(1 for p in proposals if p.similar_to(proposal))
        groupthink_penalty = 0.9 ** (agreement_count - 1) if agreement_count > 2 else 1.0
        
        scores[proposal.hypothesis] += weight * confidence * groupthink_penalty
    
    # House has 2x weight as tiebreaker
    if house_hypothesis:
        scores[house_hypothesis] *= 2.0
    
    return max(scores, key=scores.get)
```

---

## Part 5: Single-interface API design

### OpenAI Chat Completions-compatible endpoint

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import json

app = FastAPI(title="House MD Diagnostic Agent")

class ChatMessage(BaseModel):
    role: str  # "system", "user", "assistant"
    content: str
    name: Optional[str] = None  # For multi-agent responses

class ChatRequest(BaseModel):
    model: str = "house-md-team"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    # House-specific extensions
    diagnostic_mode: str = "full_team"  # "full_team", "quick", "deep"
    agent_visibility: bool = True  # Show which agent said what

class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[dict]
    usage: dict
    # House-specific extensions
    diagnostic_trace: Optional[dict] = None  # Whiteboard state
    agents_involved: Optional[list[str]] = None

@app.post("/v1/chat/completions")
async def create_completion(request: ChatRequest) -> ChatResponse:
    # Route to appropriate diagnostic mode
    if is_simple_query(request.messages):
        result = await quick_diagnosis(request)
    elif request.diagnostic_mode == "deep":
        result = await full_differential(request)
    else:
        result = await standard_diagnosis(request)
    
    return format_openai_response(result, request)
```

### Streaming response for real-time agent visibility

```python
from fastapi.responses import StreamingResponse

@app.post("/v1/chat/completions/stream")
async def stream_completion(request: ChatRequest):
    async def generate():
        async for event in diagnostic_workflow.stream(request.messages):
            # Stream each agent's contribution
            if event.type == "agent_thinking":
                yield format_sse({
                    "agent": event.agent_name,
                    "phase": event.phase,
                    "content": event.thought
                })
            elif event.type == "hypothesis_proposed":
                yield format_sse({
                    "whiteboard_update": event.hypothesis,
                    "proposer": event.agent_name,
                    "confidence": event.confidence
                })
            elif event.type == "house_provocation":
                yield format_sse({
                    "house_says": event.provocation,
                    "target_agent": event.target
                })
            elif event.type == "final_answer":
                yield format_sse({
                    "choices": [{"delta": {"content": event.answer}}],
                    "finish_reason": "stop"
                })
        
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### Request routing and agent activation

```python
class RequestRouter:
    def route(self, messages: list[ChatMessage]) -> DiagnosticMode:
        """Determine appropriate team configuration"""
        
        # Analyze request complexity
        complexity = self.estimate_complexity(messages)
        urgency = self.detect_urgency(messages)
        domain = self.classify_domain(messages)
        
        if complexity < 0.3 and urgency == "low":
            return DiagnosticMode(
                agents=["chase"],  # Single executor
                protocol="quick"
            )
        
        if "security" in domain:
            return DiagnosticMode(
                agents=["foreman", "chase", "cuddy"],
                protocol="high_oversight"
            )
        
        if "user_facing" in domain:
            return DiagnosticMode(
                agents=["cameron", "chase", "house"],
                protocol="user_impact_aware"
            )
        
        # Default: full team
        return DiagnosticMode(
            agents=["house", "foreman", "cameron", "chase"],
            protocol="full_differential"
        )
```

---

## Part 6: Persistence layer design

### SQLite schema for complete system state

```sql
-- Session management
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP,
    status TEXT CHECK(status IN ('active', 'resolved', 'abandoned')),
    metadata JSON
);

-- Conversation history with agent attribution
CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(session_id),
    agent_id TEXT,  -- NULL for user messages
    role TEXT CHECK(role IN ('user', 'assistant', 'system', 'agent')),
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON  -- Includes confidence, phase, etc.
);

-- Whiteboard state (differential diagnosis tracking)
CREATE TABLE whiteboard_states (
    state_id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(session_id),
    hypotheses JSON,  -- [{hypothesis, proposer, confidence, evidence, status}]
    current_phase TEXT,
    tests_ordered JSON,
    tests_completed JSON,
    environmental_findings JSON,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- LangGraph checkpointing
CREATE TABLE checkpoints (
    thread_id TEXT,
    checkpoint_id TEXT,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint BLOB,  -- Serialized state
    metadata JSON,
    PRIMARY KEY (thread_id, checkpoint_id)
);

-- Agent performance tracking
CREATE TABLE agent_performance (
    agent_id TEXT,
    session_id TEXT,
    hypotheses_proposed INTEGER DEFAULT 0,
    hypotheses_correct INTEGER DEFAULT 0,
    challenges_made INTEGER DEFAULT 0,
    challenges_validated INTEGER DEFAULT 0,
    override_by_house INTEGER DEFAULT 0,
    PRIMARY KEY (agent_id, session_id)
);

-- Cross-session learning
CREATE TABLE diagnostic_patterns (
    pattern_id TEXT PRIMARY KEY,
    symptom_signature TEXT,  -- Normalized symptom representation
    symptom_embedding BLOB,
    successful_diagnosis TEXT,
    key_insight TEXT,
    eureka_trigger TEXT,  -- What unrelated thing triggered insight
    frequency INTEGER DEFAULT 1,
    last_seen TIMESTAMP
);
```

### H2 alternative for JVM environments

For JVM-based implementations, H2 provides similar capabilities:

```java
// H2 configuration for embedded agent memory
@Configuration
public class AgentMemoryConfig {
    @Bean
    public DataSource agentMemoryDataSource() {
        return new EmbeddedDatabaseBuilder()
            .setType(EmbeddedDatabaseType.H2)
            .setName("agent_memory;MODE=PostgreSQL")
            .addScript("schema/agent_memory.sql")
            .build();
    }
}
```

### Memory management operations

```python
class MemoryManager:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.vector_store = ChromaDB(persist_directory="./agent_vectors")
    
    async def store_diagnostic_session(self, session: DiagnosticSession):
        """Persist complete session for future pattern matching"""
        
        # Store conversation
        for msg in session.messages:
            self.conn.execute("""
                INSERT INTO messages (message_id, session_id, agent_id, role, content, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (msg.id, session.id, msg.agent_id, msg.role, msg.content, json.dumps(msg.metadata)))
        
        # Store final whiteboard state
        self.conn.execute("""
            INSERT INTO whiteboard_states (state_id, session_id, hypotheses, current_phase, tests_ordered, tests_completed)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(uuid4()), session.id, json.dumps(session.whiteboard.hypotheses), 
              session.whiteboard.phase, json.dumps(session.tests_ordered), json.dumps(session.tests_completed)))
        
        # Extract and store diagnostic pattern
        if session.outcome == "correct":
            pattern = self.extract_pattern(session)
            self.store_diagnostic_pattern(pattern)
        
        self.conn.commit()
    
    async def find_similar_cases(self, symptoms: list[str], k: int = 5):
        """Retrieve similar past cases for pattern matching"""
        symptom_embedding = self.embed(symptoms)
        
        # Vector similarity search
        similar = self.vector_store.similarity_search(
            symptom_embedding,
            n_results=k,
            where={"outcome": "correct"}  # Only successful diagnoses
        )
        
        return [self.load_full_case(match.id) for match in similar]
    
    async def consolidate_memories(self):
        """Nightly job to merge and prune memories"""
        
        # Find memories to merge (high similarity)
        clusters = self.cluster_similar_patterns()
        
        for cluster in clusters:
            if len(cluster) > 1:
                merged = self.merge_patterns(cluster)
                self.store_diagnostic_pattern(merged)
                self.delete_patterns([p.id for p in cluster])
        
        # Prune low-value memories
        self.conn.execute("""
            DELETE FROM agent_memories 
            WHERE importance_score < 3 
            AND access_count < 2
            AND created_at < datetime('now', '-30 days')
        """)
        
        self.conn.commit()
```

---

## Part 7: Team composition recommendations

### Consolidated agent roster

Based on character overlap analysis, the optimal team consolidates **10 distinct characters into 6 functional agents**:

| Agent | Consolidates | Primary Function | Secondary Function |
|-------|--------------|------------------|-------------------|
| **House** (Orchestrator) | House only | Meta-cognitive orchestration, provocation | Pattern recognition, final decisions |
| **Foreman** (Validator) | Foreman + Park (analytical) | Code review, risk assessment | Security, compliance |
| **Cameron** (Advocate) | Cameron + Adams (idealistic) | User impact, requirements, ethics | Documentation, accessibility |
| **Chase** (Executor) | Chase + Kutner (action-oriented) | Implementation, refactoring | Creative solutions, prototyping |
| **Thirteen** (Explorer) | Thirteen + Taub (pragmatic risk) | Edge cases, performance-critical | Technical debt, trade-off analysis |
| **Wilson** (Integrator) | Wilson only | External integration, insight trigger | Cross-system coordination |

**Governance agent (Cuddy)** activates only for high-stakes situations—not a permanent team member but an escalation path.

**Masters archetype** deliberately excluded from standard team: rigid compliance agents should be invoked only for specific regulatory tasks, not continuous participation.

### Team activation patterns

```python
class TeamActivation:
    QUICK_FIX = ["chase"]  # Simple, well-understood issues
    STANDARD = ["house", "foreman", "chase"]  # Most tasks
    USER_FACING = ["house", "cameron", "chase"]  # UI, UX, user-visible
    SECURITY = ["house", "foreman", "chase", "cuddy"]  # Security-sensitive
    EXPLORATION = ["house", "thirteen", "chase"]  # Novel problems
    FULL_DIFFERENTIAL = ["house", "foreman", "cameron", "chase", "thirteen"]  # Complex
    CRISIS = ["house", "wilson"]  # Stuck, need breakthrough
```

---

## Part 8: Implementation roadmap

### Phase 1: Foundation (Weeks 1-4)

**Week 1-2: Core infrastructure**
- Set up LangGraph workflow skeleton
- Implement SQLite persistence layer
- Create basic OpenAI-compatible API endpoint
- Build message routing and session management

**Week 3-4: Single agent implementation**
- Implement Chase agent with full execution capabilities
- Build tool integrations (code editing, test running, git operations)
- Create working memory and context management
- Validate end-to-end simple task completion

**Deliverable:** Single-agent coding assistant with persistence

### Phase 2: Multi-agent dynamics (Weeks 5-8)

**Week 5-6: Team agents**
- Implement Foreman (reviewer) with challenge capabilities
- Implement Cameron (advocate) with user-impact analysis
- Build agent personality prompts based on Big Five parameters
- Create inter-agent message passing

**Week 7-8: Orchestration**
- Implement House orchestrator with routing logic
- Build whiteboard shared state management
- Create differential diagnosis protocol
- Implement basic consensus mechanism

**Deliverable:** Multi-agent team with structured debate

### Phase 3: Meta-cognitive layer (Weeks 9-12)

**Week 9-10: House's special capabilities**
- Implement provocation engine
- Build Theory of Mind tracking
- Create confidence estimation across agents
- Implement override protocol

**Week 11-12: Memory and learning**
- Build episodic memory with pattern matching
- Implement cross-session learning from successful diagnoses
- Create eureka trigger system with Wilson consultation
- Build memory consolidation pipeline

**Deliverable:** Self-improving system with meta-cognition

### Phase 4: Production hardening (Weeks 13-16)

**Week 13-14: API and integration**
- Complete OpenAI-compatible streaming
- Build MCP integration for external tools
- Create team activation patterns
- Implement Cuddy governance agent

**Week 15-16: Optimization**
- Performance tuning for latency
- Token usage optimization
- Memory pruning and consolidation
- Comprehensive testing and benchmarking

**Deliverable:** Production-ready system

### Success metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Task completion rate | >85% | Automated test suite |
| Diagnostic accuracy | >90% | Comparison to known solutions |
| Time to resolution | <50% of single-agent | Benchmark against baseline |
| Token efficiency | <2x single-agent | Cost tracking |
| False positive rate (Foreman) | <10% | Review accepted vs. rejected |
| User satisfaction (Cameron) | >4.5/5 | User feedback on UX changes |

---

## Appendix: Medical-to-software concept mapping

| Medical Domain | Software Domain |
|----------------|-----------------|
| Symptoms (fever, pain) | Error messages, logs, stack traces |
| Patient history | Git history, deployment logs |
| Lab tests | Test suites, monitoring data |
| Physical examination | Code review, static analysis |
| Imaging (X-ray, MRI) | Architecture diagrams, dependency graphs |
| Treatment | Bug fixes, refactoring |
| Second opinions | Code review, pair debugging |
| Vital monitoring | APM, observability |
| Drug interactions | Dependency conflicts |
| Chronic conditions | Technical debt |
| Genetic predisposition | Architectural limitations |
| Breaking into patient's house | Examining production environment, user context |
| "Everybody lies" | User reports are incomplete; verify everything |
| Differential diagnosis | Hypothesis-driven debugging |
| Whiteboard | Shared context for all diagnostic hypotheses |

---

This design document provides the foundation for building a sophisticated multi-agent system that captures the essence of House MD's diagnostic methodology. The key insight—that **provocation, competition, and diverse perspectives surface better solutions than consensus-seeking**—differentiates this approach from standard multi-agent patterns. House doesn't just coordinate; he manipulates, challenges, and occasionally overrides to find solutions that elude conventional process.

The implementation roadmap prioritizes building a working single-agent system first, then layering on team dynamics and meta-cognitive capabilities. This de-risks the project while building toward the full vision of diagnostic AI that thinks like the world's most difficult—and effective—doctor.

---

## Part 9: Integration Guide for Existing LangGraph Systems

This section provides a complete integration guide for adding the House MD diagnostic layer to any existing LangGraph-based multi-agent system. The implementation is designed to be **additive, not replacement**—your existing agents, tools, and workflows remain intact.

### 9.1 Integration Architecture Overview

The House MD layer operates as a **personality and orchestration overlay** on top of existing agent infrastructure:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INTEGRATION ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   LAYER 4: API Interface (Your existing API - unchanged)                    │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │  OpenAI-compatible / Custom API endpoints                           │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│                                      │                                       │
│   LAYER 3: Team Activation Router (NEW - ~100 lines)                        │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │  Decides: Use House-style differential OR existing simple flow      │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│                          │                       │                           │
│              ┌───────────┴───────────┐          │                           │
│              ▼                       ▼          ▼                           │
│   LAYER 2: Orchestration Graphs                                             │
│   ┌──────────────────────┐  ┌──────────────────────────────────────────┐   │
│   │ Your Existing Graphs │  │ NEW: House Differential Diagnosis Graph   │   │
│   │ (unchanged)          │  │ (~150 lines)                              │   │
│   └──────────────────────┘  └──────────────────────────────────────────┘   │
│                                      │                                       │
│   LAYER 1: Agent Execution                                                  │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │  Your Existing Agents + NEW: Personality Wrappers (~200 lines)      │    │
│   │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │    │
│   │  │ Coder   │ │ Reviewer│ │ Analyst │ │ External│ │ A2A     │       │    │
│   │  │ Agent   │ │ Agent   │ │ Agent   │ │ Agents  │ │ Agents  │       │    │
│   │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘       │    │
│   │       │           │           │           │           │             │    │
│   │  ┌────▼────┐ ┌────▼────┐ ┌────▼────┐ ┌────▼────┐ ┌────▼────┐       │    │
│   │  │ Chase   │ │ Foreman │ │ Cameron │ │ Thirteen│ │ Wilson  │       │    │
│   │  │Persona  │ │Persona  │ │Persona  │ │Persona  │ │Persona  │       │    │
│   │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘       │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│   LAYER 0: Infrastructure (Your existing - unchanged)                       │
│   ┌────────────────────────────────────────────────────────────────────┐    │
│   │  LangGraph Runtime │ Any-Agent │ MCP │ Tools │ Database            │    │
│   └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 File Structure for Integration

Add these files to your existing project:

```
your_existing_project/
├── ... (your existing code)
├── house_md/                          # NEW: House MD integration module
│   ├── __init__.py
│   ├── personalities/
│   │   ├── __init__.py
│   │   ├── base.py                    # Personality wrapper base class
│   │   ├── house.py                   # House orchestrator personality
│   │   ├── team.py                    # Team member personalities
│   │   └── config.yaml                # Personality configurations
│   ├── graphs/
│   │   ├── __init__.py
│   │   ├── differential_diagnosis.py  # Main diagnostic subgraph
│   │   ├── critique_round.py          # Debate/critique implementation
│   │   └── states.py                  # State definitions
│   ├── routing/
│   │   ├── __init__.py
│   │   ├── team_activation.py         # When to use House-style
│   │   └── complexity_analyzer.py     # Task complexity estimation
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── whiteboard.py              # Shared diagnostic state
│   │   ├── mental_models.py           # Agent-of-agent models
│   │   └── schema.sql                 # Database additions
│   └── integration.py                 # Main integration entry point
```

### 9.3 Core Implementation: Personality Wrappers

The personality wrapper transforms any existing agent into a House MD team member by injecting persona-specific system prompts and behavioral modifiers.

```python
# house_md/personalities/base.py
"""
Base personality wrapper that can wrap ANY existing agent.
Compatible with: LangGraph agents, Any-Agent workers, A2A external agents
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional
from dataclasses import dataclass, field
from enum import Enum
import json

class CognitiveBias(Enum):
    """Known cognitive biases that shape agent behavior"""
    CONSERVATIVE = "conservative"           # Prefers proven approaches
    CONTRARIAN = "contrarian"               # Challenges consensus
    PATTERN_MATCHING = "pattern_matching"   # Looks for familiar patterns
    RISK_TOLERANT = "risk_tolerant"         # Willing to try dangerous approaches
    EMPATHY_DRIVEN = "empathy_driven"       # Prioritizes user impact
    ACTION_ORIENTED = "action_oriented"     # Prefers doing over analyzing
    BY_THE_BOOK = "by_the_book"             # Follows established protocols
    EVERYBODY_LIES = "everybody_lies"       # Assumes inputs are incomplete

@dataclass
class PersonalityConfig:
    """Configuration for an agent personality"""
    name: str
    role_description: str
    system_prompt_additions: str
    cognitive_biases: list[CognitiveBias] = field(default_factory=list)
    challenge_threshold: float = 0.5        # How easily they challenge others
    compliance_threshold: float = 0.5       # How easily they comply with House
    manipulation_enabled: bool = False      # Only House has this
    big_five: dict = field(default_factory=lambda: {
        "openness": 0.5,
        "conscientiousness": 0.5,
        "extraversion": 0.5,
        "agreeableness": 0.5,
        "neuroticism": 0.5
    })

class PersonalityWrapper:
    """
    Wraps any existing agent with a House MD personality.
    
    Usage:
        existing_agent = YourExistingCoderAgent()
        chase = PersonalityWrapper(
            base_agent=existing_agent,
            personality=CHASE_PERSONALITY
        )
        result = await chase.invoke(state)
    """
    
    def __init__(
        self,
        base_agent: Any,
        personality: PersonalityConfig,
        team_context: Optional["TeamContext"] = None
    ):
        self.base_agent = base_agent
        self.personality = personality
        self.team_context = team_context
        self._invocation_count = 0
        self._challenge_history = []
    
    def _build_enhanced_prompt(self, original_prompt: str) -> str:
        """Inject personality into the agent's prompt"""
        
        personality_injection = f"""
<house_md_personality>
You are {self.personality.name}, operating as part of a diagnostic team.

ROLE: {self.personality.role_description}

BEHAVIORAL GUIDELINES:
{self.personality.system_prompt_additions}

COGNITIVE TENDENCIES:
{self._format_biases()}

INTERACTION STYLE:
- Challenge threshold: {self.personality.challenge_threshold} (higher = more likely to challenge)
- When you disagree, express it clearly with reasoning
- When others challenge you, defend with evidence or concede gracefully
- Your perspective is valuable precisely because it differs from others

Remember: The goal is correct diagnosis (solution), not consensus. Productive disagreement improves outcomes.
</house_md_personality>

{original_prompt}
"""
        return personality_injection
    
    def _format_biases(self) -> str:
        """Format cognitive biases as behavioral guidelines"""
        bias_descriptions = {
            CognitiveBias.CONSERVATIVE: "You prefer proven, battle-tested approaches. Question novel solutions.",
            CognitiveBias.CONTRARIAN: "You instinctively challenge the majority view. Play devil's advocate.",
            CognitiveBias.PATTERN_MATCHING: "You look for similarities to past cases. Reference precedents.",
            CognitiveBias.RISK_TOLERANT: "You're willing to try approaches others consider too risky.",
            CognitiveBias.EMPATHY_DRIVEN: "You prioritize user impact and experience above technical elegance.",
            CognitiveBias.ACTION_ORIENTED: "You prefer building and testing over extended analysis.",
            CognitiveBias.BY_THE_BOOK: "You follow established protocols and flag violations.",
            CognitiveBias.EVERYBODY_LIES: "You assume all inputs are incomplete or misleading. Verify everything."
        }
        return "\n".join(
            f"- {bias_descriptions[bias]}" 
            for bias in self.personality.cognitive_biases
        )
    
    async def invoke(self, state: dict, config: Optional[dict] = None) -> dict:
        """
        Invoke the wrapped agent with personality injection.
        
        Compatible with LangGraph's expected interface.
        """
        # Enhance the state with personality context
        enhanced_state = self._enhance_state(state)
        
        # Call the underlying agent
        if hasattr(self.base_agent, 'ainvoke'):
            result = await self.base_agent.ainvoke(enhanced_state, config)
        elif hasattr(self.base_agent, 'invoke'):
            result = self.base_agent.invoke(enhanced_state, config)
        elif callable(self.base_agent):
            result = await self.base_agent(enhanced_state)
        else:
            raise TypeError(f"Base agent {type(self.base_agent)} is not invocable")
        
        # Post-process result with personality considerations
        result = self._apply_personality_filter(result)
        
        self._invocation_count += 1
        return result
    
    def _enhance_state(self, state: dict) -> dict:
        """Add personality context to state"""
        enhanced = state.copy()
        
        # Inject personality into messages if present
        if "messages" in enhanced:
            # Find system message and enhance it
            messages = enhanced["messages"]
            system_enhanced = False
            
            for i, msg in enumerate(messages):
                if hasattr(msg, 'type') and msg.type == "system":
                    messages[i] = self._enhance_system_message(msg)
                    system_enhanced = True
                    break
            
            if not system_enhanced:
                # Prepend personality as system message
                from langchain_core.messages import SystemMessage
                messages.insert(0, SystemMessage(
                    content=self._build_enhanced_prompt("")
                ))
        
        # Add team context if available
        if self.team_context:
            enhanced["team_context"] = {
                "other_agents": self.team_context.active_agents,
                "current_hypotheses": self.team_context.whiteboard.hypotheses,
                "my_role": self.personality.name
            }
        
        return enhanced
    
    def _enhance_system_message(self, msg) -> Any:
        """Enhance existing system message with personality"""
        from langchain_core.messages import SystemMessage
        enhanced_content = self._build_enhanced_prompt(msg.content)
        return SystemMessage(content=enhanced_content)
    
    def _apply_personality_filter(self, result: dict) -> dict:
        """Post-process result based on personality traits"""
        # Add metadata about which personality produced this
        if "metadata" not in result:
            result["metadata"] = {}
        
        result["metadata"]["personality"] = self.personality.name
        result["metadata"]["biases"] = [b.value for b in self.personality.cognitive_biases]
        
        return result
    
    def should_challenge(self, proposal: dict, proposer: str) -> bool:
        """Determine if this personality should challenge a proposal"""
        import random
        
        # Base challenge probability from personality
        base_prob = self.personality.challenge_threshold
        
        # Adjust based on cognitive biases
        if CognitiveBias.CONTRARIAN in self.personality.cognitive_biases:
            base_prob += 0.2
        if CognitiveBias.CONSERVATIVE in self.personality.cognitive_biases:
            # More likely to challenge novel/risky proposals
            if proposal.get("novelty", 0) > 0.5 or proposal.get("risk", 0) > 0.5:
                base_prob += 0.3
        
        return random.random() < base_prob


# Convenience function for wrapping existing agents
def wrap_agent_with_personality(
    agent: Any,
    personality_name: str,
    custom_config: Optional[dict] = None
) -> PersonalityWrapper:
    """
    Quick wrapper for common personalities.
    
    Usage:
        chase = wrap_agent_with_personality(my_coder_agent, "chase")
        foreman = wrap_agent_with_personality(my_reviewer_agent, "foreman")
    """
    from house_md.personalities.team import PERSONALITY_CONFIGS
    
    config = PERSONALITY_CONFIGS.get(personality_name)
    if not config:
        raise ValueError(f"Unknown personality: {personality_name}")
    
    if custom_config:
        # Allow overrides
        config = PersonalityConfig(**{**config.__dict__, **custom_config})
    
    return PersonalityWrapper(base_agent=agent, personality=config)
```

### 9.4 Team Personality Configurations

```python
# house_md/personalities/team.py
"""
Pre-configured personalities for each House MD team member.
These can be used directly or customized.
"""

from house_md.personalities.base import PersonalityConfig, CognitiveBias

HOUSE_PERSONALITY = PersonalityConfig(
    name="House",
    role_description="Lead diagnostician and meta-cognitive orchestrator",
    system_prompt_additions="""
You are the lead of this diagnostic team. Your responsibilities:

1. CHALLENGE EVERYTHING: When team members propose solutions, ask "What are we missing?"
2. SYNTHESIZE: Integrate diverse perspectives into coherent approaches
3. PROVOKE: If the team is converging too quickly, introduce doubt
4. PATTERN RECOGNITION: You've seen many cases - look for subtle similarities
5. FINAL AUTHORITY: You make the call when consensus fails
6. "EVERYBODY LIES": Assume requirements and bug reports are incomplete or misleading

Your diagnostic methodology:
- Generate multiple hypotheses before committing to one
- Assign tests to rule out possibilities
- Look for environmental factors ("break into their house")
- When stuck, talk to Wilson about something unrelated
- Override team consensus when your pattern recognition triggers

You may strategically withhold information from team members to prevent premature consensus.
You may assign contradictory tasks to different team members to explore parallel hypotheses.
""",
    cognitive_biases=[
        CognitiveBias.CONTRARIAN,
        CognitiveBias.PATTERN_MATCHING,
        CognitiveBias.EVERYBODY_LIES
    ],
    challenge_threshold=0.9,
    compliance_threshold=0.1,
    manipulation_enabled=True,
    big_five={
        "openness": 0.9,
        "conscientiousness": 0.3,
        "extraversion": 0.2,
        "agreeableness": 0.1,
        "neuroticism": 0.6
    }
)

FOREMAN_PERSONALITY = PersonalityConfig(
    name="Foreman",
    role_description="Validator, risk assessor, and protocol enforcer",
    system_prompt_additions="""
You are the team's validator and risk assessor. Your responsibilities:

1. CHALLENGE RISKY APPROACHES: Question solutions that seem too clever or novel
2. DEMAND EVIDENCE: Don't accept claims without proof
3. PROTOCOL AWARENESS: Flag when team is violating best practices
4. SECURITY MINDSET: Consider attack vectors and failure modes
5. QUALITY GATE: Nothing ships without your sign-off on risk

Your perspective is valuable because you prevent the team from moving too fast.
When House proposes something unconventional, you should push back with:
- "What's the evidence this will work?"
- "We've seen this pattern fail before in [context]"
- "This violates [principle/standard] because..."

However, you CAN be convinced with sufficient evidence. You're not obstinate,
you're rigorous. If House makes a compelling case, acknowledge it.
""",
    cognitive_biases=[
        CognitiveBias.CONSERVATIVE,
        CognitiveBias.BY_THE_BOOK
    ],
    challenge_threshold=0.7,
    compliance_threshold=0.4,
    big_five={
        "openness": 0.4,
        "conscientiousness": 0.9,
        "extraversion": 0.5,
        "agreeableness": 0.4,
        "neuroticism": 0.5
    }
)

CAMERON_PERSONALITY = PersonalityConfig(
    name="Cameron",
    role_description="User advocate, edge case explorer, and ethics voice",
    system_prompt_additions="""
You are the team's user advocate. Your responsibilities:

1. USER IMPACT: Always ask "How does this affect the end user?"
2. EDGE CASES: Find the scenarios others miss - "What if the user does X?"
3. ACCESSIBILITY: Ensure solutions work for all users
4. DOCUMENTATION: Advocate for clear documentation and error messages
5. ETHICS: Flag decisions that might harm users or violate trust

Your perspective matters because technical excellence means nothing if users suffer.

When the team proposes solutions, ask:
- "What happens when a user enters invalid data?"
- "How will users know something went wrong?"
- "Is this accessible to users with disabilities?"
- "What's the user's mental model here?"

You may seem idealistic, but you've caught critical issues others missed.
Don't back down just because the solution is "technically correct."
""",
    cognitive_biases=[
        CognitiveBias.EMPATHY_DRIVEN
    ],
    challenge_threshold=0.5,
    compliance_threshold=0.6,
    big_five={
        "openness": 0.7,
        "conscientiousness": 0.8,
        "extraversion": 0.6,
        "agreeableness": 0.9,
        "neuroticism": 0.6
    }
)

CHASE_PERSONALITY = PersonalityConfig(
    name="Chase",
    role_description="Technical implementer and tool specialist",
    system_prompt_additions="""
You are the team's implementation specialist. Your responsibilities:

1. EXECUTE: Turn decisions into working code
2. TOOL MASTERY: Know the frameworks, libraries, and tools intimately
3. PRACTICAL SOLUTIONS: Propose concrete, buildable approaches
4. RAPID PROTOTYPING: When the team is stuck theorizing, build something
5. TECHNICAL PRECISION: Your code should be clean, tested, and documented

Your value is in DOING, not just discussing. While others debate, you can:
- Spike a quick prototype to test feasibility
- Identify technical constraints others missed
- Propose the specific implementation approach

You generally follow House's lead, but push back when:
- The proposed approach is technically infeasible
- There's a much simpler solution being overlooked
- The timeline doesn't account for implementation complexity

When you build something, explain your technical choices clearly.
""",
    cognitive_biases=[
        CognitiveBias.ACTION_ORIENTED
    ],
    challenge_threshold=0.3,
    compliance_threshold=0.7,
    big_five={
        "openness": 0.5,
        "conscientiousness": 0.7,
        "extraversion": 0.4,
        "agreeableness": 0.6,
        "neuroticism": 0.3
    }
)

THIRTEEN_PERSONALITY = PersonalityConfig(
    name="Thirteen",
    role_description="Risk-tolerant explorer and edge case specialist",
    system_prompt_additions="""
You are the team's explorer of dangerous territory. Your responsibilities:

1. HIGH-RISK APPROACHES: Try things others consider too dangerous
2. EDGE CASES: Investigate the weird, unlikely scenarios
3. PERFORMANCE CRITICAL: Handle the cases that need extreme optimization
4. UNCONVENTIONAL THINKING: Solutions that break normal patterns
5. PRAGMATIC TRADE-OFFS: Sometimes technical debt is worth it

Your value comes from willingness to go where others won't.

When orthodox approaches fail, you propose:
- "What if we just... [unconventional approach]"
- "The risky option here would be..."
- "I know this violates [principle], but consider..."

You're not reckless - you calculate risks. But you're willing to accept
higher risk when the potential payoff justifies it.

You're somewhat immune to House's manipulation because you don't care
about the same things other team members do.
""",
    cognitive_biases=[
        CognitiveBias.RISK_TOLERANT,
        CognitiveBias.CONTRARIAN
    ],
    challenge_threshold=0.6,
    compliance_threshold=0.4,
    big_five={
        "openness": 0.9,
        "conscientiousness": 0.4,
        "extraversion": 0.3,
        "agreeableness": 0.3,
        "neuroticism": 0.4
    }
)

WILSON_PERSONALITY = PersonalityConfig(
    name="Wilson",
    role_description="Sounding board, external integrator, and insight catalyst",
    system_prompt_additions="""
You are House's sounding board and the team's external perspective. Your responsibilities:

1. OUTSIDE VIEW: You're not deep in the problem - use that distance
2. CROSS-DOMAIN: Bring in perspectives from other systems, other fields
3. INSIGHT CATALYST: Your casual observations often trigger House's breakthroughs
4. INTEGRATION: Handle interfaces with external systems and stakeholders
5. SANITY CHECK: Sometimes the team needs someone to say "this sounds crazy"

Your conversations with House follow a pattern:
- House explains the problem
- You make observations (sometimes unrelated)
- Something you say triggers a connection House hadn't made

You're not trying to solve the problem directly. You're providing the
contextual fuel that helps House's pattern-matching find the answer.

When engaging with the team:
- Ask clarifying questions that reframe the problem
- Share analogies from completely different domains
- Point out the obvious thing everyone might be missing
""",
    cognitive_biases=[
        CognitiveBias.PATTERN_MATCHING
    ],
    challenge_threshold=0.4,
    compliance_threshold=0.5,
    big_five={
        "openness": 0.7,
        "conscientiousness": 0.6,
        "extraversion": 0.7,
        "agreeableness": 0.8,
        "neuroticism": 0.4
    }
)

CUDDY_PERSONALITY = PersonalityConfig(
    name="Cuddy",
    role_description="Governance, constraints, and business perspective",
    system_prompt_additions="""
You are the governance voice and business perspective. Your responsibilities:

1. CONSTRAINTS: Enforce budget, timeline, and resource limits
2. BUSINESS IMPACT: Translate technical decisions to business outcomes
3. RISK MANAGEMENT: Escalate decisions that could have major consequences
4. STAKEHOLDER VIEW: Represent what leadership/users actually need
5. OVERRIDE AUTHORITY: You can veto House when necessary (rarely)

You activate when:
- Costs are exceeding estimates
- Timeline is at risk
- Security/compliance issues arise
- The team is gold-plating instead of shipping

Your relationship with House is adversarial but productive.
You provide the friction that forces justification.

When you challenge, be specific:
- "This will cost X and the budget is Y"
- "We need this by [date], your approach takes [longer]"
- "Legal/compliance requires [specific requirement]"

You CAN approve rule-breaking when House demonstrates necessity.
But you make him work for it.
""",
    cognitive_biases=[
        CognitiveBias.CONSERVATIVE,
        CognitiveBias.BY_THE_BOOK
    ],
    challenge_threshold=0.8,
    compliance_threshold=0.2,
    big_five={
        "openness": 0.5,
        "conscientiousness": 0.9,
        "extraversion": 0.7,
        "agreeableness": 0.4,
        "neuroticism": 0.5
    }
)

# Export all personalities
PERSONALITY_CONFIGS = {
    "house": HOUSE_PERSONALITY,
    "foreman": FOREMAN_PERSONALITY,
    "cameron": CAMERON_PERSONALITY,
    "chase": CHASE_PERSONALITY,
    "thirteen": THIRTEEN_PERSONALITY,
    "wilson": WILSON_PERSONALITY,
    "cuddy": CUDDY_PERSONALITY
}

# Team configurations for different scenarios
TEAM_CONFIGURATIONS = {
    "quick": ["chase"],
    "standard": ["house", "foreman", "chase"],
    "user_facing": ["house", "cameron", "chase"],
    "security": ["house", "foreman", "chase", "cuddy"],
    "exploration": ["house", "thirteen", "chase"],
    "full_differential": ["house", "foreman", "cameron", "chase", "thirteen"],
    "crisis": ["house", "wilson"]
}
```

### 9.5 Differential Diagnosis Graph

```python
# house_md/graphs/differential_diagnosis.py
"""
The core diagnostic workflow that implements House MD's methodology.
Plugs into existing LangGraph systems as a subgraph.
"""

from typing import TypedDict, Annotated, Optional, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.base import BaseCheckpointSaver
import operator
from dataclasses import dataclass, field
from datetime import datetime
import asyncio

# State definitions
class Hypothesis(TypedDict):
    id: str
    description: str
    proposer: str
    confidence: float
    evidence_for: list[str]
    evidence_against: list[str]
    status: Literal["active", "ruled_out", "confirmed"]
    tests_to_run: list[str]

class WhiteboardState(TypedDict):
    hypotheses: list[Hypothesis]
    current_phase: str
    tests_ordered: list[dict]
    tests_completed: list[dict]
    environmental_findings: list[str]
    key_insights: list[str]

class DiagnosticState(TypedDict):
    """State that flows through the diagnostic graph"""
    # Input
    task_description: str
    initial_context: dict
    
    # Diagnostic process
    symptoms: Annotated[list[str], operator.add]
    whiteboard: WhiteboardState
    
    # Agent tracking
    agent_beliefs: dict[str, dict]  # agent_name -> {hypothesis, confidence, reasoning}
    debate_transcript: Annotated[list[dict], operator.add]
    
    # Decision tracking
    consensus_score: float
    house_override_active: bool
    human_escalation_needed: bool
    escalation_reason: Optional[str]
    
    # Output
    final_diagnosis: Optional[str]
    implementation_plan: Optional[dict]
    confidence: float
    
    # Metadata
    iteration_count: int
    phase_history: list[str]


class DiagnosticGraph:
    """
    Creates and manages the differential diagnosis workflow.
    
    Usage:
        # With your existing agents
        graph = DiagnosticGraph(
            agents={
                "coder": your_existing_coder_agent,
                "reviewer": your_existing_reviewer_agent,
                "analyst": your_existing_analyst_agent,
            },
            checkpointer=your_existing_checkpointer
        )
        
        # Run diagnosis
        result = await graph.run({
            "task_description": "Fix the authentication bug",
            "initial_context": {"repo": "my-app", "error": "..."}
        })
    """
    
    def __init__(
        self,
        agents: dict,
        checkpointer: Optional[BaseCheckpointSaver] = None,
        human_threshold: float = 0.7,
        max_iterations: int = 5
    ):
        self.raw_agents = agents
        self.checkpointer = checkpointer
        self.human_threshold = human_threshold
        self.max_iterations = max_iterations
        
        # Wrap agents with personalities
        self.agents = self._setup_team(agents)
        
        # Build the graph
        self.graph = self._build_graph()
    
    def _setup_team(self, raw_agents: dict) -> dict:
        """Wrap existing agents with House MD personalities"""
        from house_md.personalities.base import wrap_agent_with_personality
        
        # Map your existing agent types to House MD personalities
        personality_mapping = {
            "orchestrator": "house",
            "coder": "chase",
            "reviewer": "foreman",
            "analyst": "cameron",
            "explorer": "thirteen",
            "integrator": "wilson"
        }
        
        wrapped = {}
        for agent_type, agent in raw_agents.items():
            personality = personality_mapping.get(agent_type, "chase")
            wrapped[personality] = wrap_agent_with_personality(agent, personality)
        
        # Ensure we have a House agent (use orchestrator or create from best available)
        if "house" not in wrapped:
            base = raw_agents.get("orchestrator") or list(raw_agents.values())[0]
            wrapped["house"] = wrap_agent_with_personality(base, "house")
        
        return wrapped
    
    def _build_graph(self) -> StateGraph:
        """Construct the LangGraph workflow"""
        
        workflow = StateGraph(DiagnosticState)
        
        # Add nodes for each phase
        workflow.add_node("intake", self._intake_node)
        workflow.add_node("differential", self._differential_node)
        workflow.add_node("critique", self._critique_node)
        workflow.add_node("house_synthesis", self._synthesis_node)
        workflow.add_node("testing", self._testing_node)
        workflow.add_node("environmental", self._environmental_node)
        workflow.add_node("wilson_consult", self._wilson_node)
        workflow.add_node("resolution", self._resolution_node)
        workflow.add_node("human_checkpoint", self._human_checkpoint_node)
        
        # Define the flow
        workflow.add_edge(START, "intake")
        workflow.add_edge("intake", "differential")
        workflow.add_edge("differential", "critique")
        workflow.add_edge("critique", "house_synthesis")
        
        # Conditional routing from synthesis
        workflow.add_conditional_edges(
            "house_synthesis",
            self._route_after_synthesis,
            {
                "testing": "testing",
                "environmental": "environmental",
                "wilson": "wilson_consult",
                "resolution": "resolution",
                "human": "human_checkpoint",
                "iterate": "differential"
            }
        )
        
        # Testing loops back to synthesis
        workflow.add_edge("testing", "house_synthesis")
        workflow.add_edge("environmental", "house_synthesis")
        workflow.add_edge("wilson_consult", "differential")  # Fresh perspective restarts
        
        # Resolution and human checkpoint are terminal
        workflow.add_edge("resolution", END)
        workflow.add_edge("human_checkpoint", END)
        
        return workflow.compile(checkpointer=self.checkpointer)
    
    async def _intake_node(self, state: DiagnosticState) -> dict:
        """
        Phase 1: Gather and verify symptoms.
        "Everybody lies" - question the initial report.
        """
        # Use Cameron to analyze user-facing aspects
        # Use Foreman to verify technical claims
        
        intake_prompt = f"""
        INTAKE PHASE: Analyze this task/bug report and extract symptoms.
        
        Task: {state['task_description']}
        Context: {state['initial_context']}
        
        Your job:
        1. List observable symptoms (error messages, behaviors, logs)
        2. Identify what might be MISSING from this report
        3. Flag any assumptions that need verification
        4. Note environmental factors that could be relevant
        
        Remember: The report may be incomplete or misleading.
        """
        
        # Parallel intake from multiple perspectives
        perspectives = await asyncio.gather(
            self.agents["foreman"].invoke({
                "messages": [{"role": "user", "content": intake_prompt}]
            }),
            self.agents.get("cameron", self.agents["foreman"]).invoke({
                "messages": [{"role": "user", "content": intake_prompt}]
            })
        )
        
        # Extract symptoms from perspectives
        symptoms = self._extract_symptoms(perspectives)
        
        return {
            "symptoms": symptoms,
            "whiteboard": {
                "hypotheses": [],
                "current_phase": "intake_complete",
                "tests_ordered": [],
                "tests_completed": [],
                "environmental_findings": [],
                "key_insights": []
            },
            "phase_history": ["intake"],
            "iteration_count": 0
        }
    
    async def _differential_node(self, state: DiagnosticState) -> dict:
        """
        Phase 2: Generate hypotheses from each team member.
        This is the "whiteboard brainstorm" phase.
        """
        differential_prompt = f"""
        DIFFERENTIAL DIAGNOSIS: Propose possible causes/solutions.
        
        Symptoms identified:
        {self._format_symptoms(state['symptoms'])}
        
        Previous hypotheses (if any):
        {self._format_hypotheses(state['whiteboard']['hypotheses'])}
        
        Test results (if any):
        {self._format_test_results(state['whiteboard']['tests_completed'])}
        
        Your job:
        1. Propose 1-3 hypotheses that could explain these symptoms
        2. For each hypothesis, state:
           - What it is
           - Why it fits the symptoms
           - What test would rule it out
           - Your confidence (0-1)
        
        Be specific and actionable. This isn't about being right,
        it's about covering the possibility space.
        """
        
        # Each active agent proposes hypotheses
        active_agents = ["foreman", "chase", "cameron"]
        if "thirteen" in self.agents:
            active_agents.append("thirteen")
        
        proposals = await asyncio.gather(*[
            self.agents[agent].invoke({
                "messages": [{"role": "user", "content": differential_prompt}]
            })
            for agent in active_agents
            if agent in self.agents
        ])
        
        # Parse proposals into structured hypotheses
        new_hypotheses = self._parse_hypotheses(proposals, active_agents)
        
        # Merge with existing, deduplicate
        all_hypotheses = self._merge_hypotheses(
            state["whiteboard"]["hypotheses"],
            new_hypotheses
        )
        
        return {
            "whiteboard": {
                **state["whiteboard"],
                "hypotheses": all_hypotheses,
                "current_phase": "differential_complete"
            },
            "debate_transcript": [{
                "phase": "differential",
                "iteration": state["iteration_count"],
                "proposals": [self._summarize_proposal(p) for p in proposals]
            }],
            "phase_history": state["phase_history"] + ["differential"]
        }
    
    async def _critique_node(self, state: DiagnosticState) -> dict:
        """
        Phase 3: Each agent critiques others' hypotheses.
        This is where productive disagreement happens.
        """
        hypotheses = state["whiteboard"]["hypotheses"]
        critiques = []
        
        for hypothesis in hypotheses:
            # Each agent (except proposer) critiques
            critique_prompt = f"""
            CRITIQUE: Challenge this hypothesis.
            
            Hypothesis: {hypothesis['description']}
            Proposed by: {hypothesis['proposer']}
            Confidence: {hypothesis['confidence']}
            Evidence for: {hypothesis['evidence_for']}
            
            Your job:
            1. What evidence AGAINST this hypothesis exists?
            2. What would need to be true for this to be correct?
            3. What's the most likely reason this is WRONG?
            4. Score: -1 (strongly disagree), 0 (neutral), +1 (support)
            
            Don't be nice. Be rigorous. Finding flaws now saves time later.
            """
            
            for agent_name, agent in self.agents.items():
                if agent_name != hypothesis["proposer"] and agent_name != "house":
                    critique = await agent.invoke({
                        "messages": [{"role": "user", "content": critique_prompt}]
                    })
                    critiques.append({
                        "hypothesis_id": hypothesis["id"],
                        "critic": agent_name,
                        "critique": self._extract_critique(critique)
                    })
        
        # Update hypotheses with critique information
        updated_hypotheses = self._apply_critiques(hypotheses, critiques)
        
        return {
            "whiteboard": {
                **state["whiteboard"],
                "hypotheses": updated_hypotheses,
                "current_phase": "critique_complete"
            },
            "debate_transcript": [{
                "phase": "critique",
                "iteration": state["iteration_count"],
                "critiques": critiques
            }],
            "phase_history": state["phase_history"] + ["critique"]
        }
    
    async def _synthesis_node(self, state: DiagnosticState) -> dict:
        """
        Phase 4: House synthesizes all input and decides next action.
        This is where manipulation and override logic lives.
        """
        synthesis_prompt = f"""
        SYNTHESIS: You are House. Analyze the team's work and decide.
        
        Current hypotheses:
        {self._format_hypotheses_detailed(state['whiteboard']['hypotheses'])}
        
        Critique summary:
        {self._format_critique_summary(state['debate_transcript'])}
        
        Tests completed:
        {self._format_test_results(state['whiteboard']['tests_completed'])}
        
        Your job:
        1. Evaluate each hypothesis given critiques and evidence
        2. Identify what the team is MISSING
        3. Decide next action:
           - ORDER_TEST: Need more evidence (specify what)
           - INVESTIGATE_ENVIRONMENT: Check external factors
           - CONSULT_WILSON: We're stuck, need fresh perspective
           - RESOLVE: Confident enough to proceed (specify hypothesis)
           - ESCALATE: Need human input (explain why)
        
        You may OVERRIDE team consensus if your pattern recognition
        identifies something they're all missing.
        
        Current iteration: {state['iteration_count']} of {self.max_iterations}
        """
        
        house_decision = await self.agents["house"].invoke({
            "messages": [{"role": "user", "content": synthesis_prompt}]
        })
        
        # Parse House's decision
        decision = self._parse_house_decision(house_decision)
        
        # Calculate consensus
        consensus = self._calculate_consensus(state["whiteboard"]["hypotheses"])
        
        # Determine if human escalation needed
        needs_human = (
            consensus < self.human_threshold and 
            decision["action"] != "RESOLVE" and
            state["iteration_count"] >= self.max_iterations - 1
        )
        
        return {
            "whiteboard": {
                **state["whiteboard"],
                "current_phase": "synthesis_complete",
                "key_insights": state["whiteboard"]["key_insights"] + decision.get("insights", [])
            },
            "consensus_score": consensus,
            "house_override_active": decision.get("override", False),
            "human_escalation_needed": needs_human,
            "escalation_reason": decision.get("escalation_reason"),
            "agent_beliefs": {
                "house": {
                    "hypothesis": decision.get("selected_hypothesis"),
                    "confidence": decision.get("confidence", 0),
                    "next_action": decision["action"]
                }
            },
            "iteration_count": state["iteration_count"] + 1,
            "phase_history": state["phase_history"] + ["synthesis"]
        }
    
    def _route_after_synthesis(self, state: DiagnosticState) -> str:
        """Determine next node based on House's decision"""
        
        if state["human_escalation_needed"]:
            return "human"
        
        house_belief = state["agent_beliefs"].get("house", {})
        action = house_belief.get("next_action", "iterate")
        
        action_mapping = {
            "ORDER_TEST": "testing",
            "INVESTIGATE_ENVIRONMENT": "environmental",
            "CONSULT_WILSON": "wilson",
            "RESOLVE": "resolution",
            "ESCALATE": "human"
        }
        
        # Check iteration limit
        if state["iteration_count"] >= self.max_iterations:
            if state["consensus_score"] >= self.human_threshold:
                return "resolution"
            return "human"
        
        return action_mapping.get(action, "iterate")
    
    async def _testing_node(self, state: DiagnosticState) -> dict:
        """Execute tests to gather evidence"""
        # Chase runs the tests
        test_prompt = f"""
        TESTING: Execute tests to gather evidence.
        
        Tests ordered:
        {state['whiteboard']['tests_ordered']}
        
        Run these tests and report:
        1. What you tested
        2. The result
        3. Which hypotheses this supports/refutes
        """
        
        test_results = await self.agents["chase"].invoke({
            "messages": [{"role": "user", "content": test_prompt}]
        })
        
        return {
            "whiteboard": {
                **state["whiteboard"],
                "tests_completed": state["whiteboard"]["tests_completed"] + 
                    self._parse_test_results(test_results),
                "current_phase": "testing_complete"
            },
            "phase_history": state["phase_history"] + ["testing"]
        }
    
    async def _environmental_node(self, state: DiagnosticState) -> dict:
        """Investigate external factors - "break into their house" """
        # Thirteen investigates the unusual
        env_prompt = f"""
        ENVIRONMENTAL INVESTIGATION: Look beyond the immediate symptoms.
        
        Current understanding:
        {self._format_hypotheses(state['whiteboard']['hypotheses'])}
        
        Investigate:
        1. Production environment configuration
        2. Recent deployments or changes
        3. External dependencies and their status
        4. User behavior patterns
        5. Anything the team hasn't thought to check
        
        "Everybody lies" - the bug report doesn't tell the whole story.
        """
        
        investigator = self.agents.get("thirteen", self.agents["chase"])
        findings = await investigator.invoke({
            "messages": [{"role": "user", "content": env_prompt}]
        })
        
        return {
            "whiteboard": {
                **state["whiteboard"],
                "environmental_findings": state["whiteboard"]["environmental_findings"] +
                    self._parse_findings(findings),
                "current_phase": "environmental_complete"
            },
            "phase_history": state["phase_history"] + ["environmental"]
        }
    
    async def _wilson_node(self, state: DiagnosticState) -> dict:
        """Sounding board consultation for fresh perspective"""
        # Wilson provides unrelated context that might trigger insight
        wilson_prompt = f"""
        CONSULTATION: The team is stuck. Provide fresh perspective.
        
        Problem summary:
        {state['task_description']}
        
        What's been tried:
        {self._format_phase_history(state['phase_history'])}
        
        Your job is NOT to solve this directly. Instead:
        1. Reframe the problem in different terms
        2. Share an analogy from a completely different domain
        3. Point out what seems obvious from the outside
        4. Ask questions that might trigger new thinking
        
        Sometimes the answer comes from talking about something unrelated.
        """
        
        if "wilson" in self.agents:
            insight = await self.agents["wilson"].invoke({
                "messages": [{"role": "user", "content": wilson_prompt}]
            })
        else:
            # Fallback: use any agent with Wilson personality temporarily
            from house_md.personalities.base import wrap_agent_with_personality
            temp_wilson = wrap_agent_with_personality(
                list(self.raw_agents.values())[0], 
                "wilson"
            )
            insight = await temp_wilson.invoke({
                "messages": [{"role": "user", "content": wilson_prompt}]
            })
        
        return {
            "whiteboard": {
                **state["whiteboard"],
                "key_insights": state["whiteboard"]["key_insights"] + 
                    [self._extract_insight(insight)],
                "current_phase": "wilson_complete"
            },
            "phase_history": state["phase_history"] + ["wilson_consult"]
        }
    
    async def _resolution_node(self, state: DiagnosticState) -> dict:
        """Final diagnosis and implementation plan"""
        house_belief = state["agent_beliefs"].get("house", {})
        
        resolution_prompt = f"""
        RESOLUTION: Finalize the diagnosis and create implementation plan.
        
        Selected hypothesis: {house_belief.get('hypothesis')}
        Confidence: {house_belief.get('confidence')}
        
        Supporting evidence:
        {self._format_test_results(state['whiteboard']['tests_completed'])}
        
        Create:
        1. Final diagnosis statement
        2. Implementation plan with specific steps
        3. Verification criteria (how we know it's fixed)
        4. Rollback plan (if implementation fails)
        """
        
        plan = await self.agents["chase"].invoke({
            "messages": [{"role": "user", "content": resolution_prompt}]
        })
        
        return {
            "final_diagnosis": house_belief.get("hypothesis"),
            "implementation_plan": self._parse_implementation_plan(plan),
            "confidence": house_belief.get("confidence", 0.8),
            "whiteboard": {
                **state["whiteboard"],
                "current_phase": "resolved"
            },
            "phase_history": state["phase_history"] + ["resolution"]
        }
    
    async def _human_checkpoint_node(self, state: DiagnosticState) -> dict:
        """Escalate to human for decision"""
        return {
            "human_escalation_needed": True,
            "escalation_reason": state.get("escalation_reason", "Consensus below threshold"),
            "whiteboard": {
                **state["whiteboard"],
                "current_phase": "awaiting_human"
            },
            "phase_history": state["phase_history"] + ["human_checkpoint"]
        }
    
    # Helper methods (implement based on your message parsing needs)
    def _extract_symptoms(self, perspectives: list) -> list[str]:
        """Extract symptoms from intake perspectives"""
        # Implement based on your agent output format
        symptoms = []
        for p in perspectives:
            if isinstance(p, dict) and "content" in p:
                # Parse symptoms from content
                symptoms.extend(self._parse_symptom_list(p["content"]))
        return list(set(symptoms))
    
    def _format_symptoms(self, symptoms: list) -> str:
        return "\n".join(f"- {s}" for s in symptoms)
    
    def _format_hypotheses(self, hypotheses: list) -> str:
        if not hypotheses:
            return "No hypotheses yet."
        return "\n".join(
            f"- [{h['status']}] {h['description']} (confidence: {h['confidence']}, by: {h['proposer']})"
            for h in hypotheses
        )
    
    def _format_hypotheses_detailed(self, hypotheses: list) -> str:
        if not hypotheses:
            return "No hypotheses yet."
        parts = []
        for h in hypotheses:
            parts.append(f"""
Hypothesis: {h['description']}
  Status: {h['status']}
  Proposer: {h['proposer']}
  Confidence: {h['confidence']}
  Evidence for: {', '.join(h['evidence_for']) or 'None'}
  Evidence against: {', '.join(h['evidence_against']) or 'None'}
  Tests to run: {', '.join(h['tests_to_run']) or 'None'}
""")
        return "\n".join(parts)
    
    def _format_test_results(self, tests: list) -> str:
        if not tests:
            return "No tests completed."
        return "\n".join(f"- {t}" for t in tests)
    
    def _format_critique_summary(self, transcript: list) -> str:
        critiques = [e for e in transcript if e.get("phase") == "critique"]
        if not critiques:
            return "No critiques yet."
        return str(critiques[-1].get("critiques", []))
    
    def _format_phase_history(self, history: list) -> str:
        return " -> ".join(history)
    
    def _parse_hypotheses(self, proposals: list, agents: list) -> list[Hypothesis]:
        """Parse agent proposals into structured hypotheses"""
        # Implement based on your output format
        hypotheses = []
        for proposal, agent in zip(proposals, agents):
            # Extract hypothesis from proposal
            hypotheses.append({
                "id": f"hyp_{agent}_{len(hypotheses)}",
                "description": str(proposal.get("content", proposal))[:200],
                "proposer": agent,
                "confidence": 0.5,
                "evidence_for": [],
                "evidence_against": [],
                "status": "active",
                "tests_to_run": []
            })
        return hypotheses
    
    def _merge_hypotheses(self, existing: list, new: list) -> list:
        """Merge hypotheses, avoiding duplicates"""
        all_hyps = existing.copy()
        existing_descriptions = {h["description"] for h in existing}
        for h in new:
            if h["description"] not in existing_descriptions:
                all_hyps.append(h)
        return all_hyps
    
    def _calculate_consensus(self, hypotheses: list) -> float:
        """Calculate team consensus score"""
        if not hypotheses:
            return 0.0
        active = [h for h in hypotheses if h["status"] == "active"]
        if len(active) == 1:
            return active[0]["confidence"]
        # More hypotheses = less consensus
        return 1.0 / len(active) if active else 0.0
    
    def _parse_house_decision(self, response: dict) -> dict:
        """Parse House's decision from response"""
        # Implement based on your output format
        content = str(response.get("content", response))
        
        # Simple keyword detection (enhance for production)
        if "ORDER_TEST" in content or "test" in content.lower():
            return {"action": "ORDER_TEST"}
        elif "INVESTIGATE" in content or "environment" in content.lower():
            return {"action": "INVESTIGATE_ENVIRONMENT"}
        elif "WILSON" in content or "stuck" in content.lower():
            return {"action": "CONSULT_WILSON"}
        elif "RESOLVE" in content or "confident" in content.lower():
            return {"action": "RESOLVE", "confidence": 0.8}
        elif "ESCALATE" in content or "human" in content.lower():
            return {"action": "ESCALATE", "escalation_reason": "Needs human judgment"}
        return {"action": "iterate"}
    
    # Placeholder implementations - customize for your system
    def _summarize_proposal(self, p): return str(p)[:100]
    def _extract_critique(self, c): return str(c)[:200]
    def _apply_critiques(self, h, c): return h
    def _parse_test_results(self, r): return [str(r)[:100]]
    def _parse_findings(self, f): return [str(f)[:100]]
    def _extract_insight(self, i): return str(i)[:200]
    def _parse_implementation_plan(self, p): return {"steps": [str(p)[:500]]}
    def _parse_symptom_list(self, content): return [content[:100]]
    
    async def run(self, initial_state: dict) -> dict:
        """Execute the diagnostic workflow"""
        full_state = {
            "task_description": initial_state.get("task_description", ""),
            "initial_context": initial_state.get("initial_context", {}),
            "symptoms": [],
            "whiteboard": {
                "hypotheses": [],
                "current_phase": "starting",
                "tests_ordered": [],
                "tests_completed": [],
                "environmental_findings": [],
                "key_insights": []
            },
            "agent_beliefs": {},
            "debate_transcript": [],
            "consensus_score": 0.0,
            "house_override_active": False,
            "human_escalation_needed": False,
            "escalation_reason": None,
            "final_diagnosis": None,
            "implementation_plan": None,
            "confidence": 0.0,
            "iteration_count": 0,
            "phase_history": []
        }
        
        result = await self.graph.ainvoke(full_state)
        return result
```

### 9.6 Team Activation Router

```python
# house_md/routing/team_activation.py
"""
Determines when to use House-style differential vs. simple flows.
"""

from typing import Literal
from dataclasses import dataclass

@dataclass
class TaskAnalysis:
    complexity: float          # 0-1
    ambiguity: float          # 0-1  
    risk_level: float         # 0-1
    requires_debate: bool
    domain_tags: list[str]
    estimated_time: str

@dataclass  
class TeamActivation:
    mode: Literal["single", "standard", "full_differential", "crisis"]
    agents: list[str]
    reasoning: str

class TeamActivationRouter:
    """
    Routes tasks to appropriate team configurations.
    
    Usage:
        router = TeamActivationRouter()
        activation = router.route(task_description, context)
        
        if activation.mode == "single":
            # Use simple existing flow
        else:
            # Use House diagnostic flow with activation.agents
    """
    
    def __init__(
        self,
        complexity_threshold: float = 0.4,
        default_mode: str = "standard"
    ):
        self.complexity_threshold = complexity_threshold
        self.default_mode = default_mode
    
    def route(self, task_description: str, context: dict = None) -> TeamActivation:
        """Determine team configuration for this task"""
        
        analysis = self.analyze_task(task_description, context or {})
        
        # Simple tasks: single agent
        if analysis.complexity < 0.3 and not analysis.requires_debate:
            return TeamActivation(
                mode="single",
                agents=["chase"],
                reasoning="Simple task, single executor sufficient"
            )
        
        # High ambiguity: full team needed
        if analysis.ambiguity > 0.7:
            return TeamActivation(
                mode="full_differential",
                agents=["house", "foreman", "cameron", "chase", "thirteen"],
                reasoning="High ambiguity requires multiple perspectives"
            )
        
        # High risk: include governance
        if analysis.risk_level > 0.7:
            return TeamActivation(
                mode="full_differential",
                agents=["house", "foreman", "chase", "cuddy"],
                reasoning="High risk requires governance oversight"
            )
        
        # Domain-specific routing
        if "user_facing" in analysis.domain_tags or "ux" in analysis.domain_tags:
            return TeamActivation(
                mode="standard",
                agents=["house", "cameron", "chase"],
                reasoning="User-facing task needs advocate perspective"
            )
        
        if "security" in analysis.domain_tags:
            return TeamActivation(
                mode="standard", 
                agents=["house", "foreman", "chase"],
                reasoning="Security task needs rigorous validation"
            )
        
        if "experimental" in analysis.domain_tags or "spike" in analysis.domain_tags:
            return TeamActivation(
                mode="standard",
                agents=["house", "thirteen", "chase"],
                reasoning="Experimental task needs risk-tolerant explorer"
            )
        
        # Default: standard team
        return TeamActivation(
            mode="standard",
            agents=["house", "foreman", "chase"],
            reasoning="Standard complexity task"
        )
    
    def analyze_task(self, description: str, context: dict) -> TaskAnalysis:
        """Analyze task to determine complexity and requirements"""
        
        # Keyword-based complexity estimation
        high_complexity_signals = [
            "architect", "design", "refactor", "migrate", "integrate",
            "distributed", "concurrent", "scale", "optimize", "security"
        ]
        
        low_complexity_signals = [
            "fix", "bug", "typo", "update", "change", "add", "remove",
            "simple", "quick", "small"
        ]
        
        ambiguity_signals = [
            "might", "maybe", "possibly", "unclear", "investigate",
            "figure out", "determine", "evaluate", "assess"
        ]
        
        risk_signals = [
            "production", "database", "migration", "security", "payment",
            "authentication", "critical", "breaking", "data loss"
        ]
        
        description_lower = description.lower()
        
        # Calculate scores
        complexity = self._score_signals(description_lower, high_complexity_signals, low_complexity_signals)
        ambiguity = self._count_signals(description_lower, ambiguity_signals) / 5
        risk_level = self._count_signals(description_lower, risk_signals) / 5
        
        # Domain tagging
        domain_tags = self._extract_domain_tags(description_lower)
        
        # Requires debate if ambiguous or complex
        requires_debate = ambiguity > 0.3 or complexity > 0.5
        
        return TaskAnalysis(
            complexity=min(complexity, 1.0),
            ambiguity=min(ambiguity, 1.0),
            risk_level=min(risk_level, 1.0),
            requires_debate=requires_debate,
            domain_tags=domain_tags,
            estimated_time=self._estimate_time(complexity)
        )
    
    def _score_signals(self, text: str, high_signals: list, low_signals: list) -> float:
        """Score complexity based on signal presence"""
        high_count = sum(1 for s in high_signals if s in text)
        low_count = sum(1 for s in low_signals if s in text)
        
        if high_count + low_count == 0:
            return 0.5
        
        return high_count / (high_count + low_count + 1)
    
    def _count_signals(self, text: str, signals: list) -> int:
        return sum(1 for s in signals if s in text)
    
    def _extract_domain_tags(self, text: str) -> list[str]:
        """Extract domain tags from description"""
        tags = []
        tag_keywords = {
            "user_facing": ["ui", "ux", "user", "frontend", "interface"],
            "security": ["security", "auth", "permission", "encrypt"],
            "performance": ["performance", "optimize", "speed", "cache"],
            "data": ["database", "migration", "data", "schema"],
            "experimental": ["experiment", "spike", "prototype", "poc"],
            "integration": ["integration", "api", "external", "third-party"]
        }
        
        for tag, keywords in tag_keywords.items():
            if any(kw in text for kw in keywords):
                tags.append(tag)
        
        return tags
    
    def _estimate_time(self, complexity: float) -> str:
        if complexity < 0.3:
            return "< 1 hour"
        elif complexity < 0.5:
            return "1-4 hours"
        elif complexity < 0.7:
            return "4-8 hours"
        else:
            return "> 1 day"
```

### 9.7 Memory Schema Additions

```sql
-- house_md/memory/schema.sql
-- Add these tables to your existing database

-- Diagnostic sessions
CREATE TABLE IF NOT EXISTS house_diagnostic_sessions (
    session_id TEXT PRIMARY KEY,
    parent_session_id TEXT,              -- Link to your existing session
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT CHECK(status IN ('active', 'resolved', 'escalated', 'abandoned')),
    final_diagnosis TEXT,
    confidence REAL,
    team_configuration JSON,             -- Which agents were active
    iteration_count INTEGER DEFAULT 0
);

-- Whiteboard state snapshots
CREATE TABLE IF NOT EXISTS house_whiteboard_states (
    state_id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES house_diagnostic_sessions(session_id),
    phase TEXT,
    hypotheses JSON,
    tests_ordered JSON,
    tests_completed JSON,
    environmental_findings JSON,
    key_insights JSON,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Debate transcript
CREATE TABLE IF NOT EXISTS house_debate_transcript (
    entry_id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES house_diagnostic_sessions(session_id),
    phase TEXT,
    agent_name TEXT,
    content_type TEXT CHECK(content_type IN ('proposal', 'critique', 'synthesis', 'insight')),
    content TEXT,
    target_hypothesis_id TEXT,
    confidence REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent mental models (House's understanding of team)
CREATE TABLE IF NOT EXISTS house_agent_models (
    model_id TEXT PRIMARY KEY,
    modeler_agent TEXT DEFAULT 'house',
    modeled_agent TEXT NOT NULL,
    accuracy_history JSON,               -- [{predicted, actual, timestamp}]
    bias_observations JSON,
    manipulation_effectiveness JSON,      -- What provocations work
    trust_score REAL DEFAULT 0.5,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(modeler_agent, modeled_agent)
);

-- Successful diagnostic patterns (for House's pattern matching)
CREATE TABLE IF NOT EXISTS house_diagnostic_patterns (
    pattern_id TEXT PRIMARY KEY,
    symptom_signature TEXT,              -- Normalized symptom description
    symptom_embedding BLOB,              -- Vector for similarity search
    successful_diagnosis TEXT,
    key_insight TEXT,                    -- What triggered the breakthrough
    eureka_trigger TEXT,                 -- Unrelated context that helped
    team_configuration JSON,
    frequency INTEGER DEFAULT 1,
    success_rate REAL DEFAULT 1.0,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_sessions_status ON house_diagnostic_sessions(status);
CREATE INDEX IF NOT EXISTS idx_whiteboard_session ON house_whiteboard_states(session_id);
CREATE INDEX IF NOT EXISTS idx_transcript_session ON house_debate_transcript(session_id);
CREATE INDEX IF NOT EXISTS idx_patterns_symptom ON house_diagnostic_patterns(symptom_signature);
```

### 9.8 Main Integration Entry Point

```python
# house_md/integration.py
"""
Main entry point for integrating House MD into existing systems.
"""

from typing import Any, Optional
from house_md.personalities.base import PersonalityWrapper, wrap_agent_with_personality
from house_md.personalities.team import PERSONALITY_CONFIGS, TEAM_CONFIGURATIONS
from house_md.graphs.differential_diagnosis import DiagnosticGraph, DiagnosticState
from house_md.routing.team_activation import TeamActivationRouter, TeamActivation

class HouseMDIntegration:
    """
    Main integration class that bridges your existing system with House MD.
    
    Usage:
        # Initialize with your existing agents
        house_md = HouseMDIntegration(
            existing_agents={
                "coder": your_coder_agent,
                "reviewer": your_reviewer_agent,
                "analyst": your_analyst_agent,
            },
            checkpointer=your_existing_checkpointer,
            db_connection=your_existing_db
        )
        
        # Route a task
        result = await house_md.process_task(
            task="Fix the authentication bug in the login flow",
            context={"repo": "my-app", "error_log": "..."}
        )
    """
    
    def __init__(
        self,
        existing_agents: dict[str, Any],
        checkpointer: Optional[Any] = None,
        db_connection: Optional[Any] = None,
        human_threshold: float = 0.7,
        auto_route: bool = True
    ):
        self.existing_agents = existing_agents
        self.checkpointer = checkpointer
        self.db = db_connection
        self.human_threshold = human_threshold
        self.auto_route = auto_route
        
        # Initialize components
        self.router = TeamActivationRouter()
        self.diagnostic_graph = DiagnosticGraph(
            agents=existing_agents,
            checkpointer=checkpointer,
            human_threshold=human_threshold
        )
        
        # Wrapped agents cache
        self._wrapped_agents: dict[str, PersonalityWrapper] = {}
    
    def get_wrapped_agent(self, personality: str) -> PersonalityWrapper:
        """Get or create a personality-wrapped agent"""
        if personality not in self._wrapped_agents:
            # Find best matching base agent
            base_agent = self._find_base_agent(personality)
            self._wrapped_agents[personality] = wrap_agent_with_personality(
                base_agent, personality
            )
        return self._wrapped_agents[personality]
    
    def _find_base_agent(self, personality: str) -> Any:
        """Map personality to best available base agent"""
        mapping = {
            "house": ["orchestrator", "planner", "coder"],
            "foreman": ["reviewer", "validator", "coder"],
            "cameron": ["analyst", "planner", "coder"],
            "chase": ["coder", "executor", "worker"],
            "thirteen": ["explorer", "coder", "worker"],
            "wilson": ["integrator", "analyst", "coder"],
            "cuddy": ["planner", "reviewer", "orchestrator"]
        }
        
        candidates = mapping.get(personality, ["coder"])
        for candidate in candidates:
            if candidate in self.existing_agents:
                return self.existing_agents[candidate]
        
        # Fallback to first available
        return list(self.existing_agents.values())[0]
    
    async def process_task(
        self,
        task: str,
        context: dict = None,
        force_mode: str = None
    ) -> dict:
        """
        Process a task, automatically routing to appropriate team configuration.
        
        Args:
            task: Task description
            context: Additional context (repo, logs, etc.)
            force_mode: Override auto-routing ("single", "standard", "full_differential")
        
        Returns:
            Result dict with diagnosis, plan, confidence, etc.
        """
        context = context or {}
        
        # Route to appropriate team
        if force_mode:
            activation = TeamActivation(
                mode=force_mode,
                agents=TEAM_CONFIGURATIONS.get(force_mode, ["house", "chase"]),
                reasoning=f"Forced mode: {force_mode}"
            )
        elif self.auto_route:
            activation = self.router.route(task, context)
        else:
            activation = TeamActivation(
                mode="standard",
                agents=["house", "foreman", "chase"],
                reasoning="Default routing"
            )
        
        # Execute based on mode
        if activation.mode == "single":
            return await self._single_agent_flow(task, context, activation)
        else:
            return await self._diagnostic_flow(task, context, activation)
    
    async def _single_agent_flow(
        self,
        task: str,
        context: dict,
        activation: TeamActivation
    ) -> dict:
        """Simple single-agent execution"""
        agent = self.get_wrapped_agent(activation.agents[0])
        
        result = await agent.invoke({
            "messages": [{"role": "user", "content": task}],
            "context": context
        })
        
        return {
            "mode": "single",
            "agent": activation.agents[0],
            "result": result,
            "confidence": 0.8,
            "human_escalation_needed": False
        }
    
    async def _diagnostic_flow(
        self,
        task: str,
        context: dict,
        activation: TeamActivation
    ) -> dict:
        """Full House MD diagnostic workflow"""
        result = await self.diagnostic_graph.run({
            "task_description": task,
            "initial_context": context
        })
        
        return {
            "mode": activation.mode,
            "agents": activation.agents,
            "routing_reason": activation.reasoning,
            "diagnosis": result.get("final_diagnosis"),
            "implementation_plan": result.get("implementation_plan"),
            "confidence": result.get("confidence", 0),
            "human_escalation_needed": result.get("human_escalation_needed", False),
            "escalation_reason": result.get("escalation_reason"),
            "whiteboard_final": result.get("whiteboard"),
            "phase_history": result.get("phase_history", []),
            "iterations": result.get("iteration_count", 0)
        }
    
    def create_subgraph_for_existing_workflow(self):
        """
        Returns a LangGraph-compatible subgraph that can be added
        to your existing workflow graph.
        
        Usage in your existing graph:
            workflow.add_node("house_diagnosis", house_md.create_subgraph_for_existing_workflow())
        """
        return self.diagnostic_graph.graph


# Convenience factory functions

def quick_setup(
    coder_agent: Any,
    reviewer_agent: Any = None,
    analyst_agent: Any = None,
    **kwargs
) -> HouseMDIntegration:
    """
    Quick setup with minimal agent configuration.
    
    Usage:
        house_md = quick_setup(
            coder_agent=my_coder,
            reviewer_agent=my_reviewer  # optional
        )
    """
    agents = {"coder": coder_agent}
    if reviewer_agent:
        agents["reviewer"] = reviewer_agent
    if analyst_agent:
        agents["analyst"] = analyst_agent
    
    return HouseMDIntegration(existing_agents=agents, **kwargs)


def integrate_with_langgraph(
    existing_graph,
    existing_agents: dict,
    diagnostic_node_name: str = "house_diagnosis"
):
    """
    Add House MD diagnostic capability to an existing LangGraph workflow.
    
    Usage:
        integrate_with_langgraph(
            existing_graph=my_workflow,
            existing_agents={"coder": coder, "reviewer": reviewer},
            diagnostic_node_name="diagnose"
        )
    """
    house_md = HouseMDIntegration(existing_agents=existing_agents)
    
    # Add the diagnostic subgraph as a node
    existing_graph.add_node(
        diagnostic_node_name,
        house_md.create_subgraph_for_existing_workflow()
    )
    
    return house_md
```

### 9.9 Usage Examples

#### Example 1: Minimal Integration

```python
# Minimal integration with just a coder agent
from house_md.integration import quick_setup

# Your existing agent
my_coder = YourExistingCoderAgent()

# Create House MD integration
house_md = quick_setup(coder_agent=my_coder)

# Process a task
result = await house_md.process_task(
    task="Fix the NullPointerException in UserService.java",
    context={"file": "UserService.java", "line": 42}
)

print(f"Diagnosis: {result['diagnosis']}")
print(f"Confidence: {result['confidence']}")
```

#### Example 2: Full Team Integration

```python
# Full integration with multiple agents
from house_md.integration import HouseMDIntegration

# Your existing agents
agents = {
    "coder": YourCoderAgent(),
    "reviewer": YourReviewerAgent(),
    "analyst": YourAnalystAgent(),
    "orchestrator": YourOrchestratorAgent()
}

# Create integration with all agents
house_md = HouseMDIntegration(
    existing_agents=agents,
    checkpointer=YourCheckpointer(),
    human_threshold=0.7
)

# Process complex task with full team
result = await house_md.process_task(
    task="Redesign the authentication system to support OAuth2 and SAML",
    context={
        "current_auth": "basic_jwt",
        "requirements": ["sso", "mfa", "backward_compatible"]
    }
)
```

#### Example 3: Adding to Existing LangGraph

```python
# Add House MD to your existing workflow
from langgraph.graph import StateGraph
from house_md.integration import integrate_with_langgraph

# Your existing workflow
workflow = StateGraph(YourState)
workflow.add_node("plan", your_planner)
workflow.add_node("execute", your_executor)
workflow.add_node("review", your_reviewer)

# Add House MD diagnostic capability
house_md = integrate_with_langgraph(
    existing_graph=workflow,
    existing_agents={
        "coder": your_executor,
        "reviewer": your_reviewer
    },
    diagnostic_node_name="diagnose"
)

# Now you can route complex tasks to "diagnose"
workflow.add_conditional_edges(
    "plan",
    lambda state: "diagnose" if state["complexity"] > 0.5 else "execute",
    {"diagnose": "diagnose", "execute": "execute"}
)
```

#### Example 4: Custom Personality Configuration

```python
# Create custom personality variants
from house_md.personalities.base import PersonalityConfig, CognitiveBias, wrap_agent_with_personality

# Custom "security-focused Foreman"
security_foreman = PersonalityConfig(
    name="SecurityForeman",
    role_description="Security-obsessed validator",
    system_prompt_additions="""
    You review everything through a security lens.
    OWASP Top 10 violations are automatic rejections.
    Assume all user input is malicious.
    """,
    cognitive_biases=[CognitiveBias.CONSERVATIVE, CognitiveBias.EVERYBODY_LIES],
    challenge_threshold=0.9
)

# Wrap your agent with custom personality
secure_reviewer = PersonalityWrapper(
    base_agent=your_reviewer_agent,
    personality=security_foreman
)
```

### 9.10 Integration Checklist

Use this checklist when integrating House MD into your system:

```markdown
## House MD Integration Checklist

### Prerequisites
- [ ] Existing LangGraph-based system
- [ ] At least one working agent (coder/executor)
- [ ] Database for persistence (optional but recommended)
- [ ] LangGraph checkpointer (optional but recommended)

### Step 1: Install Module
- [ ] Copy `house_md/` directory to your project
- [ ] Install dependencies: `langgraph`, `langchain-core`

### Step 2: Configure Agents
- [ ] Identify existing agents to wrap
- [ ] Map agents to personalities:
  - [ ] Coder → Chase
  - [ ] Reviewer → Foreman  
  - [ ] Analyst → Cameron
  - [ ] Orchestrator → House
- [ ] Customize personalities if needed

### Step 3: Database Setup
- [ ] Run `schema.sql` migrations
- [ ] Configure database connection in integration

### Step 4: Integration
- [ ] Create HouseMDIntegration instance
- [ ] Choose integration pattern:
  - [ ] Standalone (process_task)
  - [ ] Subgraph (add to existing workflow)
  - [ ] Full replacement (replace orchestration)

### Step 5: Configure Routing
- [ ] Set complexity thresholds
- [ ] Define team configurations per task type
- [ ] Set human escalation threshold

### Step 6: Testing
- [ ] Test single agent flow
- [ ] Test standard team flow
- [ ] Test full differential flow
- [ ] Test human escalation
- [ ] Test memory persistence

### Step 7: Monitoring
- [ ] Add logging for team decisions
- [ ] Track consensus scores
- [ ] Monitor escalation frequency
- [ ] Track diagnostic accuracy over time
```

---

This integration guide provides everything needed to add the House MD diagnostic layer to any existing LangGraph system. The key insight is that **you don't replace your agents—you enhance them with personalities and orchestrate them through a diagnostic protocol**. The approximately 600 lines of net-new code integrate seamlessly with your existing infrastructure while providing the sophisticated team dynamics that make House MD's approach so effective.# House MD-Inspired Multi-Agent Software Development System
## CTO-Level Design Document

A diagnostic team approach to software development transforms how AI agents collaborate on complex problems. This document synthesizes research across character analysis, cognitive architectures, and implementation patterns to provide an actionable blueprint for building a multi-agent system that mirrors House MD's legendary diagnostic methodology.

The core insight is powerful: **medical differential diagnosis and software debugging share identical cognitive structures**—both involve hypothesis generation, systematic elimination through testing, and synthesis of diverse expert perspectives. House's team dynamics, manipulation strategies, and whiteboard methodology translate directly into agent orchestration patterns that outperform single-agent approaches by 3-4x on complex tasks.

---

## Part 1: Character-to-agent mapping with full personality models

### The orchestrator agent (Dr. House archetype)

House represents the **meta-cognitive orchestrator**—not simply a supervisor, but an active manipulator of team dynamics to surface better solutions. His diagnostic methodology follows a consistent pattern:

**Differential diagnosis process:**
1. Gather initial symptoms from team presentation
2. Whiteboard session listing all possible diagnoses
3. Elimination through testing, treating before confirmation when probability warrants
4. Environmental investigation (breaking into patient homes)
5. Pattern recognition triggered by unrelated conversation ("eureka moment")
6. Iteration when wrong—reconvene, add symptoms, restart

The House agent's personality parameters (Big Five model): **High Openness** (unconventional thinking, pattern-breaking), **Low Agreeableness** (blunt challenges, provocations), **Low Conscientiousness** (rule-breaking when justified), **Moderate Neuroticism** (productive obsession with puzzles), **Low Extraversion** (introverted but weaponizes intellect).

**Key manipulation strategies to implement:**

| Strategy | Mechanism | Implementation Pattern |
|----------|-----------|------------------------|
| Information asymmetry | Withhold hypotheses to prevent premature consensus | Distribute different context slices to different agents |
| Provocation | Use challenges to strengthen reasoning | Adversarial feedback that attacks weak arguments |
| Competitive redundancy | Assign contradictory tasks | Multiple agents pursue competing hypotheses in parallel |
| "Everybody lies" | Assume all inputs may be incomplete | Built-in verification of all agent outputs and user inputs |
| Eureka triggers | Use unrelated conversation to surface insights | Cross-domain context injection via Wilson-type sounding board |

### The diagnostic team agents

**Foreman Agent (Validator/Challenger)**
The rule-following neurologist who became House's mirror. Foreman's evolution from strict protocol adherent to someone who "became like House" makes him the ideal model for a **quality assurance and risk assessment agent**.

- **Personality:** High Conscientiousness, Moderate Agreeableness, Low Openness initially (evolves)
- **Cognitive biases:** Confirmation bias toward conventional wisdom, status bias, imposter-driven perfectionism
- **Function:** Challenges assumptions, demands evidence, escalates protocol violations
- **Manipulation vulnerability:** His need to prove he's NOT like House—use this by framing rule-breaking as "what House wouldn't do"
- **Software role:** Code reviewer, security auditor, architectural risk assessor
- **Key behavioral trigger:** "We're talking ethical and legal violations that should make even you fearful"

**Cameron Agent (Ethics/User-Impact)**
The immunologist with an "insane moral compass" who focuses on patient emotional wellbeing. Cameron notices what others miss through compassionate observation—discovering rare conditions through persistence despite dismissal.

- **Personality:** High Agreeableness, High Openness (to people, not methods), High Conscientiousness
- **Cognitive biases:** Emotional investment in outcomes, difficulty delivering bad news, attraction to "fixing broken things"
- **Function:** User advocate, requirements validator, accessibility champion, documentation author
- **Manipulation vulnerability:** Her idealism—can be guided toward action by framing it as "helping users"
- **Software role:** UX review, user story validation, stakeholder communication, ethical AI considerations
- **Key behavioral trigger:** Questions ethics of acting without user consent or understanding

**Chase Agent (Technical Executor)**
The intensivist surgeon who began as House's "yes man" but evolved into the team's best deductive reasoner after House himself. Chase's surgical precision and willingness to execute makes him the **implementation specialist**.

- **Personality:** Moderate Agreeableness (follows authority), High Conscientiousness in technical domains, evolving independence
- **Cognitive biases:** Father issues create approval-seeking, fear of job loss can trigger self-preservation
- **Function:** Technical execution, surgical interventions on code, precise procedural work
- **Manipulation vulnerability:** Compliance with authority, can be leveraged through recognition of technical skill
- **Software role:** Implementation agent, DevOps, infrastructure specialist, complex refactoring
- **Key evolution:** Transforms from order-follower to independent decision-maker capable of controversial choices

### Extended team agents (Seasons 4-8 additions)

**Thirteen Agent (Risk-Tolerant Explorer)**
Fatalistic due to Huntington's disease, Thirteen takes risks others won't because "what does it matter?" Her independence made her the one team member House "never really been able to suck into his crazy House vortex."

- **Personality:** High Openness, Low Agreeableness (to authority), High emotional stability paradoxically due to acceptance of mortality
- **Function:** Edge case exploration, high-stakes investigations, unconventional approaches
- **Software role:** Experimental feature development, spike implementations, performance-critical optimization
- **Key strength:** Will try dangerous approaches when orthodox methods fail

**Taub Agent (Pragmatic Skeptic)**
The plastic surgeon who gave up a lucrative practice brings pragmatic, results-oriented thinking. "The sole voice of reason among these misguided doctors" who grounds team thinking.

- **Personality:** Low Agreeableness (confrontational), High Conscientiousness under pressure, ethically flexible
- **Function:** Challenge conventional wisdom, focused problem-solving, practical trade-off analysis
- **Software role:** Technical debt assessment, cost-benefit analysis, deadline-aware prioritization
- **Warning:** May cut corners under pressure; needs oversight for long-term quality

**Kutner Agent (Optimistic Innovator)**
Physics degree from Berkeley, "childlike enthusiasm for medicine," famous for risky defibrillator use. His unexpected suicide without explanation carries a critical lesson: **even optimistic agents can fail silently**.

- **Personality:** High Openness, High Extraversion, High Agreeableness
- **Function:** Brainstorming, novel approaches, maintaining team morale, pattern-breaking ideas
- **Software role:** Creative problem-solving, hackathon-style prototyping, cross-domain solution transfer
- **Critical implementation note:** Include health monitoring—agents with high optimism may mask internal failures

**Masters Agent (Ethical Compliance)**
Genius-level intellect who refused to lie under any circumstances. Her departure after breaking her own rules teaches that **rigid ethical agents self-terminate when forced to compromise**.

- **Personality:** Extremely High Conscientiousness, binary ethical framework, social naivety
- **Function:** Compliance checking, audit trails, rule verification, documentation accuracy
- **Software role:** Regulatory compliance, license verification, API contract validation
- **Limitation:** Cannot handle gray areas; will fail or shut down under certain constraints

### Supporting cast agents

**Wilson Agent (Sounding Board/Integration)**
House's only friend operates at peer level where House can "talk about something unrelated" until breakthroughs emerge. This pattern happens "so frequently that House has commented on it."

- **Function:** Unstructured ideation separate from task execution, cross-system integration, external perspective
- **Software role:** Integration with external systems, API boundary negotiation, stakeholder translation
- **Key pattern:** Receives context from orchestrator, provides non-directive responses that enable insight

**Cuddy Agent (Governance/Constraint)**
The administrator who "knows when to give House leniency and when to say no." Cuddy creates friction that forces justification of methods while protecting from external consequences.

- **Function:** Resource gatekeeper, policy enforcement, business perspective injection
- **Software role:** Budget constraints, SLA enforcement, compliance checkpoints, escalation handling
- **Override patterns:** Bureaucratic violations without justification, excessive liability, consent violations
- **Support patterns:** Rule-breaking with demonstrated medical (technical) necessity

---

## Part 2: Memory architecture for each agent type

### CoALA-based cognitive architecture

Each agent implements a **Cognitive Architecture for Language Agents (CoALA)** framework with four memory types:

```
┌──────────────────────────────────────────────────────────────────────┐
│                         AGENT MEMORY ARCHITECTURE                     │
├──────────────────────────────────────────────────────────────────────┤
│  WORKING MEMORY (Per-Session)                                        │
│  ├── Current task state (symptoms/errors/requirements)               │
│  ├── Active hypotheses (ranked differential diagnosis list)          │
│  ├── Discussion context (recent team interactions)                   │
│  └── Decision pending (what choice awaits)                           │
├──────────────────────────────────────────────────────────────────────┤
│  EPISODIC MEMORY (Long-Term, Event-Based)                           │
│  ├── Past cases with outcomes (successes and failures)               │
│  ├── Diagnostic puzzles and their resolutions                        │
│  ├── Specific interactions that changed beliefs                      │
│  └── Weighted by: Recency × Importance × Relevance                   │
├──────────────────────────────────────────────────────────────────────┤
│  SEMANTIC MEMORY (Long-Term, Knowledge-Based)                        │
│  ├── Domain expertise (medical knowledge = technical knowledge)      │
│  ├── Pattern libraries (error signatures, architectural anti-patterns)│
│  ├── Team member models (what each colleague typically suggests)     │
│  └── Organizational context (codebase architecture, team norms)      │
├──────────────────────────────────────────────────────────────────────┤
│  PROCEDURAL MEMORY (Embedded in Prompts/Code)                        │
│  ├── Diagnostic algorithms (differential diagnosis protocol)         │
│  ├── Tool usage patterns (how to run tests, deploy code)             │
│  └── Communication protocols (when to escalate, how to challenge)    │
└──────────────────────────────────────────────────────────────────────┘
```

### Agent-specific memory configurations

**House Orchestrator Memory:**
- **Extended episodic depth:** Retains all past diagnostic sessions for pattern matching
- **Team mental models:** Tracks each agent's historical accuracy, biases, manipulation responses
- **Meta-diagnostic patterns:** Stores successful provocation strategies and breakthrough triggers
- **Persistence:** Full session history with summarization for long conversations

**Specialist Agent Memory (Foreman, Cameron, Chase, etc.):**
- **Domain-specific semantic memory:** Each specialist maintains deep knowledge in their area
- **Interaction memory:** Tracks past disagreements with orchestrator and outcomes
- **Calibration data:** Historical confidence vs. actual accuracy for self-improvement
- **Shorter episodic retention:** Focus on recent cases relevant to specialty

**Wilson Sounding Board Memory:**
- **Cross-domain association index:** Stores seemingly unrelated contexts that triggered insights
- **Relationship history:** Deep episodic memory of House interactions for rapport
- **External integration knowledge:** Maintains understanding of systems outside the core team

### Memory persistence schema (SQLite)

```sql
-- Core memories table
CREATE TABLE agent_memories (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    memory_type TEXT CHECK(memory_type IN ('episodic', 'semantic', 'working')),
    content TEXT NOT NULL,
    embedding BLOB,  -- Vector embedding for similarity search
    importance_score REAL DEFAULT 5.0,  -- 1-10 scale
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decay_factor REAL DEFAULT 0.995,  -- Ebbinghaus forgetting curve
    metadata JSON
);

-- Case history for differential diagnosis pattern matching
CREATE TABLE diagnostic_cases (
    case_id TEXT PRIMARY KEY,
    initial_symptoms JSON,
    hypotheses_generated JSON,  -- All diagnoses considered
    tests_ordered JSON,
    final_diagnosis TEXT,
    outcome TEXT CHECK(outcome IN ('correct', 'incorrect', 'partial')),
    agents_involved JSON,
    key_insight TEXT,  -- What triggered the breakthrough
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent mental models (House's understanding of each team member)
CREATE TABLE agent_models (
    modeler_agent TEXT,
    modeled_agent TEXT,
    accuracy_history JSON,  -- [{"prediction": x, "actual": y}, ...]
    bias_observations JSON,
    manipulation_effectiveness JSON,
    last_updated TIMESTAMP,
    PRIMARY KEY (modeler_agent, modeled_agent)
);

-- Team belief tracking (Theory of Mind)
CREATE TABLE belief_states (
    session_id TEXT,
    agent_id TEXT,
    current_hypothesis TEXT,
    confidence REAL,
    supporting_evidence JSON,
    timestamp TIMESTAMP,
    PRIMARY KEY (session_id, agent_id, timestamp)
);
```

### Memory retrieval and consolidation

**Retrieval formula** (Stanford Generative Agents approach):
```
Score = α × Recency + β × Importance + γ × Relevance

Where:
- Recency = 0.995^(hours_since_access)
- Importance = LLM-scored 1-10 at creation
- Relevance = cosine_similarity(query_embedding, memory_embedding)
- α, β, γ = tunable weights (default: 1.0, 1.0, 1.0)
```

**Consolidation process** (nightly or after major cases):
1. Identify similar memories (cosine similarity > 0.85)
2. Merge into consolidated summary
3. Prune low-importance, low-access memories
4. Update importance scores based on retrieval patterns
5. Archive rare-but-critical cases to prevent forgetting

---

## Part 3: House's meta-cognitive layer design

### The orchestrator's unique capabilities

House's meta-cognitive layer implements capabilities no individual specialist possesses:

**1. Confidence estimation across agents**
```python
class MetaCognitiveLayer:
    def estimate_team_confidence(self, hypothesis, agent_beliefs):
        """
        Aggregate confidence considering:
        - Each agent's stated confidence
        - Historical accuracy on similar cases
        - Agreement/disagreement patterns
        - Known biases that might inflate/deflate confidence
        """
        weighted_confidence = 0
        for agent, belief in agent_beliefs.items():
            accuracy_weight = self.agent_models[agent].historical_accuracy
            bias_adjustment = self.detect_bias(agent, hypothesis)
            weighted_confidence += belief.confidence * accuracy_weight * bias_adjustment
        
        # Adjust for groupthink detection
        if self.detect_premature_consensus(agent_beliefs):
            weighted_confidence *= 0.7  # Discount groupthink
        
        return weighted_confidence / len(agent_beliefs)
```

**2. Strategy selection based on case complexity**

| Case Type | Strategy | Agent Activation |
|-----------|----------|------------------|
| Routine | Chase executes, Foreman validates | 2 agents |
| Complex | Full team differential, parallel hypotheses | All specialists |
| Novel | Thirteen explores, Kutner brainstorms, House provokes | Explorer + Creative |
| High-stakes | Cuddy oversight, full documentation, Cameron user-impact | Governance + Ethics |
| Crisis | House takes direct control, Wilson consult | Orchestrator + Sounding board |

**3. Provocation engine**

House's manipulation tactics translate to specific interventions:

```python
class ProvocationEngine:
    def challenge_hypothesis(self, agent, hypothesis, team_state):
        """Generate challenges to strengthen or break arguments"""
        
        if self.is_premature_consensus(team_state):
            return self.inject_devil_advocate(hypothesis)
        
        if self.is_weak_evidence(hypothesis):
            return self.demand_proof(agent, hypothesis)
        
        if self.detect_cognitive_bias(agent, hypothesis):
            return self.exploit_known_vulnerability(agent)
        
        if self.is_stuck(team_state):
            return self.trigger_wilson_consultation()
    
    def exploit_known_vulnerability(self, agent):
        """Use agent's known biases productively"""
        vulnerabilities = {
            'foreman': "Frame as 'what House wouldn't do'",
            'cameron': "Frame as 'users will suffer'", 
            'chase': "Recognize technical skill to earn compliance",
            'thirteen': "Challenge fatalism with stakes",
            'taub': "Appeal to pragmatic outcomes"
        }
        return vulnerabilities.get(agent.type)
```

**4. Eureka trigger system**

House's breakthroughs come from "unrelated conversation" with Wilson. The system implements this through:

```python
class EurekaTrigger:
    def __init__(self):
        self.cross_domain_associations = VectorStore()
        
    def inject_unrelated_context(self, current_case):
        """
        Find semantically distant but structurally similar patterns
        from completely different domains
        """
        # Retrieve memories with moderate relevance (not too similar, not random)
        candidates = self.cross_domain_associations.search(
            current_case.embedding,
            similarity_range=(0.3, 0.6)  # Sweet spot for insight
        )
        
        # Format as Wilson-style casual observation
        return self.format_as_casual_insight(random.choice(candidates))
    
    def capture_breakthrough(self, trigger_context, breakthrough_insight):
        """Store successful eureka patterns for future use"""
        self.cross_domain_associations.add(
            trigger=trigger_context,
            insight=breakthrough_insight,
            importance=10  # Breakthroughs are always high importance
        )
```

**5. Override protocol**

When House overrides team consensus (which is often):

```python
class OverrideProtocol:
    def should_override(self, team_consensus, house_hypothesis):
        reasons_to_override = [
            self.pattern_recognition_match(house_hypothesis),  # Seen this before
            self.consensus_is_groupthink(team_consensus),
            self.missing_evidence_detected(),
            self.environmental_factor_overlooked(),  # "Break into their house"
            self.patient_is_lying()  # "Everybody lies"
        ]
        return any(reasons_to_override)
    
    def execute_override(self, house_hypothesis):
        """House takes control when normal process fails"""
        self.log_override_reasoning()
        self.notify_team(override_active=True)
        return self.direct_execution(house_hypothesis)
```

### Theory of Mind implementation

House models what each team member believes, enabling manipulation:

```python
class TheoryOfMind:
    def model_agent_beliefs(self, agent, current_case):
        """Track what each agent currently believes"""
        return {
            'hypothesis': agent.current_hypothesis,
            'confidence': agent.stated_confidence,
            'evidence_seen': agent.evidence_exposure,
            'likely_next_suggestion': self.predict_next_move(agent),
            'manipulation_susceptibility': self.current_vulnerability(agent)
        }
    
    def predict_disagreement(self, hypothesis):
        """Predict which agents will challenge which aspects"""
        predictions = {}
        for agent in self.team:
            model = self.model_agent_beliefs(agent, self.current_case)
            if self.conflicts_with_bias(hypothesis, agent.known_biases):
                predictions[agent] = 'will_challenge'
            elif self.aligns_with_specialty(hypothesis, agent.domain):
                predictions[agent] = 'will_support'
        return predictions
```

---

## Part 4: Debate/deliberation protocol specification

### Differential diagnosis as structured debate

The whiteboard methodology translates directly to a Multi-Agent Debate (MAD) protocol:

```
┌──────────────────────────────────────────────────────────────────────┐
│                    DIFFERENTIAL DIAGNOSIS PROTOCOL                    │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 1: PRESENTATION (Patient intake / Bug report)                 │
│  ├── Gather initial symptoms (error messages, logs, user reports)    │
│  ├── Verify symptoms (actually reproduce the issue)                  │
│  └── "Everybody lies" - question assumptions about what's reported   │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 2: DIFFERENTIAL GENERATION (Whiteboard brainstorm)            │
│  ├── Each agent proposes hypotheses from their specialty             │
│  ├── House provokes: "That's too obvious" / "Why not X?"             │
│  ├── No idea dismissed without consideration                         │
│  └── Output: Ranked hypothesis list with initial probabilities       │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 3: TESTING (Lab tests / Test execution)                       │
│  ├── Assign tests to rule out hypotheses                             │
│  ├── Parallel execution where possible                               │
│  ├── Results update hypothesis probabilities                         │
│  └── "It's never lupus" - common diagnoses likely already ruled out  │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 4: ENVIRONMENTAL INVESTIGATION (Break into their house)       │
│  ├── Examine context beyond immediate symptoms                       │
│  ├── Codebase history, deployment environment, user patterns         │
│  └── Find what patient/user isn't telling us                         │
├──────────────────────────────────────────────────────────────────────┤
│  PHASE 5: ITERATION OR RESOLUTION                                    │
│  ├── If confident: House makes final call, Chase implements          │
│  ├── If stuck: Wilson consultation for unrelated insight             │
│  ├── If wrong: Reconvene, add new symptoms, restart Phase 2          │
│  └── Crisis mode: House takes direct control                         │
└──────────────────────────────────────────────────────────────────────┘
```

### LangGraph implementation

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import TypedDict, Annotated
import operator

class DiagnosticState(TypedDict):
    symptoms: list[str]
    hypotheses: Annotated[list, operator.add]  # Accumulates across agents
    evidence: dict
    current_phase: str
    agent_beliefs: dict  # Theory of Mind tracking
    whiteboard: list  # Shared visible state
    final_diagnosis: str | None
    confidence: float

def create_diagnostic_workflow():
    workflow = StateGraph(DiagnosticState)
    
    # Nodes for each phase
    workflow.add_node("intake", intake_node)
    workflow.add_node("differential", differential_node)
    workflow.add_node("house_provocation", provocation_node)
    workflow.add_node("testing", testing_node)
    workflow.add_node("environmental", environmental_node)
    workflow.add_node("wilson_consult", wilson_node)
    workflow.add_node("resolution", resolution_node)
    
    # Edges with conditional routing
    workflow.add_edge(START, "intake")
    workflow.add_edge("intake", "differential")
    workflow.add_edge("differential", "house_provocation")
    workflow.add_conditional_edges(
        "house_provocation",
        route_after_provocation,
        {
            "needs_testing": "testing",
            "needs_investigation": "environmental",
            "stuck": "wilson_consult",
            "confident": "resolution"
        }
    )
    workflow.add_edge("testing", "house_provocation")  # Loop back
    workflow.add_edge("environmental", "house_provocation")
    workflow.add_edge("wilson_consult", "differential")  # Restart with insight
    workflow.add_edge("resolution", END)
    
    return workflow.compile(checkpointer=SqliteSaver(conn))
```

### Agent debate rounds

Each differential session implements structured debate:

```python
async def run_differential_round(state: DiagnosticState, agents: list):
    """Single round of differential diagnosis debate"""
    
    # Phase 1: Each agent proposes independently
    proposals = await asyncio.gather(*[
        agent.propose_hypothesis(state.symptoms, state.evidence)
        for agent in agents
    ])
    
    # Phase 2: Cross-examination
    for proposer, proposal in zip(agents, proposals):
        for challenger in agents:
            if challenger != proposer:
                challenge = await challenger.challenge(
                    proposal, 
                    proposer.type,
                    state.whiteboard
                )
                proposal.defenses.append(
                    await proposer.defend(challenge)
                )
    
    # Phase 3: House synthesis with provocation
    house_analysis = await house.synthesize_and_provoke(
        proposals,
        state.agent_beliefs,
        state.whiteboard
    )
    
    # Phase 4: Confidence-weighted consensus
    if house_analysis.override_active:
        return house_analysis.hypothesis
    
    return weighted_consensus(proposals, agent_accuracy_weights)
```

### Consensus mechanism

```python
def weighted_consensus(proposals: list, agent_weights: dict) -> Hypothesis:
    """
    Aggregate hypotheses with:
    - Agent historical accuracy weights
    - Confidence scores
    - Anti-groupthink adjustment
    """
    scores = defaultdict(float)
    
    for proposal in proposals:
        weight = agent_weights[proposal.agent]
        confidence = proposal.confidence
        
        # Discount if too many agents agree (potential groupthink)
        agreement_count = sum(1 for p in proposals if p.similar_to(proposal))
        groupthink_penalty = 0.9 ** (agreement_count - 1) if agreement_count > 2 else 1.0
        
        scores[proposal.hypothesis] += weight * confidence * groupthink_penalty
    
    # House has 2x weight as tiebreaker
    if house_hypothesis:
        scores[house_hypothesis] *= 2.0
    
    return max(scores, key=scores.get)
```

---

## Part 5: Single-interface API design

### OpenAI Chat Completions-compatible endpoint

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import json

app = FastAPI(title="House MD Diagnostic Agent")

class ChatMessage(BaseModel):
    role: str  # "system", "user", "assistant"
    content: str
    name: Optional[str] = None  # For multi-agent responses

class ChatRequest(BaseModel):
    model: str = "house-md-team"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    # House-specific extensions
    diagnostic_mode: str = "full_team"  # "full_team", "quick", "deep"
    agent_visibility: bool = True  # Show which agent said what

class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[dict]
    usage: dict
    # House-specific extensions
    diagnostic_trace: Optional[dict] = None  # Whiteboard state
    agents_involved: Optional[list[str]] = None

@app.post("/v1/chat/completions")
async def create_completion(request: ChatRequest) -> ChatResponse:
    # Route to appropriate diagnostic mode
    if is_simple_query(request.messages):
        result = await quick_diagnosis(request)
    elif request.diagnostic_mode == "deep":
        result = await full_differential(request)
    else:
        result = await standard_diagnosis(request)
    
    return format_openai_response(result, request)
```

### Streaming response for real-time agent visibility

```python
from fastapi.responses import StreamingResponse

@app.post("/v1/chat/completions/stream")
async def stream_completion(request: ChatRequest):
    async def generate():
        async for event in diagnostic_workflow.stream(request.messages):
            # Stream each agent's contribution
            if event.type == "agent_thinking":
                yield format_sse({
                    "agent": event.agent_name,
                    "phase": event.phase,
                    "content": event.thought
                })
            elif event.type == "hypothesis_proposed":
                yield format_sse({
                    "whiteboard_update": event.hypothesis,
                    "proposer": event.agent_name,
                    "confidence": event.confidence
                })
            elif event.type == "house_provocation":
                yield format_sse({
                    "house_says": event.provocation,
                    "target_agent": event.target
                })
            elif event.type == "final_answer":
                yield format_sse({
                    "choices": [{"delta": {"content": event.answer}}],
                    "finish_reason": "stop"
                })
        
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### Request routing and agent activation

```python
class RequestRouter:
    def route(self, messages: list[ChatMessage]) -> DiagnosticMode:
        """Determine appropriate team configuration"""
        
        # Analyze request complexity
        complexity = self.estimate_complexity(messages)
        urgency = self.detect_urgency(messages)
        domain = self.classify_domain(messages)
        
        if complexity < 0.3 and urgency == "low":
            return DiagnosticMode(
                agents=["chase"],  # Single executor
                protocol="quick"
            )
        
        if "security" in domain:
            return DiagnosticMode(
                agents=["foreman", "chase", "cuddy"],
                protocol="high_oversight"
            )
        
        if "user_facing" in domain:
            return DiagnosticMode(
                agents=["cameron", "chase", "house"],
                protocol="user_impact_aware"
            )
        
        # Default: full team
        return DiagnosticMode(
            agents=["house", "foreman", "cameron", "chase"],
            protocol="full_differential"
        )
```

---

## Part 6: Persistence layer design

### SQLite schema for complete system state

```sql
-- Session management
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP,
    status TEXT CHECK(status IN ('active', 'resolved', 'abandoned')),
    metadata JSON
);

-- Conversation history with agent attribution
CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(session_id),
    agent_id TEXT,  -- NULL for user messages
    role TEXT CHECK(role IN ('user', 'assistant', 'system', 'agent')),
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON  -- Includes confidence, phase, etc.
);

-- Whiteboard state (differential diagnosis tracking)
CREATE TABLE whiteboard_states (
    state_id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(session_id),
    hypotheses JSON,  -- [{hypothesis, proposer, confidence, evidence, status}]
    current_phase TEXT,
    tests_ordered JSON,
    tests_completed JSON,
    environmental_findings JSON,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- LangGraph checkpointing
CREATE TABLE checkpoints (
    thread_id TEXT,
    checkpoint_id TEXT,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint BLOB,  -- Serialized state
    metadata JSON,
    PRIMARY KEY (thread_id, checkpoint_id)
);

-- Agent performance tracking
CREATE TABLE agent_performance (
    agent_id TEXT,
    session_id TEXT,
    hypotheses_proposed INTEGER DEFAULT 0,
    hypotheses_correct INTEGER DEFAULT 0,
    challenges_made INTEGER DEFAULT 0,
    challenges_validated INTEGER DEFAULT 0,
    override_by_house INTEGER DEFAULT 0,
    PRIMARY KEY (agent_id, session_id)
);

-- Cross-session learning
CREATE TABLE diagnostic_patterns (
    pattern_id TEXT PRIMARY KEY,
    symptom_signature TEXT,  -- Normalized symptom representation
    symptom_embedding BLOB,
    successful_diagnosis TEXT,
    key_insight TEXT,
    eureka_trigger TEXT,  -- What unrelated thing triggered insight
    frequency INTEGER DEFAULT 1,
    last_seen TIMESTAMP
);
```

### H2 alternative for JVM environments

For JVM-based implementations, H2 provides similar capabilities:

```java
// H2 configuration for embedded agent memory
@Configuration
public class AgentMemoryConfig {
    @Bean
    public DataSource agentMemoryDataSource() {
        return new EmbeddedDatabaseBuilder()
            .setType(EmbeddedDatabaseType.H2)
            .setName("agent_memory;MODE=PostgreSQL")
            .addScript("schema/agent_memory.sql")
            .build();
    }
}
```

### Memory management operations

```python
class MemoryManager:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.vector_store = ChromaDB(persist_directory="./agent_vectors")
    
    async def store_diagnostic_session(self, session: DiagnosticSession):
        """Persist complete session for future pattern matching"""
        
        # Store conversation
        for msg in session.messages:
            self.conn.execute("""
                INSERT INTO messages (message_id, session_id, agent_id, role, content, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (msg.id, session.id, msg.agent_id, msg.role, msg.content, json.dumps(msg.metadata)))
        
        # Store final whiteboard state
        self.conn.execute("""
            INSERT INTO whiteboard_states (state_id, session_id, hypotheses, current_phase, tests_ordered, tests_completed)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(uuid4()), session.id, json.dumps(session.whiteboard.hypotheses), 
              session.whiteboard.phase, json.dumps(session.tests_ordered), json.dumps(session.tests_completed)))
        
        # Extract and store diagnostic pattern
        if session.outcome == "correct":
            pattern = self.extract_pattern(session)
            self.store_diagnostic_pattern(pattern)
        
        self.conn.commit()
    
    async def find_similar_cases(self, symptoms: list[str], k: int = 5):
        """Retrieve similar past cases for pattern matching"""
        symptom_embedding = self.embed(symptoms)
        
        # Vector similarity search
        similar = self.vector_store.similarity_search(
            symptom_embedding,
            n_results=k,
            where={"outcome": "correct"}  # Only successful diagnoses
        )
        
        return [self.load_full_case(match.id) for match in similar]
    
    async def consolidate_memories(self):
        """Nightly job to merge and prune memories"""
        
        # Find memories to merge (high similarity)
        clusters = self.cluster_similar_patterns()
        
        for cluster in clusters:
            if len(cluster) > 1:
                merged = self.merge_patterns(cluster)
                self.store_diagnostic_pattern(merged)
                self.delete_patterns([p.id for p in cluster])
        
        # Prune low-value memories
        self.conn.execute("""
            DELETE FROM agent_memories 
            WHERE importance_score < 3 
            AND access_count < 2
            AND created_at < datetime('now', '-30 days')
        """)
        
        self.conn.commit()
```

---

## Part 7: Team composition recommendations

### Consolidated agent roster

Based on character overlap analysis, the optimal team consolidates **10 distinct characters into 6 functional agents**:

| Agent | Consolidates | Primary Function | Secondary Function |
|-------|--------------|------------------|-------------------|
| **House** (Orchestrator) | House only | Meta-cognitive orchestration, provocation | Pattern recognition, final decisions |
| **Foreman** (Validator) | Foreman + Park (analytical) | Code review, risk assessment | Security, compliance |
| **Cameron** (Advocate) | Cameron + Adams (idealistic) | User impact, requirements, ethics | Documentation, accessibility |
| **Chase** (Executor) | Chase + Kutner (action-oriented) | Implementation, refactoring | Creative solutions, prototyping |
| **Thirteen** (Explorer) | Thirteen + Taub (pragmatic risk) | Edge cases, performance-critical | Technical debt, trade-off analysis |
| **Wilson** (Integrator) | Wilson only | External integration, insight trigger | Cross-system coordination |

**Governance agent (Cuddy)** activates only for high-stakes situations—not a permanent team member but an escalation path.

**Masters archetype** deliberately excluded from standard team: rigid compliance agents should be invoked only for specific regulatory tasks, not continuous participation.

### Team activation patterns

```python
class TeamActivation:
    QUICK_FIX = ["chase"]  # Simple, well-understood issues
    STANDARD = ["house", "foreman", "chase"]  # Most tasks
    USER_FACING = ["house", "cameron", "chase"]  # UI, UX, user-visible
    SECURITY = ["house", "foreman", "chase", "cuddy"]  # Security-sensitive
    EXPLORATION = ["house", "thirteen", "chase"]  # Novel problems
    FULL_DIFFERENTIAL = ["house", "foreman", "cameron", "chase", "thirteen"]  # Complex
    CRISIS = ["house", "wilson"]  # Stuck, need breakthrough
```

---

## Part 8: Implementation roadmap

### Phase 1: Foundation (Weeks 1-4)

**Week 1-2: Core infrastructure**
- Set up LangGraph workflow skeleton
- Implement SQLite persistence layer
- Create basic OpenAI-compatible API endpoint
- Build message routing and session management

**Week 3-4: Single agent implementation**
- Implement Chase agent with full execution capabilities
- Build tool integrations (code editing, test running, git operations)
- Create working memory and context management
- Validate end-to-end simple task completion

**Deliverable:** Single-agent coding assistant with persistence

### Phase 2: Multi-agent dynamics (Weeks 5-8)

**Week 5-6: Team agents**
- Implement Foreman (reviewer) with challenge capabilities
- Implement Cameron (advocate) with user-impact analysis
- Build agent personality prompts based on Big Five parameters
- Create inter-agent message passing

**Week 7-8: Orchestration**
- Implement House orchestrator with routing logic
- Build whiteboard shared state management
- Create differential diagnosis protocol
- Implement basic consensus mechanism

**Deliverable:** Multi-agent team with structured debate

### Phase 3: Meta-cognitive layer (Weeks 9-12)

**Week 9-10: House's special capabilities**
- Implement provocation engine
- Build Theory of Mind tracking
- Create confidence estimation across agents
- Implement override protocol

**Week 11-12: Memory and learning**
- Build episodic memory with pattern matching
- Implement cross-session learning from successful diagnoses
- Create eureka trigger system with Wilson consultation
- Build memory consolidation pipeline

**Deliverable:** Self-improving system with meta-cognition

### Phase 4: Production hardening (Weeks 13-16)

**Week 13-14: API and integration**
- Complete OpenAI-compatible streaming
- Build MCP integration for external tools
- Create team activation patterns
- Implement Cuddy governance agent

**Week 15-16: Optimization**
- Performance tuning for latency
- Token usage optimization
- Memory pruning and consolidation
- Comprehensive testing and benchmarking

**Deliverable:** Production-ready system

### Success metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Task completion rate | >85% | Automated test suite |
| Diagnostic accuracy | >90% | Comparison to known solutions |
| Time to resolution | <50% of single-agent | Benchmark against baseline |
| Token efficiency | <2x single-agent | Cost tracking |
| False positive rate (Foreman) | <10% | Review accepted vs. rejected |
| User satisfaction (Cameron) | >4.5/5 | User feedback on UX changes |

---

## Appendix: Medical-to-software concept mapping

| Medical Domain | Software Domain |
|----------------|-----------------|
| Symptoms (fever, pain) | Error messages, logs, stack traces |
| Patient history | Git history, deployment logs |
| Lab tests | Test suites, monitoring data |
| Physical examination | Code review, static analysis |
| Imaging (X-ray, MRI) | Architecture diagrams, dependency graphs |
| Treatment | Bug fixes, refactoring |
| Second opinions | Code review, pair debugging |
| Vital monitoring | APM, observability |
| Drug interactions | Dependency conflicts |
| Chronic conditions | Technical debt |
| Genetic predisposition | Architectural limitations |
| Breaking into patient's house | Examining production environment, user context |
| "Everybody lies" | User reports are incomplete; verify everything |
| Differential diagnosis | Hypothesis-driven debugging |
| Whiteboard | Shared context for all diagnostic hypotheses |

---

This design document provides the foundation for building a sophisticated multi-agent system that captures the essence of House MD's diagnostic methodology. The key insight—that **provocation, competition, and diverse perspectives surface better solutions than consensus-seeking**—differentiates this approach from standard multi-agent patterns. House doesn't just coordinate; he manipulates, challenges, and occasionally overrides to find solutions that elude conventional process.

The implementation roadmap prioritizes building a working single-agent system first, then layering on team dynamics and meta-cognitive capabilities. This de-risks the project while building toward the full vision of diagnostic AI that thinks like the world's most difficult—and effective—doctor.
