# D03: Glossary & Terminology

## Config-Driven Multi-Agent Orchestration System

**Document ID:** D03  
**Version:** 1.0  
**Status:** Draft  
**Last Updated:** January 2026

---

## 1. Core Concepts

### 1.1 Agent Hierarchy

| Term | Definition | Example |
|------|------------|---------|
| **Supervisor** | The top-level LangGraph agent that routes tasks to workers and external agents. Does not execute substantive work—only routes, coordinates, and handles human-in-the-loop via `send_message`. | The single supervisor node in the orchestration graph |
| **Native Worker** | An agent running locally within the system, instantiated via Any-Agent, registered as a LangGraph node. Has tools attached via skillsets. | `research_agent`, `code_agent` |
| **External Agent** | An agent running outside the system, communicating via A2A protocol. Discovered via Agent Card at boot time. | An analytics agent running on `http://localhost:9001` |
| **Worker Node** | A LangGraph node wrapping either a native worker or external agent. The supervisor routes to worker nodes. | `ext::analytics-agent` node |

### 1.2 Tool Hierarchy

| Term | Definition | Example |
|------|------------|---------|
| **Tool** | A single callable capability, typically exposed via MCP. The atomic unit of agent capability. | `search_web`, `gh_open_pr`, `summarize_text` |
| **Skill** | A logical grouping of related tools. Represents a coherent capability area. | `web_research` skill = [`search_web`, `summarize_text`] |
| **Skillset** | A collection of skills assigned to an agent. Defines what an agent can do. | `researcher` skillset = [`web_research`, `data_analysis`] |
| **Tool Overlap** | Multiple agents having access to the same tool (via shared skills). Allowed and common. | Both `research_agent` and `code_agent` have `search_web` |
| **Tool Duplication** | The same tool ID mapping to multiple MCP servers. NOT allowed—each tool ID maps to exactly one MCP server. | ❌ `search_web` from both `mcp_server_a` and `mcp_server_b` |

### 1.3 MCP Concepts

| Term | Definition | Example |
|------|------------|---------|
| **MCP (Model Context Protocol)** | Anthropic-originated protocol for connecting AI applications to tools, data sources, and services. Defines tools, resources, and prompts. | Industry standard for tool exposure |
| **MCP Server** | A process that exposes tools via MCP protocol. Can use stdio or HTTP transport. | `python -m mcp_server_knowledge` |
| **MCP Client** | The component that connects to MCP servers and invokes tools. In our system, Any-Agent handles MCP client functionality. | Any-Agent runtime |
| **stdio Transport** | MCP communication via stdin/stdout. Used for local tools, single-client scenarios. Low latency. | Local filesystem MCP server |
| **HTTP Transport** | MCP communication via HTTP with SSE streaming. Used for remote/shared tools. Scalable. | Cloud-hosted MCP server |
| **Tool Materialization** | The process of converting MCP tool definitions into callable objects usable by agents. | Boot-time tool registry population |

### 1.4 A2A Concepts

| Term | Definition | Example |
|------|------------|---------|
| **A2A (Agent-to-Agent Protocol)** | Linux Foundation-backed protocol for agent-to-agent communication. Enables discovery and collaboration between opaque agent systems. | External agent integration |
| **Agent Card** | JSON document describing an agent's capabilities, skills, endpoints, and auth requirements. Published at well-known URL. | `/.well-known/agent.json` |
| **Host Index** | Endpoint on a multi-agent host that returns list of available agents and their Agent Card URLs. | `/a2a/index.json` |
| **Multi-Agent Host** | A single server process hosting multiple A2A agents at namespaced paths. | `http://host:9001/a2a/agent-a/`, `http://host:9001/a2a/agent-b/` |
| **Individual Agent Server** | A standalone server hosting a single A2A agent. | `http://localhost:9010` serving one agent |
| **Agent Discovery** | Boot-time process of fetching Agent Cards from seed URLs to identify available external agents. | Fetching cards from configured seed URLs |

