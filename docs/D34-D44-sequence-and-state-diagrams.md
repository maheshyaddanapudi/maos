# D34-D44: Sequence and State Diagrams

## Config-Driven Multi-Agent Orchestration System

**Document ID:** D34-D44  
**Version:** 1.0  
**Status:** Draft  
**Last Updated:** January 2026

---

## Document Index

| Doc ID | Diagram | Description |
|--------|---------|-------------|
| D34 | Boot Lifecycle | Config load → registries → discovery → graph → serve |
| D35 | Native Worker Path | User → Supervisor → Worker → MCP → Response |
| D36 | External Agent Path | User → Supervisor → External → A2A → Response |
| D37 | tools_only Mode | Worker → A2A tool call → Response |
| D38 | Human-in-the-Loop | Supervisor → send_message → User → Resume |
| D39 | A2A Discovery (Host) | Boot → Index → Agent Cards → Import |
| D40 | A2A Discovery (Individual) | Boot → Agent Card → Import |
| D41 | Streaming Pass-through | Worker streams → API streams → Client |
| D42 | Timeout & Error Handling | Timeout → Retry → Fallback → Error |
| D43 | Supervisor Routing Loop | State machine for supervisor |
| D44 | Task Lifecycle | State machine for task execution |

---

## D34: Boot Lifecycle Sequence

```mermaid
sequenceDiagram
    participant Main as Main Entry
    participant CL as Config Loader
    participant SV as Schema Validator
    participant LLMR as LLM Registry
    participant MCPR as MCP Registry
    participant TR as Tool Registry
    participant SKR as Skill Registry
    participant SSR as Skillset Registry
    participant AR as Agent Registry
    participant A2AD as A2A Discovery
    participant GF as Graph Factory
    participant API as API Server

    Main->>CL: load_config(path)
    CL->>CL: Read YAML/JSON
    CL->>SV: validate(config)
    SV-->>CL: validation result
    
    alt Validation Failed
        CL-->>Main: ConfigError
    end

    CL-->>Main: parsed config

    Main->>LLMR: build(config.llms)
    loop For each LLM config
        LLMR->>LLMR: Create LLM client
        LLMR->>LLMR: Verify connection
    end
    LLMR-->>Main: LLM Registry ready

    Main->>MCPR: connect(config.mcp_servers)
    loop For each MCP server
        MCPR->>MCPR: Establish connection
        MCPR->>MCPR: Handshake
    end
    MCPR-->>Main: MCP Registry ready

    Main->>TR: materialize(config.tools, MCPR)
    loop For each tool
        TR->>MCPR: Get tool from server
        TR->>TR: Create tool object
    end
    TR-->>Main: Tool Registry ready

    Main->>SKR: build(config.skills, TR)
    loop For each skill
        SKR->>TR: Resolve tools
        SKR->>SKR: Create skill
    end
    SKR-->>Main: Skill Registry ready

    Main->>SSR: build(config.skillsets, SKR)
    loop For each skillset
        SSR->>SKR: Resolve skills
        SSR->>SSR: Create skillset
    end
    SSR-->>Main: Skillset Registry ready

    Main->>AR: build_native(config.agents, SSR, LLMR)
    loop For each native agent
        AR->>AR: Apply ignore list
        AR->>SSR: Get skillset
        AR->>LLMR: Get LLM
        AR->>AR: Instantiate Any-Agent
    end
    AR-->>Main: Native agents ready

    Main->>A2AD: discover(config.a2a)
    loop For each seed URL
        A2AD->>A2AD: Fetch Agent Card or Index
        A2AD->>A2AD: Parse cards
        A2AD->>A2AD: Apply import policy
    end
    A2AD->>AR: Register external agents
    A2AD-->>Main: Discovery complete

    Main->>GF: build_graph(AR)
    GF->>GF: Create supervisor node
    GF->>GF: Create worker nodes
    GF->>GF: Create external nodes
    GF->>GF: Wire edges
    GF->>GF: Compile graph
    GF-->>Main: Compiled graph

    Main->>API: serve(graph, config.serving)
    API->>API: Setup routes
    API->>API: Start server
    API-->>Main: Server running
```

---

## D35: Native Worker Path Sequence

