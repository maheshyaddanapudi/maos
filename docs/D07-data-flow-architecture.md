# D07: Data Flow Architecture

## Config-Driven Multi-Agent Orchestration System

**Document ID:** D07  
**Version:** 1.0  
**Status:** Draft  
**Last Updated:** January 2026

---

## 1. Overview

This document describes how data flows through the Multi-Agent Orchestration System, from user input to final response. Understanding data flow is critical for debugging, performance optimization, and ensuring correct state management.

---

## 2. End-to-End Data Flow

```mermaid
flowchart LR
    subgraph Input["📥 Input"]
        User["User Message"]
        Context["Conversation Context"]
    end

    subgraph API["🌐 API Layer"]
        Validate["Validate Request"]
        BuildState["Build Initial State"]
    end

    subgraph Graph["🔄 LangGraph Orchestration"]
        Supervisor["Supervisor Node"]
        Router["Route Decision"]
        Workers["Worker Nodes"]
        External["External Nodes"]
        Aggregate["Aggregate Results"]
    end

    subgraph Execution["⚡ Execution Layer"]
        AnyAgent["Any-Agent Runtime"]
        MCP["MCP Tool Calls"]
        A2A["A2A Agent Calls"]
        LLM["LLM Inference"]
    end

    subgraph Output["📤 Output"]
        Response["Final Response"]
        Stream["Stream Chunks"]
    end

    User --> Validate
    Context --> Validate
    Validate --> BuildState
    BuildState --> Supervisor
    
    Supervisor --> Router
    Router -->|native| Workers
    Router -->|external| External
    Router -->|done| Aggregate
    
    Workers --> AnyAgent
    External --> A2A
    AnyAgent --> MCP
    AnyAgent --> LLM
    A2A --> LLM
    
    MCP --> Workers
    LLM --> Workers
    LLM --> External
    A2A --> External
    
    Workers --> Supervisor
    External --> Supervisor
    
    Aggregate --> Response
    Aggregate --> Stream
```

---

## 3. Request Processing Flow

### 3.1 Inbound Request Flow

```mermaid
flowchart TB
    subgraph Client["Client"]
        HTTP["HTTP POST /chat"]
        WS["WebSocket"]
    end

    subgraph Validation["Request Validation"]
        Parse["Parse JSON Body"]
        Schema["Validate Schema"]
        Sanitize["Sanitize Input"]
    end

    subgraph StateInit["State Initialization"]
        Messages["Extract Messages"]
        Roster["Load Agent Roster"]
        Defaults["Apply Defaults"]
        InitState["Create Initial State"]
    end

    subgraph Invoke["Graph Invocation"]
        Compile["Get Compiled Graph"]
        Invoke2["Invoke with State"]
    end

    HTTP --> Parse
    WS --> Parse
    Parse --> Schema
    Schema --> Sanitize
    Sanitize --> Messages
    Messages --> Roster
    Roster --> Defaults
    Defaults --> InitState
    InitState --> Compile
    Compile --> Invoke2
```

### 3.2 Request Data Structure

```python
# Inbound Request
{
    "messages": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
    ],
    "stream": true,
    "context": {
        "session_id": "...",
        "metadata": {}
    }
}

# Initial Graph State
{
    "messages": [...],
    "task": "normalized user request",
    "context": {...},
    "roster": ["research_agent", "code_agent", "ext::analytics"],
    "last_result": None,
    "next": None,
    "done": False,
    "iteration": 0
}
```

---

## 4. Supervisor Routing Flow

### 4.1 Routing Decision Process

```mermaid
flowchart TB
    subgraph Input["Input to Supervisor"]
        State["Current State"]
        Messages["Message History"]
        LastResult["Last Worker Result"]
    end

    subgraph Decision["Routing Decision"]
        Analyze["Analyze Task"]
        MatchSkills["Match to Worker Skills"]
        CheckComplete["Check if Complete"]
    end

    subgraph Outcomes["Possible Outcomes"]
        RouteWorker["Route to Native Worker"]
        RouteExternal["Route to External Agent"]
        RequestInput["Request User Input"]
        Complete["Mark Complete (END)"]
    end

    State --> Analyze
    Messages --> Analyze
    LastResult --> Analyze
    
    Analyze --> MatchSkills
    MatchSkills --> CheckComplete
    
    CheckComplete -->|"needs work"| RouteWorker
    CheckComplete -->|"needs external"| RouteExternal
    CheckComplete -->|"needs clarification"| RequestInput
    CheckComplete -->|"done"| Complete
```

### 4.2 Routing State Update

```python
# Supervisor Output
{
    "next": "research_agent",  # or "ext::analytics" or "END"
    "messages": [
        # Supervisor's routing message
        {"role": "assistant", "content": "Routing to research agent..."}
    ],
    "context": {
        "routing_reason": "Task requires web research",
        "expected_output": "Summary of findings"
    }
}
```

---

## 5. Worker Execution Flow

### 5.1 Native Worker Data Flow

