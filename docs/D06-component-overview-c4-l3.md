# D06: Component Overview (C4 Level 3)

## Config-Driven Multi-Agent Orchestration System

**Document ID:** D06  
**Version:** 1.0  
**Status:** Draft  
**Last Updated:** January 2026

---

## 1. Overview

This document presents the C4 Level 3 (Component) diagram, showing the internal components within each container and their interactions.

---

## 2. Full System Component Diagram

```mermaid
flowchart TB
    subgraph API["API Server"]
        direction TB
        APIRouter["API Router"]
        ChatEndpoint["Chat Endpoint"]
        AgentsEndpoint["Agents Endpoint"]
        HealthEndpoint["Health Endpoint"]
        OpenAIEndpoint["OpenAI Facade"]
        StreamHandler["Stream Handler"]
        RequestValidator["Request Validator"]
    end

    subgraph LangGraph["LangGraph Engine"]
        direction TB
        GraphFactory["Graph Factory"]
        StateSchema["State Schema"]
        SupervisorNode["Supervisor Node"]
        NativeWorkerNode["Native Worker Node"]
        ExternalAgentNode["External Agent Node"]
        EdgeRouter["Edge Router"]
        IterationController["Iteration Controller"]
    end

    subgraph AnyAgent["Any-Agent Runtime"]
        direction TB
        AgentFactory["Agent Factory"]
        FrameworkAdapter["Framework Adapter"]
        MCPToolLoader["MCP Tool Loader"]
        A2AToolWrapper["A2A Tool Wrapper"]
        LLMFactory["LLM Factory"]
    end

    subgraph Config["Configuration"]
        direction TB
        ConfigLoader["Config Loader"]
        SchemaValidator["Schema Validator"]
        LLMRegistry["LLM Registry"]
        MCPRegistry["MCP Registry"]
        ToolRegistry["Tool Registry"]
        SkillRegistry["Skill Registry"]
        SkillsetRegistry["Skillset Registry"]
        AgentRegistry["Agent Registry"]
    end

    subgraph Discovery["A2A Discovery"]
        direction TB
        SeedManager["Seed Manager"]
        HostIndexFetcher["Host Index Fetcher"]
        AgentCardFetcher["Agent Card Fetcher"]
        CardParser["Card Parser"]
        ImportPolicyEngine["Import Policy Engine"]
    end

    %% API Internal Flow
    APIRouter --> ChatEndpoint
    APIRouter --> AgentsEndpoint
    APIRouter --> HealthEndpoint
    APIRouter --> OpenAIEndpoint
    ChatEndpoint --> RequestValidator
    ChatEndpoint --> StreamHandler

    %% API to LangGraph
    ChatEndpoint --> GraphFactory

    %% LangGraph Internal Flow
    GraphFactory --> StateSchema
    GraphFactory --> SupervisorNode
    GraphFactory --> NativeWorkerNode
    GraphFactory --> ExternalAgentNode
    GraphFactory --> EdgeRouter
    SupervisorNode --> EdgeRouter
    EdgeRouter --> IterationController

    %% LangGraph to Any-Agent
    NativeWorkerNode --> AgentFactory
    ExternalAgentNode --> A2AToolWrapper

    %% Any-Agent Internal Flow
    AgentFactory --> FrameworkAdapter
    AgentFactory --> MCPToolLoader
    AgentFactory --> LLMFactory
    FrameworkAdapter --> MCPToolLoader

    %% Config Internal Flow
    ConfigLoader --> SchemaValidator
    SchemaValidator --> LLMRegistry
    SchemaValidator --> MCPRegistry
    SchemaValidator --> ToolRegistry
    ToolRegistry --> SkillRegistry
    SkillRegistry --> SkillsetRegistry
    SkillsetRegistry --> AgentRegistry

    %% Discovery Internal Flow
    SeedManager --> HostIndexFetcher
    SeedManager --> AgentCardFetcher
    HostIndexFetcher --> AgentCardFetcher
    AgentCardFetcher --> CardParser
    CardParser --> ImportPolicyEngine
    ImportPolicyEngine --> AgentRegistry

    %% Cross-Container Dependencies
    LLMFactory --> LLMRegistry
    MCPToolLoader --> MCPRegistry
    MCPToolLoader --> ToolRegistry
    AgentFactory --> SkillsetRegistry
    GraphFactory --> AgentRegistry
```

---

## 3. Component Details by Container

### 3.1 API Server Components

```mermaid
flowchart LR
    subgraph APIServer["API Server Components"]
        Router["API Router<br/>───────────<br/>Route dispatch<br/>Middleware chain"]
        
        Chat["Chat Endpoint<br/>───────────<br/>POST /chat<br/>Streaming support"]
        
        Agents["Agents Endpoint<br/>───────────<br/>GET /agents<br/>List workers"]
        
        Health["Health Endpoint<br/>───────────<br/>GET /health<br/>Status check"]
        
        OpenAI["OpenAI Facade<br/>───────────<br/>/v1/chat/completions<br/>Compatibility layer"]
        
        Stream["Stream Handler<br/>───────────<br/>SSE formatting<br/>Chunk delivery"]
        
        Validator["Request Validator<br/>───────────<br/>Pydantic models<br/>Input sanitization"]
    end

    Router --> Chat
    Router --> Agents
    Router --> Health
    Router --> OpenAI
    Chat --> Validator
    Chat --> Stream
```