```mermaid
sequenceDiagram
    participant User as User
    participant API as API Server
    participant LG as LangGraph
    participant SN as Supervisor Node
    participant WN as Worker Node
    participant AA as Any-Agent
    participant MCP as MCP Server
    participant LLM as LLM Provider

    User->>API: POST /chat {messages}
    API->>API: Validate request
    API->>LG: invoke(initial_state)
    
    LG->>SN: run(state)
    SN->>LLM: Analyze task + decide routing
    LLM-->>SN: Route to research_agent
    SN-->>LG: next = "research_agent"
    
    LG->>WN: run(state)
    WN->>AA: execute(task)
    
    AA->>LLM: Generate with tools
    LLM-->>AA: Tool call: search_web
    
    AA->>MCP: tools/call(search_web, args)
    MCP-->>AA: Search results
    
    AA->>LLM: Continue with tool result
    LLM-->>AA: Final response
    
    AA-->>WN: worker_result
    WN-->>LG: updated_state
    
    LG->>SN: run(state)
    SN->>LLM: Check if complete
    LLM-->>SN: Task complete
    SN-->>LG: next = "END"
    
    LG-->>API: final_state
    API-->>User: Response
```

---

## D36: External Agent Path Sequence

```mermaid
sequenceDiagram
    participant User as User
    participant API as API Server
    participant LG as LangGraph
    participant SN as Supervisor Node
    participant EN as External Node
    participant A2A as A2A Client
    participant Ext as External Agent

    User->>API: POST /chat {messages}
    API->>LG: invoke(initial_state)
    
    LG->>SN: run(state)
    SN->>SN: Analyze task
    SN-->>LG: next = "ext::analytics"
    
    LG->>EN: run(state)
    EN->>A2A: send_task(message)
    
    A2A->>Ext: POST /a2a (message/send)
    
    alt Synchronous
        Ext-->>A2A: Task result
    else Streaming
        loop Stream chunks
            Ext-->>A2A: SSE chunk
        end
        Ext-->>A2A: Complete
    end
    
    A2A-->>EN: external_result
    EN-->>LG: updated_state
    
    LG->>SN: run(state)
    SN-->>LG: next = "END"
    
    LG-->>API: final_state
    API-->>User: Response
```

---

## D37: tools_only Mode Sequence

```mermaid
sequenceDiagram
    participant User as User
    participant API as API Server
    participant LG as LangGraph
    participant SN as Supervisor Node
    participant WN as Worker Node
    participant AA as Any-Agent
    participant A2ATool as A2A Tool
    participant Ext as External Agent

    User->>API: POST /chat {messages}
    API->>LG: invoke(initial_state)
    
    LG->>SN: run(state)
    SN-->>LG: next = "research_agent"
    
    LG->>WN: run(state)
    WN->>AA: execute(task)
    
    Note over AA: Worker has external agent<br/>attached as tool
    
    AA->>AA: Decide to use external tool
    AA->>A2ATool: call_external_agent(args)
    
    A2ATool->>Ext: POST /a2a (message/send)
    Ext-->>A2ATool: External result
    
    A2ATool-->>AA: Tool result
    AA->>AA: Continue with result
    AA-->>WN: worker_result
    
    WN-->>LG: updated_state
    
    LG->>SN: run(state)
    SN-->>LG: next = "END"
    
    LG-->>API: final_state
    API-->>User: Response
```

---

## D38: Human-in-the-Loop Sequence

```mermaid
sequenceDiagram
    participant User as User
    participant API as API Server
    participant LG as LangGraph
    participant SN as Supervisor Node
    participant SM as send_message Tool

    User->>API: POST /chat {"Analyze the data"}
    API->>LG: invoke(initial_state)
    
    LG->>SN: run(state)
    SN->>SN: Analyze: ambiguous request
    SN->>SM: send_message("Which dataset?<br/>1. Sales data<br/>2. User data")
    SM-->>SN: Message sent
    
    SN-->>LG: next = "AWAIT_INPUT"
    LG-->>API: partial_state (awaiting input)
    API-->>User: "Which dataset? 1. Sales 2. User"
    
    Note over User,API: User provides clarification
    
    User->>API: POST /chat {"Sales data"}
    API->>LG: resume(state, user_input)
    
    LG->>SN: run(state + user_input)
    SN->>SN: Now clear: analyze sales
    SN-->>LG: next = "analysis_agent"
    
    Note over LG: Continue normal flow
    
    LG-->>API: final_state
    API-->>User: Analysis results
```