### 1.5 Any-Agent Concepts

| Term | Definition | Example |
|------|------------|---------|
| **Any-Agent** | Mozilla AI library providing unified API to build agents across multiple frameworks. Supports MCP and A2A natively. | Framework abstraction layer |
| **Framework** | The underlying agent implementation library. Any-Agent supports: `langchain`, `openai`, `google`, `smolagents`, `llamaindex`, `agno`, `tinyagent`. | `langchain` framework for a worker |
| **AgentConfig** | Any-Agent configuration object specifying model, name, instructions, and tools for an agent. | Python dataclass passed to `AnyAgent.create()` |
| **Serving** | Exposing an Any-Agent as an A2A or MCP endpoint. | `agent.serve_async(A2AServingConfig(...))` |

### 1.6 LangGraph Concepts

| Term | Definition | Example |
|------|------------|---------|
| **LangGraph** | LangChain's library for building stateful, multi-step agent workflows as graphs. | Orchestration engine |
| **Graph** | A directed graph of nodes (agents/functions) and edges (transitions). Compiled before execution. | The supervisor + workers graph |
| **Node** | A function or agent that processes state. In our system: supervisor node, worker nodes, external nodes. | `research_agent` node |
| **Edge** | A transition between nodes. Can be unconditional or conditional based on state. | Supervisor → Worker edge |
| **Conditional Edge** | An edge whose target depends on runtime state evaluation. Used for supervisor routing. | Route to `research_agent` if task is research-related |
| **State** | A TypedDict passed through the graph, accumulating results. Uses reducers for updates. | `{messages, task, context, last_result, next}` |
| **Reducer** | A function that combines old and new state values. Default is replacement; `add_messages` appends. | `Annotated[list, add_messages]` |
| **Supervisor Pattern** | Hierarchical pattern where a supervisor agent delegates to workers and aggregates results. | Core pattern of this system |
| **Compile** | The process of finalizing a graph definition. No nodes can be added after compile. | `graph.compile()` |

### 1.7 Orchestration Concepts

| Term | Definition | Example |
|------|------------|---------|
| **Routing** | Supervisor's decision of which worker/external agent handles the current task. | Supervisor routes to `research_agent` |
| **Delegation** | Passing a task to a worker/external agent for execution. | Supervisor delegates research task |
| **Human-in-the-Loop** | Pausing execution to request user input. Supervisor uses `send_message` tool. | Clarifying ambiguous requests |
| **send_message** | Special tool attached to supervisor for requesting human input. | `send_message("Please clarify: X or Y?")` |
| **Import Mode** | How external agents are integrated: as `langgraph_nodes` (full nodes) or `tools_only` (callable tools). | Config: `mode: langgraph_nodes` |
| **Import Policy** | Rules for filtering which external agents to import: by tags, names, limits. | Include only agents tagged "internal" |
| **Assignment Strategy** | In `tools_only` mode, how external agent tools are attached to workers. Options: `skill_overlap`, `explicit`, `supervisor`. | Auto-assign by skill overlap |

### 1.8 Configuration Concepts

| Term | Definition | Example |
|------|------------|---------|
| **Config** | YAML/JSON file defining all system components: LLMs, MCP servers, tools, skills, skillsets, agents, A2A settings. | `config.yaml` |
| **Registry** | Runtime data structure holding instantiated objects (LLMs, tools, skills, agents). Built from config at boot. | `ToolRegistry`, `AgentRegistry` |
| **Boot Lifecycle** | Sequence from config load to API serving: config → registries → discovery → graph → serve. | System startup process |
| **Ignore List** | Config list of native workers to exclude from the graph. | `ignore_workers: ["code_agent"]` |

### 1.9 API Concepts

