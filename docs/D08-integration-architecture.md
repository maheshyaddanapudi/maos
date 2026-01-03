# D08: Integration Architecture

## Config-Driven Multi-Agent Orchestration System

**Document ID:** D08  
**Version:** 1.0  
**Status:** Draft  
**Last Updated:** January 2026

---

## 1. Overview

This document describes how the Multi-Agent Orchestration System integrates with external systems: LLM providers, MCP servers, and A2A external agents. Each integration point has specific patterns, protocols, and failure modes.

---

## 2. Integration Landscape

```mermaid
flowchart TB
    subgraph Core["Multi-Agent Orchestration System"]
        API["API Server"]
        LG["LangGraph Engine"]
        AA["Any-Agent Runtime"]
    end

    subgraph LLMIntegration["LLM Provider Integration"]
        LLMFactory["LLM Factory"]
        OpenAI["OpenAI API"]
        Anthropic["Anthropic API"]
        Google["Google AI API"]
        Ollama["Ollama (Local)"]
        Azure["Azure OpenAI"]
    end

    subgraph MCPIntegration["MCP Tool Integration"]
        MCPClient["MCP Client"]
        MCPStdio["stdio Servers"]
        MCPHTTP["HTTP Servers"]
    end

    subgraph A2AIntegration["A2A Agent Integration"]
        A2AClient["A2A Client"]
        A2AHost["Multi-Agent Hosts"]
        A2AIndividual["Individual Agents"]
    end

    AA --> LLMFactory
    LLMFactory --> OpenAI
    LLMFactory --> Anthropic
    LLMFactory --> Google
    LLMFactory --> Ollama
    LLMFactory --> Azure

    AA --> MCPClient
    MCPClient --> MCPStdio
    MCPClient --> MCPHTTP

    AA --> A2AClient
    A2AClient --> A2AHost
    A2AClient --> A2AIndividual
```

---

## 3. LLM Provider Integration

### 3.1 Provider Architecture

```mermaid
flowchart TB
    subgraph Factory["LLM Factory"]
        Config["LLM Config"]
        Detect["Detect Provider"]
        Create["Create Client"]
        Cache["Client Cache"]
    end

    subgraph Adapters["Provider Adapters"]
        OpenAIAdapter["OpenAI Adapter"]
        AnthropicAdapter["Anthropic Adapter"]
        GoogleAdapter["Google Adapter"]
        OllamaAdapter["Ollama Adapter"]
    end

    subgraph Interface["Unified Interface"]
        Invoke["invoke(messages)"]
        Stream["stream(messages)"]
        Tokenize["count_tokens(text)"]
    end

    Config --> Detect
    Detect --> Create
    Create --> Cache
    
    Cache --> OpenAIAdapter
    Cache --> AnthropicAdapter
    Cache --> GoogleAdapter
    Cache --> OllamaAdapter
    
    OpenAIAdapter --> Interface
    AnthropicAdapter --> Interface
    GoogleAdapter --> Interface
    OllamaAdapter --> Interface
```

### 3.2 Provider Configuration Matrix

| Provider | Auth Method | Endpoint | Streaming | Tool Calling |
|----------|-------------|----------|-----------|--------------|
| OpenAI | API Key (Bearer) | `api.openai.com` | ✅ SSE | ✅ Native |
| Anthropic | API Key (x-api-key) | `api.anthropic.com` | ✅ SSE | ✅ Native |
| Google | API Key | `generativelanguage.googleapis.com` | ✅ SSE | ✅ Native |
| Ollama | None | `localhost:11434` | ✅ SSE | ✅ OpenAI-compat |
| Azure OpenAI | API Key | Custom endpoint | ✅ SSE | ✅ Native |

### 3.3 LLM Request/Response Flow

```mermaid
sequenceDiagram
    participant Agent as Agent
    participant Factory as LLM Factory
    participant Adapter as Provider Adapter
    participant API as LLM API

    Agent->>Factory: get_llm("openai")
    Factory->>Factory: Check cache
    Factory-->>Agent: LLM Client

    Agent->>Adapter: invoke(messages, tools)
    Adapter->>Adapter: Format request
    Adapter->>API: POST /chat/completions
    
    alt Streaming
        loop For each chunk
            API-->>Adapter: SSE chunk
            Adapter-->>Agent: Yield chunk
        end
    else Non-streaming
        API-->>Adapter: Complete response
        Adapter-->>Agent: Return response
    end
```