---

## D39: A2A Discovery (Host Index) Sequence

```mermaid
sequenceDiagram
    participant Boot as Boot Loader
    participant Disc as A2A Discovery
    participant HTTP as HTTP Client
    participant Host as Multi-Agent Host
    participant Policy as Import Policy

    Boot->>Disc: discover(seeds)
    
    loop For each seed URL
        Disc->>HTTP: GET seed_url/a2a/index.json
        
        alt Is Host Index
            HTTP-->>Disc: Host index JSON
            Disc->>Disc: Parse host index
            
            loop For each agent in index
                Disc->>HTTP: GET agent_card_url
                HTTP-->>Host: Request Agent Card
                Host-->>HTTP: Agent Card JSON
                HTTP-->>Disc: Agent Card
                Disc->>Disc: Parse Agent Card
            end
        else Is Individual Agent
            Disc->>HTTP: GET seed_url/.well-known/agent.json
            HTTP-->>Disc: Agent Card JSON
            Disc->>Disc: Parse Agent Card
        end
    end
    
    Disc->>Policy: apply_policy(discovered_agents)
    Policy->>Policy: Filter by tags
    Policy->>Policy: Filter by names
    Policy->>Policy: Apply max_agents limit
    Policy-->>Disc: filtered_agents
    
    Disc-->>Boot: discovered_agents
```

---

## D40: A2A Discovery (Individual) Sequence

```mermaid
sequenceDiagram
    participant Boot as Boot Loader
    participant Disc as A2A Discovery
    participant HTTP as HTTP Client
    participant Agent as Individual Agent Server
    participant Policy as Import Policy
    participant AR as Agent Registry

    Boot->>Disc: discover([agent_url])
    
    Disc->>HTTP: GET agent_url/.well-known/agent.json
    HTTP->>Agent: Request
    Agent-->>HTTP: Agent Card JSON
    HTTP-->>Disc: Response
    
    Disc->>Disc: Parse Agent Card
    
    Note over Disc: Extract from Agent Card:<br/>- name, description<br/>- skills<br/>- endpoint<br/>- capabilities
    
    Disc->>Policy: apply_policy([agent])
    Policy->>Policy: Check include_tags
    Policy->>Policy: Check exclude_names
    Policy-->>Disc: approved/rejected
    
    alt Approved
        Disc->>AR: register_external(agent)
        AR-->>Disc: ext::agent_name
    else Rejected
        Note over Disc: Skip agent
    end
    
    Disc-->>Boot: discovery_result
```

---

## D41: Streaming Pass-through Sequence

```mermaid
sequenceDiagram
    participant User as User
    participant API as API Server
    participant LG as LangGraph
    participant WN as Worker Node
    participant AA as Any-Agent
    participant LLM as LLM Provider

    User->>API: POST /chat {stream: true}
    API->>API: Setup SSE response
    API->>LG: stream(initial_state)
    
    LG->>WN: run_stream(state)
    WN->>AA: execute_stream(task)
    AA->>LLM: stream_request()
    
    loop For each token
        LLM-->>AA: Token chunk
        AA-->>WN: Chunk
        WN-->>LG: Chunk
        LG-->>API: Chunk
        API-->>User: SSE: data: {"chunk": "..."}
    end
    
    LLM-->>AA: Stream complete
    AA-->>WN: Final result
    WN-->>LG: updated_state
    
    LG->>LG: Route to supervisor
    Note over LG: Supervisor decides END
    
    LG-->>API: Stream complete
    API-->>User: SSE: data: {"done": true}
```

---

## D42: Timeout and Error Handling Sequence