| Component | Responsibility | Interfaces |
|-----------|----------------|------------|
| **API Router** | Dispatch requests to endpoints, apply middleware | Inbound HTTP |
| **Chat Endpoint** | Handle `/chat` requests, invoke LangGraph | REST, WebSocket |
| **Agents Endpoint** | Return list of available agents | REST GET |
| **Health Endpoint** | System health status | REST GET |
| **OpenAI Facade** | Translate OpenAI format to internal format | REST POST |
| **Stream Handler** | Format and deliver SSE chunks | SSE |
| **Request Validator** | Validate request payloads | Pydantic |

### 3.2 LangGraph Engine Components

```mermaid
flowchart TB
    subgraph LangGraphEngine["LangGraph Engine Components"]
        GF["Graph Factory<br/>───────────<br/>Build graph from config<br/>Wire nodes + edges"]
        
        SS["State Schema<br/>───────────<br/>TypedDict definition<br/>Reducer configuration"]
        
        SN["Supervisor Node<br/>───────────<br/>Routing decisions<br/>send_message tool"]
        
        NWN["Native Worker Node<br/>───────────<br/>Wrap Any-Agent<br/>Execute + return"]
        
        EAN["External Agent Node<br/>───────────<br/>A2A client call<br/>Timeout handling"]
        
        ER["Edge Router<br/>───────────<br/>Conditional routing<br/>Next node selection"]
        
        IC["Iteration Controller<br/>───────────<br/>Loop count<br/>Termination check"]
    end

    GF --> SS
    GF --> SN
    GF --> NWN
    GF --> EAN
    GF --> ER
    SN --> ER
    ER --> IC
    IC --> SN
```

| Component | Responsibility | Key Methods |
|-----------|----------------|-------------|
| **Graph Factory** | Construct LangGraph from agent registry | `build_graph()`, `compile()` |
| **State Schema** | Define graph state structure | TypedDict class |
| **Supervisor Node** | Route tasks, handle ambiguity | `run()`, `decide_next()` |
| **Native Worker Node** | Execute native agent, return result | `run()`, `invoke_agent()` |
| **External Agent Node** | Call A2A agent, handle response | `run()`, `a2a_call()` |
| **Edge Router** | Determine next node from state | `route()` |
| **Iteration Controller** | Enforce max iterations | `check_limit()` |

### 3.3 Any-Agent Runtime Components

```mermaid
flowchart TB
    subgraph AnyAgentRuntime["Any-Agent Runtime Components"]
        AF["Agent Factory<br/>───────────<br/>Create agents<br/>Framework selection"]
        
        FA["Framework Adapter<br/>───────────<br/>langchain, openai, etc.<br/>Normalize interface"]
        
        MTL["MCP Tool Loader<br/>───────────<br/>Connect MCP servers<br/>Materialize tools"]
        
        ATW["A2A Tool Wrapper<br/>───────────<br/>Wrap A2A as tool<br/>For tools_only mode"]
        
        LF["LLM Factory<br/>───────────<br/>Create LLM clients<br/>Provider abstraction"]
    end

    AF --> FA
    AF --> MTL
    AF --> ATW
    AF --> LF
    FA --> MTL
```

| Component | Responsibility | Key Methods |
|-----------|----------------|-------------|
| **Agent Factory** | Instantiate Any-Agent with config | `create_agent()`, `create_async()` |
| **Framework Adapter** | Map framework-specific APIs to unified interface | `get_adapter()` |
| **MCP Tool Loader** | Connect to MCP servers, get tools | `connect()`, `get_tools()` |
| **A2A Tool Wrapper** | Wrap external agent as callable tool | `wrap_as_tool()` |
| **LLM Factory** | Create LLM client from config | `create_llm()` |

### 3.4 Configuration Components

```mermaid
flowchart TB
    subgraph ConfigComponents["Configuration Components"]
        CL["Config Loader<br/>───────────<br/>Read YAML/JSON<br/>Merge defaults"]
        
        SV["Schema Validator<br/>───────────<br/>JSON Schema check<br/>Type validation"]
        
        LLMR["LLM Registry<br/>───────────<br/>Store LLM clients<br/>By config name"]
        
        MCPR["MCP Registry<br/>───────────<br/>Store connections<br/>By server name"]
        
        TR["Tool Registry<br/>───────────<br/>Store tool objects<br/>By tool ID"]
        
        SKR["Skill Registry<br/>───────────<br/>Group tools<br/>By skill name"]
        
        SSR["Skillset Registry<br/>───────────<br/>Group skills<br/>By skillset name"]
        
        AR["Agent Registry<br/>───────────<br/>Store agents<br/>Native + external"]
    end

    CL --> SV
    SV --> LLMR
    SV --> MCPR
    SV --> TR
    TR --> SKR
    SKR --> SSR
    SSR --> AR
```

