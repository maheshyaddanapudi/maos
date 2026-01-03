# D02: Architecture Vision & Goals

## Config-Driven Multi-Agent Orchestration System

**Document ID:** D02  
**Version:** 1.0  
**Status:** Draft  
**Last Updated:** January 2026

---

## 1. Executive Problem Statement

Modern AI agent development faces a fragmentation problem: multiple frameworks (LangGraph, OpenAI Agents, Google ADK, LlamaIndex, etc.), multiple protocols (MCP for tools, A2A for agent communication), and no unified way to compose, configure, and orchestrate agents across these boundaries.

Organizations need to:
- Build agent systems without vendor lock-in to a single framework
- Integrate external agent services alongside internal workers
- Expose tools via standard protocols (MCP)
- Enable agent-to-agent collaboration (A2A)
- Maintain flexibility through configuration rather than code changes

This prototype addresses these needs by creating a **config-driven orchestration layer** that unifies LangGraph's workflow engine, Any-Agent's framework abstraction, MCP's tool protocol, and A2A's agent communication standard.

---

## 2. Vision Statement

> **Build a flexible, config-driven multi-agent orchestration system where a LangGraph Supervisor delegates to native workers (via Any-Agent) and external agents (via A2A), with all tools exposed through MCP—entirely configurable at startup without code changes.**

---

## 3. Design Principles

### 3.1 Configuration Over Code

Every aspect of the system—LLMs, tools, skills, agents, external integrations—is defined in YAML/JSON configuration. Adding a new agent or tool requires only config changes, not deployments.

### 3.2 Protocol-Native Integration

- **MCP** for tool exposure (not custom REST APIs)
- **A2A** for external agent communication (not proprietary protocols)
- Standard protocols enable interoperability with the broader ecosystem

### 3.3 Framework Abstraction

Native workers can use any framework supported by Any-Agent (LangGraph, OpenAI, Google ADK, smolagents, LlamaIndex, Agno, TinyAgent). The orchestration layer doesn't care—it sees unified agent interfaces.

### 3.4 Hierarchical Delegation

The Supervisor pattern provides clear separation:
- **Supervisor**: Routes tasks, handles ambiguity (via `send_message`), doesn't do substantive work
- **Workers**: Execute tasks using tools, return results
- **External Agents**: Collaborate via A2A, treated as peers or tools

### 3.5 Boot-Time Dynamism

The system discovers external agents, applies import policies, and constructs the LangGraph at startup. Runtime is deterministic; flexibility comes from reconfiguration and restart.

### 3.6 Graceful Degradation

- Streaming when supported, final response when not
- Agent-level timeouts with global defaults
- External agent failures don't crash the system

### 3.7 Security-Ready Architecture

Authentication, authorization, and multi-tenancy are not implemented but extension points are preserved in config schema and module interfaces.

---

## 4. Goals

### 4.1 Primary Goals

| ID | Goal | Success Criteria |
|----|------|------------------|
| G1 | LangGraph as orchestration engine | Supervisor routes to workers via LangGraph state machine |
| G2 | Any-Agent as runtime abstraction | Native workers instantiated via Any-Agent factory with configurable framework |
| G3 | MCP tool integration | Tools from MCP servers attached to workers via skill/skillset hierarchy |
| G4 | A2A external agent support | External agents discovered via Agent Cards, imported as nodes or tools |
| G5 | Config-driven everything | Zero code changes to add/modify agents, tools, skills, LLMs |
| G6 | Dual A2A hosting modes | Support both multi-agent host and individual agent servers |
| G7 | Human-in-the-loop | Supervisor can pause for user input via `send_message` tool |

### 4.2 Secondary Goals

| ID | Goal | Success Criteria |
|----|------|------------------|
| G8 | Streaming pass-through | Stream from workers/external agents to client when supported |
| G9 | Pluggable LLM providers | OpenAI, Anthropic, Google, Ollama/OpenAI-compatible via config |
| G10 | OpenAI-compatible API | Facade endpoint for Open WebUI integration |
| G11 | Flexible import policies | Filter external agents by tags, names, limits |

### 4.3 Non-Goals (Prototype Phase)

| ID | Explicitly Excluded | Rationale |
|----|---------------------|-----------|
| NG1 | Authentication & Authorization | Security layer deferred; extension points preserved |
| NG2 | Multi-tenancy | Single-tenant prototype; isolation patterns identified |
| NG3 | Runtime agent discovery | LangGraph requires compile-time node definition |
| NG4 | Persistent conversation state | In-memory state sufficient for prototype |
| NG5 | Production deployment hardening | Focus on architecture validation, not ops |

---

## 5. Success Criteria

The prototype is successful when:

1. **Config Change Test**: A new native worker can be added by editing YAML only (no Python changes)
2. **Framework Swap Test**: Changing a worker's framework (e.g., `langchain` → `openai`) works via config
3. **External Agent Test**: An A2A agent running separately is discovered and routed to by supervisor
4. **Tool Composition Test**: MCP tools compose into skills/skillsets and attach to correct workers
5. **Streaming Test**: A streaming-capable worker streams through to the client
6. **Human Loop Test**: Supervisor uses `send_message` to request clarification and resumes after user response
7. **Dual Host Test**: Both multi-agent host and individual agent servers work simultaneously

---

## 6. Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Orchestration engine | LangGraph | Company direction; mature supervisor pattern |
| Agent abstraction | Any-Agent | Framework-agnostic; MCP/A2A native support |
| Tool protocol | MCP | Industry standard; Anthropic-originated, widely adopted |
| Agent protocol | A2A | Linux Foundation backed; 150+ organizations |
| Config format | YAML (primary), JSON (supported) | Human-readable; JSON Schema validation |
| API framework | FastAPI | Async-native; OpenAPI generation; streaming support |
| Import modes | `langgraph_nodes` + `tools_only` | Flexibility for different external agent patterns |
| Assignment strategy | Skill-overlap auto-matching | Consistent with tool/skill/skillset model |

---

## 7. Stakeholders

| Role | Interest |
|------|----------|
| Platform Team | Validate architecture for company-wide adoption |
| Agent Developers | Understand how to build workers and external agents |
| Integration Team | Understand MCP/A2A integration patterns |
| Security Team | Review extension points for future hardening |
| Leadership | Assess feasibility and alignment with AI strategy |

---

## 8. Related Documents

- D03: Glossary & Terminology
- D04-D06: C4 Architecture Diagrams
- D07: Data Flow Architecture
- D25-D27: Configuration Specifications

---

## 9. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Architecture Team | Initial draft |