### 3.4 LLM Error Handling

| Error Type | HTTP Status | Retry | Action |
|------------|-------------|-------|--------|
| Rate limit | 429 | Yes (with backoff) | Wait and retry |
| Auth error | 401, 403 | No | Fail with config error |
| Server error | 500, 502, 503 | Yes (limited) | Retry up to 3 times |
| Timeout | - | Yes | Retry with longer timeout |
| Invalid request | 400 | No | Fail with validation error |

---

## 4. MCP Server Integration

### 4.1 MCP Transport Architecture

```mermaid
flowchart TB
    subgraph Client["MCP Client"]
        Registry["MCP Registry"]
        Router["Transport Router"]
    end

    subgraph StdioTransport["stdio Transport"]
        Spawn["Spawn Process"]
        StdinWriter["stdin Writer"]
        StdoutReader["stdout Reader"]
        ProcessMgr["Process Manager"]
    end

    subgraph HTTPTransport["HTTP Transport"]
        HTTPClient["HTTP Client"]
        SSEHandler["SSE Handler"]
        Reconnect["Reconnection Logic"]
    end

    subgraph Servers["MCP Servers"]
        LocalServer["Local MCP Server"]
        RemoteServer["Remote MCP Server"]
    end

    Registry --> Router
    Router -->|"stdio"| Spawn
    Router -->|"http"| HTTPClient
    
    Spawn --> StdinWriter
    Spawn --> StdoutReader
    StdinWriter --> LocalServer
    StdoutReader --> LocalServer
    ProcessMgr --> Spawn
    
    HTTPClient --> RemoteServer
    SSEHandler --> RemoteServer
    Reconnect --> HTTPClient
```

### 4.2 MCP Connection Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Disconnected
    
    Disconnected --> Connecting: connect()
    Connecting --> Connected: handshake success
    Connecting --> Failed: handshake failed
    
    Connected --> Disconnected: disconnect()
    Connected --> Reconnecting: connection lost
    
    Reconnecting --> Connected: reconnect success
    Reconnecting --> Failed: max retries
    
    Failed --> Connecting: retry()
    Failed --> [*]: give up
```

### 4.3 MCP Tool Discovery Flow

```mermaid
sequenceDiagram
    participant Boot as Boot Loader
    participant Registry as MCP Registry
    participant Client as MCP Client
    participant Server as MCP Server

    Boot->>Registry: connect_servers(config)
    
    loop For each server
        Registry->>Client: connect(server_config)
        Client->>Server: initialize
        Server-->>Client: capabilities
        Client->>Server: tools/list
        Server-->>Client: tool definitions
        Client-->>Registry: register tools
    end
    
    Registry-->>Boot: all tools registered
```

### 4.4 MCP Tool Call Flow

```mermaid
sequenceDiagram
    participant Agent as Agent
    participant Tool as Tool Object
    participant Client as MCP Client
    participant Server as MCP Server

    Agent->>Tool: call(args)
    Tool->>Client: tools/call
    Client->>Server: JSON-RPC request
    
    alt Success
        Server-->>Client: result
        Client-->>Tool: parsed result
        Tool-->>Agent: tool output
    else Error
        Server-->>Client: error response
        Client-->>Tool: MCP error
        Tool-->>Agent: raise ToolError
    end
```

---

## 5. A2A Agent Integration

### 5.1 A2A Discovery Architecture

```mermaid
flowchart TB
    subgraph Discovery["A2A Discovery"]
        Seeds["Seed URLs"]
        Fetcher["Agent Card Fetcher"]
        HostIndex["Host Index Parser"]
        CardParser["Card Parser"]
        Policy["Import Policy"]
    end

    subgraph Sources["Discovery Sources"]
        Individual["Individual Agent<br/>/.well-known/agent.json"]
        Host["Multi-Agent Host<br/>/a2a/index.json"]
    end

    subgraph Output["Discovery Output"]
        AgentList["Discovered Agents"]
        NodeGen["Node/Tool Generation"]
    end

    Seeds --> Fetcher
    Fetcher --> Individual
    Fetcher --> Host
    
    Individual --> CardParser
    Host --> HostIndex
    HostIndex --> Fetcher
    
    CardParser --> Policy
    Policy --> AgentList
    AgentList --> NodeGen