| Component | Responsibility | Storage Format |
|-----------|----------------|----------------|
| **Config Loader** | Parse config files, apply defaults | YAML/JSON → dict |
| **Schema Validator** | Validate against JSON Schema | Pydantic models |
| **LLM Registry** | Map config names to LLM clients | `Dict[str, LLMClient]` |
| **MCP Registry** | Map server names to connections | `Dict[str, MCPConnection]` |
| **Tool Registry** | Map tool IDs to callable objects | `Dict[str, Tool]` |
| **Skill Registry** | Map skill names to tool lists | `Dict[str, List[str]]` |
| **Skillset Registry** | Map skillset names to skill lists | `Dict[str, List[str]]` |
| **Agent Registry** | Map agent names to agent objects | `Dict[str, Agent]` |

### 3.5 A2A Discovery Components

```mermaid
flowchart TB
    subgraph DiscoveryComponents["A2A Discovery Components"]
        SM["Seed Manager<br/>───────────<br/>Load seed URLs<br/>Classify type"]
        
        HIF["Host Index Fetcher<br/>───────────<br/>GET /a2a/index.json<br/>Extract agent URLs"]
        
        ACF["Agent Card Fetcher<br/>───────────<br/>GET /.well-known/<br/>agent.json"]
        
        CP["Card Parser<br/>───────────<br/>Parse Agent Card<br/>Extract metadata"]
        
        IPE["Import Policy Engine<br/>───────────<br/>Apply filters<br/>Include/exclude"]
    end

    SM --> HIF
    SM --> ACF
    HIF --> ACF
    ACF --> CP
    CP --> IPE
```

| Component | Responsibility | Key Methods |
|-----------|----------------|-------------|
| **Seed Manager** | Iterate seed URLs, detect type | `process_seeds()` |
| **Host Index Fetcher** | Fetch multi-agent host index | `fetch_index()` |
| **Agent Card Fetcher** | Fetch individual Agent Card | `fetch_card()` |
| **Card Parser** | Parse JSON to AgentCard model | `parse()` |
| **Import Policy Engine** | Apply include/exclude rules | `apply_policy()` |

---

## 4. Component Dependency Matrix

```
                    │ LLM  │ MCP  │ Tool │ Skill│ S.Set│ Agent│
                    │ Reg  │ Reg  │ Reg  │ Reg  │ Reg  │ Reg  │
────────────────────┼──────┼──────┼──────┼──────┼──────┼──────┤
LLM Factory         │  R   │      │      │      │      │      │
MCP Tool Loader     │      │  R   │  W   │      │      │      │
Skill Registry      │      │      │  R   │  W   │      │      │
Skillset Registry   │      │      │      │  R   │  W   │      │
Agent Factory       │  R   │      │      │      │  R   │  W   │
Graph Factory       │      │      │      │      │      │  R   │
Import Policy Engine│      │      │      │      │      │  W   │

R = Reads from    W = Writes to
```

---

## 5. Component Communication Patterns

### 5.1 Synchronous Request-Response

```mermaid
sequenceDiagram
    participant Chat as Chat Endpoint
    participant GF as Graph Factory
    participant SN as Supervisor Node
    participant NWN as Native Worker Node
    participant AF as Agent Factory

    Chat->>GF: invoke(messages)
    GF->>SN: run(state)
    SN->>SN: decide_next()
    SN->>GF: return next=worker
    GF->>NWN: run(state)
    NWN->>AF: execute(task)
    AF-->>NWN: result
    NWN-->>GF: updated_state
    GF-->>Chat: final_response
```

### 5.2 Streaming Pass-Through

```mermaid
sequenceDiagram
    participant SH as Stream Handler
    participant LG as LangGraph
    participant NWN as Native Worker Node
    participant AF as Agent Factory
    participant LLM as LLM Provider

    SH->>LG: stream(messages)
    LG->>NWN: run(state)
    NWN->>AF: execute_stream(task)
    AF->>LLM: stream_request()
    loop For each chunk
        LLM-->>AF: chunk
        AF-->>NWN: chunk
        NWN-->>LG: chunk
        LG-->>SH: chunk
    end
```

---

## 6. Error Handling by Component

| Component | Error Type | Handling Strategy |
|-----------|------------|-------------------|
| Config Loader | Invalid YAML | Fail fast, clear error message |
| Schema Validator | Schema violation | Fail fast, list violations |
| MCP Tool Loader | Connection failed | Log warning, skip server |
| Agent Card Fetcher | HTTP error | Log warning, skip agent |
| Import Policy Engine | No agents pass filter | Log warning, continue |
| Supervisor Node | Routing ambiguity | Use send_message |
| Native Worker Node | Tool error | Return error in result |
| External Agent Node | Timeout | Return timeout error |
| Iteration Controller | Max iterations | Force END state |

---

## 7. Related Documents

- D05: Container Diagram (C4 Level 2)
- D10-D24: Module Specifications (LLD)
- D34-D42: Sequence Diagrams

---

## 8. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Architecture Team | Initial draft |