```mermaid
flowchart TB
    subgraph Input["Worker Input"]
        Task["Task from Supervisor"]
        Tools["Available Tools"]
        Prompt["System Prompt"]
    end

    subgraph AnyAgent["Any-Agent Execution"]
        Framework["Framework Adapter"]
        LLMCall["LLM Inference"]
        ToolSelect["Tool Selection"]
    end

    subgraph ToolExec["Tool Execution"]
        MCPCall["MCP Tool Call"]
        ToolResult["Tool Result"]
        ParseResult["Parse Result"]
    end

    subgraph Output["Worker Output"]
        WorkerResult["Worker Result"]
        UpdateState["Update State"]
    end

    Task --> Framework
    Tools --> Framework
    Prompt --> Framework
    
    Framework --> LLMCall
    LLMCall --> ToolSelect
    ToolSelect --> MCPCall
    MCPCall --> ToolResult
    ToolResult --> ParseResult
    ParseResult --> LLMCall
    
    LLMCall -->|"final answer"| WorkerResult
    WorkerResult --> UpdateState
```

### 5.2 Worker Result Structure

```python
# Worker Result
{
    "from": "research_agent",
    "output": {
        "type": "text",
        "content": "Research findings...",
        "sources": ["https://..."],
        "tool_calls": [
            {"tool": "search_web", "input": "...", "output": "..."}
        ]
    },
    "metadata": {
        "tokens_used": 1500,
        "duration_ms": 3200,
        "tools_invoked": ["search_web", "summarize"]
    }
}
```

---

## 6. External Agent (A2A) Data Flow

### 6.1 A2A Communication Flow

```mermaid
flowchart TB
    subgraph Orchestrator["Orchestrator"]
        PrepareTask["Prepare A2A Task"]
        A2AClient["A2A Client"]
        HandleResponse["Handle Response"]
    end

    subgraph Network["Network"]
        HTTPS["HTTPS Request"]
        JSONRpc["JSON-RPC 2.0"]
    end

    subgraph External["External Agent"]
        Receive["Receive Task"]
        Process["Process Task"]
        Respond["Send Response"]
    end

    subgraph Result["Result Handling"]
        Parse["Parse A2A Response"]
        Convert["Convert to State"]
        Return["Return to Supervisor"]
    end

    PrepareTask --> A2AClient
    A2AClient --> HTTPS
    HTTPS --> JSONRpc
    JSONRpc --> Receive
    
    Receive --> Process
    Process --> Respond
    
    Respond --> JSONRpc
    JSONRpc --> HTTPS
    HTTPS --> HandleResponse
    
    HandleResponse --> Parse
    Parse --> Convert
    Convert --> Return
```

### 6.2 A2A Message Structures

```python
# A2A Request (JSON-RPC 2.0)
{
    "jsonrpc": "2.0",
    "method": "message/send",
    "id": "req-123",
    "params": {
        "message": {
            "role": "user",
            "parts": [
                {"type": "text", "text": "Analyze this data..."}
            ]
        },
        "configuration": {
            "timeout": 40
        }
    }
}

# A2A Response
{
    "jsonrpc": "2.0",
    "id": "req-123",
    "result": {
        "task": {
            "id": "task-456",
            "status": "COMPLETED",
            "result": {
                "role": "agent",
                "parts": [
                    {"type": "text", "text": "Analysis complete..."}
                ]
            }
        }
    }
}
```

---

## 7. MCP Tool Data Flow

### 7.1 Tool Invocation Flow

```mermaid
flowchart LR
    subgraph Agent["Agent"]
        Decide["Decide Tool"]
        Prepare["Prepare Args"]
        Invoke["Invoke Tool"]
        Process["Process Result"]
    end

    subgraph MCPClient["MCP Client"]
        Serialize["Serialize Request"]
        Transport["Transport Layer"]
        Deserialize["Deserialize Response"]
    end

    subgraph MCPServer["MCP Server"]
        Receive["Receive Request"]
        Validate["Validate Args"]
        Execute["Execute Tool"]
        Return["Return Result"]
    end

    Decide --> Prepare
    Prepare --> Invoke
    Invoke --> Serialize
    Serialize --> Transport
    Transport --> Receive
    
    Receive --> Validate
    Validate --> Execute
    Execute --> Return
    
    Return --> Transport
    Transport --> Deserialize
    Deserialize --> Process
```

### 7.2 MCP Message Structures

```python
# MCP Tool Call Request
{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 1,
    "params": {
        "name": "search.web",
        "arguments": {
            "query": "latest AI research",
            "limit": 10
        }
    }
}

# MCP Tool Call Response
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "content": [
            {
                "type": "text",
                "text": "Search results..."
            }
        ],
        "isError": false
    }
}
```

---

## 8. Streaming Data Flow

### 8.1 Stream Pipeline