```

### 5.2 Host Index Structure

```json
{
  "version": "1.0",
  "host": {
    "name": "Analytics Agent Host",
    "description": "Hosts specialized analytics agents"
  },
  "agents": [
    {
      "name": "data-analyzer",
      "path": "/a2a/data-analyzer",
      "agent_card_path": "/a2a/data-analyzer/.well-known/agent.json"
    },
    {
      "name": "ml-predictor",
      "path": "/a2a/ml-predictor",
      "agent_card_path": "/a2a/ml-predictor/.well-known/agent.json"
    }
  ]
}
```

### 5.3 A2A Communication Flow

```mermaid
sequenceDiagram
    participant Node as External Agent Node
    participant Client as A2A Client
    participant External as External A2A Agent

    Node->>Client: send_task(message)
    Client->>Client: Build JSON-RPC request
    Client->>External: POST /a2a (message/send)
    
    alt Synchronous Response
        External-->>Client: Task result
        Client-->>Node: Parsed result
    else Streaming Response
        loop For each chunk
            External-->>Client: SSE event
            Client-->>Node: Yield chunk
        end
        External-->>Client: Task complete
        Client-->>Node: Final result
    else Async Task
        External-->>Client: Task ID (SUBMITTED)
        loop Poll for completion
            Client->>External: tasks/get
            External-->>Client: Task status
        end
        External-->>Client: Task result (COMPLETED)
        Client-->>Node: Parsed result
    end
```

### 5.4 A2A Task State Machine

```mermaid
stateDiagram-v2
    [*] --> SUBMITTED: message/send
    
    SUBMITTED --> WORKING: Agent starts
    
    WORKING --> COMPLETED: Success
    WORKING --> FAILED: Error
    WORKING --> INPUT_REQUIRED: Needs clarification
    WORKING --> CANCELLED: Cancel requested
    
    INPUT_REQUIRED --> WORKING: Input provided
    INPUT_REQUIRED --> CANCELLED: Timeout
    
    COMPLETED --> [*]
    FAILED --> [*]
    CANCELLED --> [*]
```

### 5.5 A2A Authentication (Future)

```mermaid
flowchart TB
    subgraph Auth["Authentication Flow"]
        Card["Read Agent Card"]
        Schemes["Get Security Schemes"]
        Select["Select Auth Method"]
    end

    subgraph Methods["Auth Methods"]
        Bearer["Bearer Token"]
        APIKey["API Key"]
        OAuth["OAuth 2.0"]
        mTLS["Mutual TLS"]
    end

    subgraph Apply["Apply Auth"]
        Headers["Add Headers"]
        Request["Make Request"]
    end

    Card --> Schemes
    Schemes --> Select
    
    Select --> Bearer
    Select --> APIKey
    Select --> OAuth
    Select --> mTLS
    
    Bearer --> Headers
    APIKey --> Headers
    OAuth --> Headers
    mTLS --> Request
    
    Headers --> Request
```

---

## 6. Integration Failure Modes

### 6.1 Failure Classification

```mermaid
flowchart TB
    subgraph Failures["Integration Failures"]
        Network["Network Failures"]
        Auth["Auth Failures"]
        Timeout["Timeout Failures"]
        Protocol["Protocol Failures"]
        Capacity["Capacity Failures"]
    end

    subgraph Responses["Response Strategies"]
        Retry["Retry with Backoff"]
        Fallback["Use Fallback"]
        Degrade["Graceful Degradation"]
        Fail["Fail Fast"]
    end

    Network --> Retry
    Auth --> Fail
    Timeout --> Retry
    Protocol --> Fail
    Capacity --> Degrade
    
    Retry -->|"exhausted"| Fallback
    Fallback -->|"no fallback"| Degrade
    Degrade -->|"critical"| Fail