| Term | Definition | Example |
|------|------------|---------|
| **Chat Endpoint** | Primary API for user interaction. Invokes LangGraph with messages. | `POST /chat` |
| **Streaming** | Progressive token delivery to client as generation occurs. Pass-through from workers when supported. | SSE stream response |
| **OpenAI-Compatible Endpoint** | Facade mimicking OpenAI API format for compatibility with tools like Open WebUI. | `POST /v1/chat/completions` |

---

## 2. Abbreviations

| Abbreviation | Full Form |
|--------------|-----------|
| A2A | Agent-to-Agent (Protocol) |
| MCP | Model Context Protocol |
| LLM | Large Language Model |
| API | Application Programming Interface |
| SSE | Server-Sent Events |
| YAML | YAML Ain't Markup Language |
| JSON | JavaScript Object Notation |
| RBAC | Role-Based Access Control |
| C4 | Context, Container, Component, Code (architecture model) |
| HLD | High-Level Design |
| LLD | Low-Level Design |

---

## 3. Naming Conventions

### 3.1 Config Keys

| Pattern | Usage | Example |
|---------|-------|---------|
| `snake_case` | All config keys | `mcp_servers`, `import_policy` |
| `kebab-case` | Agent names in A2A | `analytics-agent` |
| `dot.notation` | MCP tool names | `github.search_code` |

### 3.2 Node IDs

| Pattern | Usage | Example |
|---------|-------|---------|
| `{name}` | Native workers | `research_agent` |
| `ext::{name}` | External agents | `ext::analytics-agent` |
| `supervisor` | Supervisor node | `supervisor` |

### 3.3 Registry Keys

| Registry | Key Pattern | Example |
|----------|-------------|---------|
| LLMRegistry | Config name | `default`, `supervisor`, `gpt4` |
| MCPRegistry | Server name | `knowledge`, `github` |
| ToolRegistry | Tool ID | `search_web`, `gh_open_pr` |
| SkillRegistry | Skill name | `web_research`, `repo_ops` |
| SkillsetRegistry | Skillset name | `researcher`, `coder` |
| AgentRegistry | Agent name | `research_agent`, `ext::analytics-agent` |

---

## 4. Visual Glossary

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              ORCHESTRATION                               │
│  ┌─────────────┐                                                        │
│  │ Supervisor  │──routes to──►┌─────────────┐  ┌─────────────────────┐ │
│  │   (LangGraph│              │Native Worker│  │  External Agent     │ │
│  │    Node)    │              │ (Any-Agent) │  │  (A2A Protocol)     │ │
│  └─────────────┘              └─────────────┘  └─────────────────────┘ │
│        │                            │                    │              │
│        │ send_message               │ uses               │ via A2A     │
│        ▼                            ▼                    ▼              │
│  ┌──────────┐                ┌───────────┐        ┌──────────────┐     │
│  │  Human   │                │MCP Server │        │ Agent Card   │     │
│  │   (UI)   │                │  (Tools)  │        │(/.well-known)│     │
│  └──────────┘                └───────────┘        └──────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           TOOL HIERARCHY                                 │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        SKILLSET: researcher                      │   │
│  │  ┌─────────────────────────┐  ┌─────────────────────────────┐   │   │
│  │  │   SKILL: web_research   │  │   SKILL: data_analysis      │   │   │
│  │  │  ┌──────┐ ┌──────────┐  │  │  ┌──────────┐ ┌──────────┐  │   │   │
│  │  │  │search│ │summarize │  │  │  │analyze   │ │visualize │  │   │   │
│  │  │  │_web  │ │_text     │  │  │  │_data     │ │_chart    │  │   │   │
│  │  │  └──────┘ └──────────┘  │  │  └──────────┘ └──────────┘  │   │   │
│  │  │       TOOLS             │  │        TOOLS                │   │   │
│  │  └─────────────────────────┘  └─────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Related Documents

- D02: Architecture Vision & Goals
- D04-D06: C4 Architecture Diagrams
- D25: Master Config Schema

---

## 6. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Architecture Team | Initial draft |