```mermaid
sequenceDiagram
    participant LG as LangGraph
    participant Node as Worker/External Node
    participant Exec as Executor
    participant Retry as Retry Handler
    participant Error as Error Handler

    LG->>Node: run(state)
    Node->>Exec: execute(task)
    
    alt Timeout
        Exec--xNode: Timeout error
        Node->>Retry: handle_timeout()
        
        loop Retry attempts
            Retry->>Exec: retry(task)
            alt Success
                Exec-->>Retry: Result
                Retry-->>Node: Result
            else Timeout again
                Exec--xRetry: Timeout
                Retry->>Retry: Increment attempt
            end
        end
        
        alt Retries exhausted
            Retry-->>Node: Max retries exceeded
            Node->>Error: handle_failure()
            Error-->>LG: Error state
        end
        
    else Tool Error
        Exec--xNode: Tool error
        Node->>Error: handle_tool_error()
        
        alt Recoverable
            Error-->>Node: Error result (partial)
            Node-->>LG: State with error info
        else Fatal
            Error-->>LG: Fail state
        end
        
    else LLM Error
        Exec--xNode: LLM API error
        Node->>Retry: handle_llm_error()
        
        alt Rate limit
            Retry->>Retry: Wait with backoff
            Retry->>Exec: Retry
        else Auth error
            Retry-->>Node: Unrecoverable
            Node->>Error: handle_failure()
        end
    end
```

---

## D43: Supervisor Routing Loop State Machine

```mermaid
stateDiagram-v2
    [*] --> Initialize: Graph invoked
    
    Initialize --> Analyze: Load state
    
    Analyze --> Routing: Determine next action
    
    Routing --> DelegateWorker: next = worker
    Routing --> DelegateExternal: next = external
    Routing --> RequestInput: needs clarification
    Routing --> Complete: task done
    
    DelegateWorker --> AwaitWorker: Invoke worker
    DelegateExternal --> AwaitExternal: Invoke external
    
    AwaitWorker --> Analyze: Worker returns
    AwaitExternal --> Analyze: External returns
    
    RequestInput --> AwaitHuman: send_message
    AwaitHuman --> Analyze: Human responds
    
    Complete --> [*]: Return final state
    
    note right of Analyze
        Check iteration count
        If max reached → Complete
    end note
    
    note right of Routing
        Supervisor LLM decides:
        - Which worker/external
        - If clarification needed
        - If task complete
    end note
```

---

## D44: Task Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> Received: Request received
    
    Received --> Validated: Validation passed
    Received --> Rejected: Validation failed
    
    Rejected --> [*]: Return error
    
    Validated --> Queued: State initialized
    
    Queued --> Executing: Graph invoked
    
    Executing --> Routing: In supervisor
    Executing --> WorkerActive: In worker
    Executing --> ExternalActive: In external
    
    Routing --> WorkerActive: Route to worker
    Routing --> ExternalActive: Route to external
    Routing --> AwaitingInput: Need clarification
    Routing --> Completed: Task done
    
    WorkerActive --> Routing: Worker done
    WorkerActive --> Failed: Worker error
    
    ExternalActive --> Routing: External done
    ExternalActive --> Failed: External timeout
    
    AwaitingInput --> Routing: Input received
    AwaitingInput --> Cancelled: Timeout
    
    Completed --> [*]: Return success
    Failed --> [*]: Return error
    Cancelled --> [*]: Return cancelled
    
    note right of Executing
        May loop between:
        Routing ↔ WorkerActive
        Routing ↔ ExternalActive
        Up to max_iterations
    end note
```

---

## Summary: Diagram Count

| Doc ID | Diagram Type | Count |
|--------|--------------|-------|
| D34 | sequenceDiagram | 1 |
| D35 | sequenceDiagram | 1 |
| D36 | sequenceDiagram | 1 |
| D37 | sequenceDiagram | 1 |
| D38 | sequenceDiagram | 1 |
| D39 | sequenceDiagram | 1 |
| D40 | sequenceDiagram | 1 |
| D41 | sequenceDiagram | 1 |
| D42 | sequenceDiagram | 1 |
| D43 | stateDiagram-v2 | 1 |
| D44 | stateDiagram-v2 | 1 |
| **Total** | | **11** |

---

## Related Documents

- D06: Component Overview
- D07: Data Flow Architecture
- D08: Integration Architecture
- D45-D50: Data Models

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Architecture Team | Initial draft |