```mermaid
flowchart LR
    subgraph Source["Stream Source"]
        LLM["LLM Provider"]
        Worker["Worker Agent"]
        External["External Agent"]
    end

    subgraph Pipeline["Stream Pipeline"]
        Collect["Collect Chunks"]
        Transform["Transform Format"]
        Buffer["Buffer (optional)"]
    end

    subgraph Delivery["Delivery"]
        SSE["SSE Formatter"]
        WS["WebSocket"]
        Client["Client"]
    end

    LLM --> Collect
    Worker --> Collect
    External --> Collect
    
    Collect --> Transform
    Transform --> Buffer
    
    Buffer --> SSE
    Buffer --> WS
    
    SSE --> Client
    WS --> Client
```

### 8.2 Stream Chunk Structure

```python
# SSE Stream Chunk
data: {"type": "chunk", "content": "Here is", "done": false}

data: {"type": "chunk", "content": " the analysis", "done": false}

data: {"type": "chunk", "content": "...", "done": false}

data: {"type": "done", "content": "", "done": true, "metadata": {...}}
```

---

## 9. State Transitions

### 9.1 Graph State Evolution

```mermaid
flowchart TB
    subgraph S1["Initial State"]
        S1M["messages: [user_msg]"]
        S1N["next: null"]
        S1D["done: false"]
        S1I["iteration: 0"]
    end

    subgraph S2["After Supervisor (Route)"]
        S2M["messages: [user_msg, routing_msg]"]
        S2N["next: 'research_agent'"]
        S2D["done: false"]
        S2I["iteration: 1"]
    end

    subgraph S3["After Worker"]
        S3M["messages: [..., worker_result]"]
        S3L["last_result: {from: 'research_agent', ...}"]
        S3N["next: null"]
        S3I["iteration: 2"]
    end

    subgraph S4["After Supervisor (Complete)"]
        S4M["messages: [..., final_response]"]
        S4N["next: 'END'"]
        S4D["done: true"]
        S4I["iteration: 3"]
    end

    S1 --> S2
    S2 --> S3
    S3 --> S4
```

### 9.2 State Reducer Operations

| Field | Reducer | Behavior |
|-------|---------|----------|
| `messages` | `add_messages` | Append new messages to list |
| `last_result` | Replace | Overwrite with latest result |
| `next` | Replace | Overwrite with routing decision |
| `done` | Replace | Overwrite with completion flag |
| `iteration` | Increment | Add 1 each supervisor cycle |
| `context` | Merge | Deep merge new context |

---

## 10. Error Data Flow

### 10.1 Error Propagation

```mermaid
flowchart TB
    subgraph Source["Error Sources"]
        ToolError["Tool Execution Error"]
        LLMError["LLM API Error"]
        A2AError["A2A Timeout/Error"]
        ValidationError["Validation Error"]
    end

    subgraph Handling["Error Handling"]
        Catch["Catch Exception"]
        Classify["Classify Error Type"]
        Decide["Decide Action"]
    end

    subgraph Actions["Possible Actions"]
        Retry["Retry with Backoff"]
        Fallback["Try Fallback"]
        Report["Report to Supervisor"]
        Fail["Fail Request"]
    end

    subgraph Response["Error Response"]
        ErrorState["Update State with Error"]
        ErrorMsg["Error Message to User"]
    end

    ToolError --> Catch
    LLMError --> Catch
    A2AError --> Catch
    ValidationError --> Catch
    
    Catch --> Classify
    Classify --> Decide
    
    Decide -->|"retryable"| Retry
    Decide -->|"has fallback"| Fallback
    Decide -->|"recoverable"| Report
    Decide -->|"fatal"| Fail
    
    Retry -->|"success"| Report
    Retry -->|"exhausted"| Fail
    Fallback -->|"success"| Report
    Fallback -->|"failed"| Fail
    
    Report --> ErrorState
    Fail --> ErrorMsg
```

### 10.2 Error State Structure

```python
# Error in Worker Result
{
    "from": "research_agent",
    "output": {
        "type": "error",
        "error_code": "TOOL_TIMEOUT",
        "error_message": "search_web timed out after 30s",
        "partial_result": None
    },
    "metadata": {
        "retries_attempted": 2,
        "duration_ms": 90500
    }
}

# Error Response to Client
{
    "error": {
        "code": "EXECUTION_ERROR",
        "message": "Unable to complete research task",
        "details": {
            "worker": "research_agent",
            "cause": "Tool timeout"
        }
    }
}
```

---

## 11. Data Flow Metrics

### 11.1 Key Metrics Points

| Point | Metrics Captured |
|-------|------------------|
| Request Received | `request_count`, `request_size_bytes` |
| Supervisor Decision | `routing_decisions`, `routing_latency_ms` |
| Worker Execution | `worker_duration_ms`, `tools_invoked` |
| MCP Tool Call | `tool_latency_ms`, `tool_success_rate` |
| A2A Call | `a2a_latency_ms`, `a2a_success_rate` |
| LLM Inference | `llm_latency_ms`, `tokens_used` |
| Response Sent | `response_latency_ms`, `response_size_bytes` |

---

## 12. Related Documents

- D05: Container Diagram
- D06: Component Overview
- D08: Integration Architecture
- D34-D42: Sequence Diagrams

---

## 13. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Architecture Team | Initial draft |