```

### 6.2 Failure Handling Matrix

| Integration | Failure Type | Retry | Fallback | Degradation |
|-------------|--------------|-------|----------|-------------|
| LLM | Rate limit | Yes (backoff) | Alt provider | Reduced tokens |
| LLM | Timeout | Yes (2x) | Alt provider | Shorter prompt |
| MCP (stdio) | Process crash | Yes (respawn) | None | Skip tool |
| MCP (HTTP) | Connection lost | Yes (3x) | None | Skip tool |
| A2A | Timeout | Yes (1x) | None | Skip agent |
| A2A | Auth failure | No | None | Skip agent |

---

## 7. Integration Monitoring

### 7.1 Health Check Architecture

```mermaid
flowchart TB
    subgraph HealthCheck["Health Check System"]
        Scheduler["Health Scheduler"]
        Checker["Health Checker"]
        Aggregator["Status Aggregator"]
    end

    subgraph Targets["Check Targets"]
        LLMHealth["LLM Providers"]
        MCPHealth["MCP Servers"]
        A2AHealth["A2A Agents"]
    end

    subgraph Status["Health Status"]
        Healthy["✅ Healthy"]
        Degraded["⚠️ Degraded"]
        Unhealthy["❌ Unhealthy"]
    end

    Scheduler --> Checker
    Checker --> LLMHealth
    Checker --> MCPHealth
    Checker --> A2AHealth
    
    LLMHealth --> Aggregator
    MCPHealth --> Aggregator
    A2AHealth --> Aggregator
    
    Aggregator --> Healthy
    Aggregator --> Degraded
    Aggregator --> Unhealthy
```

### 7.2 Health Check Endpoints

| Integration | Health Check Method | Interval |
|-------------|---------------------|----------|
| LLM (OpenAI) | `GET /v1/models` | 60s |
| LLM (Anthropic) | Test completion | 60s |
| LLM (Ollama) | `GET /api/tags` | 30s |
| MCP (stdio) | Process alive check | 10s |
| MCP (HTTP) | `GET /health` or ping | 30s |
| A2A | Fetch Agent Card | 60s |

---

## 8. Integration Configuration

### 8.1 Connection Pool Settings

```yaml
integration:
  llm:
    connection_pool_size: 10
    keepalive_timeout: 30
    retry_attempts: 3
    retry_backoff_base: 1.0
    retry_backoff_max: 30.0

  mcp:
    stdio:
      process_restart_delay: 5
      max_restart_attempts: 3
    http:
      connection_pool_size: 5
      request_timeout: 30

  a2a:
    connection_pool_size: 10
    discovery_timeout: 15
    request_timeout: 40
    stream_timeout: 120
```

### 8.2 Circuit Breaker Settings

```yaml
circuit_breaker:
  enabled: true
  failure_threshold: 5
  success_threshold: 3
  timeout: 60
  half_open_requests: 1
```

---

## 9. Security Considerations

### 9.1 Integration Security Matrix

| Integration | Transport Security | Auth Storage | Data Sensitivity |
|-------------|-------------------|--------------|------------------|
| LLM APIs | TLS 1.2+ | Env vars | High (prompts) |
| MCP (stdio) | N/A (local) | N/A | Medium (tool data) |
| MCP (HTTP) | TLS 1.2+ | Env vars | Medium (tool data) |
| A2A | TLS 1.2+ | Env vars (future) | High (task data) |

### 9.2 Secret Management

```mermaid
flowchart LR
    subgraph Sources["Secret Sources"]
        EnvVars["Environment Variables"]
        SecretFile["Secret Files"]
        Vault["Vault (Future)"]
    end

    subgraph Load["Secret Loading"]
        Loader["Secret Loader"]
        Validate["Validate Presence"]
    end

    subgraph Use["Secret Usage"]
        LLMAuth["LLM Auth Headers"]
        A2AAuth["A2A Auth Headers"]
    end

    EnvVars --> Loader
    SecretFile --> Loader
    Vault --> Loader
    
    Loader --> Validate
    Validate --> LLMAuth
    Validate --> A2AAuth
```

---

## 10. Related Documents

- D07: Data Flow Architecture
- D09: Technology Stack
- D10-D24: Module Specifications
- D34-D42: Sequence Diagrams

---

## 11. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Architecture Team | Initial draft |
