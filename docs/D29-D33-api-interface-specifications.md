# D29-D33: API & Interface Specifications

## Config-Driven Multi-Agent Orchestration System

**Document ID:** D29-D33  
**Version:** 1.0  
**Status:** Draft  
**Last Updated:** January 2026

---

## Document Index

| Doc ID | Specification | Description |
|--------|---------------|-------------|
| D29 | REST API Specification | OpenAPI spec for all endpoints |
| D30 | WebSocket/SSE Streaming | Streaming protocol details |
| D31 | A2A Host Index Endpoint | Host index JSON structure |
| D32 | Agent Card Schema | Required/optional fields |
| D33 | Internal Message Contracts | State schema, worker results |

---

## D29: REST API Specification (OpenAPI)

### OpenAPI 3.0 Specification

```yaml
openapi: 3.0.3
info:
  title: Multi-Agent Orchestration API
  description: API for the config-driven multi-agent orchestration system
  version: 1.0.0

servers:
  - url: http://localhost:7777
    description: Local development server

paths:
  /chat:
    post:
      summary: Send chat message
      description: Send a message to the multi-agent system
      operationId: chat
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ChatRequest'
      responses:
        '200':
          description: Successful response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ChatResponse'
            text/event-stream:
              schema:
                type: string
                description: SSE stream when stream=true
        '400':
          $ref: '#/components/responses/BadRequest'
        '500':
          $ref: '#/components/responses/InternalError'

  /agents:
    get:
      summary: List available agents
      description: Get list of native workers and external agents
      operationId: listAgents
      responses:
        '200':
          description: List of agents
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AgentsResponse'

  /health:
    get:
      summary: Health check
      description: Check system health status
      operationId: healthCheck
      responses:
        '200':
          description: System healthy
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HealthResponse'

  /v1/chat/completions:
    post:
      summary: OpenAI-compatible chat
      description: OpenAI API compatible endpoint for tools like Open WebUI
      operationId: openaiChat
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/OpenAIChatRequest'
      responses:
        '200':
          description: Chat completion response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OpenAIChatResponse'
            text/event-stream:
              schema:
                type: string

components:
  schemas:
    ChatRequest:
      type: object
      required:
        - messages
      properties:
        messages:
          type: array
          items:
            $ref: '#/components/schemas/Message'
          minItems: 1
        stream:
          type: boolean
          default: false
        context:
          type: object
          additionalProperties: true

    ChatResponse:
      type: object
      properties:
        id:
          type: string
        messages:
          type: array
          items:
            $ref: '#/components/schemas/Message'
        final_response:
          type: string
        metadata:
          type: object
          properties:
            total_tokens:
              type: integer
            duration_ms:
              type: integer
            workers_used:
              type: array
              items:
                type: string

    Message:
      type: object
      required:
        - role
        - content
      properties:
        role:
          type: string
          enum: [user, assistant, system, tool]
        content:
          type: string
        name:
          type: string
        tool_calls:
          type: array
          items:
            $ref: '#/components/schemas/ToolCall'
        tool_call_id:
          type: string

    ToolCall:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
        arguments:
          type: object

    AgentsResponse:
      type: object
      properties:
        native_workers:
          type: array
          items:
            $ref: '#/components/schemas/AgentInfo'
        external_agents:
          type: array
          items:
            $ref: '#/components/schemas/AgentInfo'

    AgentInfo:
      type: object
      properties:
        name:
          type: string
        description:
          type: string
        skills:
          type: array
          items:
            type: string
        framework:
          type: string
        status:
          type: string
          enum: [active, inactive, error]

    HealthResponse:
      type: object
      properties:
        status:
          type: string
          enum: [healthy, degraded, unhealthy]
        version:
          type: string
        uptime_seconds:
          type: integer
        components:
          type: object
          additionalProperties:
            type: object
            properties:
              status:
                type: string
              message:
                type: string

    OpenAIChatRequest:
      type: object
      required:
        - model
        - messages
      properties:
        model:
          type: string
        messages:
          type: array
          items:
            type: object
            properties:
              role:
                type: string
              content:
                type: string
        stream:
          type: boolean
          default: false
        temperature:
          type: number
        max_tokens:
          type: integer

    OpenAIChatResponse:
      type: object
      properties:
        id:
          type: string
        object:
          type: string
          default: chat.completion
        created:
          type: integer
        model:
          type: string
        choices:
          type: array
          items:
            type: object
            properties:
              index:
                type: integer
              message:
                type: object
                properties:
                  role:
                    type: string
                  content:
                    type: string
              finish_reason:
                type: string
        usage:
          type: object
          properties:
            prompt_tokens:
              type: integer
            completion_tokens:
              type: integer
            total_tokens:
              type: integer

    Error:
      type: object
      properties:
        error:
          type: object
          properties:
            code:
              type: string
            message:
              type: string
            details:
              type: object

  responses:
    BadRequest:
      description: Bad request
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'

    InternalError:
      description: Internal server error
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Error'
```

---

## D30: WebSocket/SSE Streaming Specification

### SSE (Server-Sent Events) Protocol

#### Connection
```
POST /chat
Content-Type: application/json
Accept: text/event-stream

{"messages": [...], "stream": true}
```

#### Event Types

| Event | Description | Data Format |
|-------|-------------|-------------|
| `chunk` | Token chunk | `{"type": "chunk", "content": "...", "done": false}` |
| `tool_call` | Tool invocation | `{"type": "tool_call", "tool": "...", "args": {...}}` |
| `tool_result` | Tool result | `{"type": "tool_result", "tool": "...", "result": ...}` |
| `routing` | Supervisor routing | `{"type": "routing", "from": "...", "to": "..."}` |
| `done` | Stream complete | `{"type": "done", "metadata": {...}}` |
| `error` | Error occurred | `{"type": "error", "code": "...", "message": "..."}` |

#### Example Stream

```
data: {"type": "routing", "from": "supervisor", "to": "research_agent"}

data: {"type": "tool_call", "tool": "search_web", "args": {"query": "AI trends"}}

data: {"type": "tool_result", "tool": "search_web", "result": "..."}

data: {"type": "chunk", "content": "Based on", "done": false}

data: {"type": "chunk", "content": " my research,", "done": false}

data: {"type": "chunk", "content": " here are", "done": false}

data: {"type": "done", "metadata": {"tokens": 150, "duration_ms": 3500}}

```

### WebSocket Protocol (Optional)

#### Connection
```
WS /ws/chat
```

#### Message Format

```json
// Client -> Server
{
  "type": "message",
  "id": "msg-123",
  "data": {
    "messages": [...],
    "stream": true
  }
}

// Server -> Client
{
  "type": "chunk",
  "id": "msg-123",
  "data": {
    "content": "...",
    "done": false
  }
}
```

---

## D31: A2A Host Index Endpoint Specification

### Endpoint
```
GET /a2a/index.json
```

### Response Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["version", "agents"],
  "properties": {
    "version": {
      "type": "string",
      "description": "Host index schema version",
      "example": "1.0"
    },
    "host": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string",
          "description": "Host display name"
        },
        "description": {
          "type": "string",
          "description": "Host description"
        },
        "base_url": {
          "type": "string",
          "format": "uri",
          "description": "Base URL for agent endpoints"
        }
      }
    },
    "agents": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "path"],
        "properties": {
          "name": {
            "type": "string",
            "description": "Agent identifier"
          },
          "path": {
            "type": "string",
            "description": "Relative path to agent endpoint"
          },
          "agent_card_path": {
            "type": "string",
            "description": "Relative path to Agent Card"
          },
          "description": {
            "type": "string",
            "description": "Brief agent description"
          },
          "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Tags for filtering"
          }
        }
      }
    }
  }
}
```

### Example Response

```json
{
  "version": "1.0",
  "host": {
    "name": "Analytics Agent Host",
    "description": "Hosts specialized analytics and ML agents",
    "base_url": "http://localhost:9001"
  },
  "agents": [
    {
      "name": "data-analyzer",
      "path": "/a2a/data-analyzer",
      "agent_card_path": "/a2a/data-analyzer/.well-known/agent.json",
      "description": "Analyzes structured data",
      "tags": ["analytics", "data", "internal"]
    },
    {
      "name": "ml-predictor",
      "path": "/a2a/ml-predictor",
      "agent_card_path": "/a2a/ml-predictor/.well-known/agent.json",
      "description": "ML predictions and forecasting",
      "tags": ["ml", "prediction", "internal"]
    }
  ]
}
```

---

## D32: Agent Card Schema Reference

### Full Agent Card Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["name", "version"],
  "properties": {
    "protocolVersion": {
      "type": "string",
      "default": "1.0",
      "description": "A2A protocol version"
    },
    "name": {
      "type": "string",
      "description": "Agent name (used as identifier)"
    },
    "description": {
      "type": "string",
      "description": "Human-readable description"
    },
    "version": {
      "type": "string",
      "description": "Agent version"
    },
    "supportedInterfaces": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "url": {
            "type": "string",
            "format": "uri"
          },
          "protocolBinding": {
            "type": "string",
            "enum": ["JSONRPC", "HTTP"],
            "default": "JSONRPC"
          }
        }
      }
    },
    "capabilities": {
      "type": "object",
      "properties": {
        "streaming": {"type": "boolean", "default": false},
        "pushNotifications": {"type": "boolean", "default": false},
        "stateTransitionHistory": {"type": "boolean", "default": false}
      }
    },
    "defaultInputModes": {
      "type": "array",
      "items": {"type": "string"},
      "default": ["text/plain"]
    },
    "defaultOutputModes": {
      "type": "array",
      "items": {"type": "string"},
      "default": ["text/plain"]
    },
    "skills": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "name"],
        "properties": {
          "id": {"type": "string"},
          "name": {"type": "string"},
          "description": {"type": "string"},
          "tags": {
            "type": "array",
            "items": {"type": "string"}
          },
          "examples": {
            "type": "array",
            "items": {"type": "string"}
          }
        }
      }
    },
    "securitySchemes": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "type": {"type": "string"},
          "scheme": {"type": "string"},
          "bearerFormat": {"type": "string"}
        }
      }
    }
  }
}
```

### Minimal Agent Card Example

```json
{
  "name": "simple-agent",
  "version": "1.0.0",
  "description": "A simple A2A agent"
}
```

### Full Agent Card Example

```json
{
  "protocolVersion": "1.0",
  "name": "data-analysis-agent",
  "description": "Specialized agent for data analysis and visualization",
  "version": "2.1.0",
  "supportedInterfaces": [
    {
      "url": "http://localhost:9010/a2a",
      "protocolBinding": "JSONRPC"
    }
  ],
  "capabilities": {
    "streaming": true,
    "pushNotifications": false,
    "stateTransitionHistory": true
  },
  "defaultInputModes": ["text/plain", "application/json"],
  "defaultOutputModes": ["text/plain", "application/json", "image/png"],
  "skills": [
    {
      "id": "analyze-csv",
      "name": "CSV Analysis",
      "description": "Analyze CSV files and generate insights",
      "tags": ["data", "analysis", "csv"],
      "examples": [
        "Analyze this CSV for trends",
        "Find correlations in the data"
      ]
    },
    {
      "id": "create-chart",
      "name": "Chart Creation",
      "description": "Create visualizations from data",
      "tags": ["visualization", "charts"],
      "examples": [
        "Create a bar chart of sales by region",
        "Plot the time series data"
      ]
    }
  ],
  "securitySchemes": {
    "bearerAuth": {
      "type": "http",
      "scheme": "bearer",
      "bearerFormat": "JWT"
    }
  }
}
```

---

## D33: Internal Message Contracts

### Graph State Contract

```python
@dataclass
class GraphStateContract:
    """Contract for LangGraph state."""
    
    # Required fields
    messages: List[Message]  # Conversation history
    
    # Routing fields
    next: Optional[str]  # Next node or "END"
    done: bool  # Completion flag
    iteration: int  # Loop counter
    
    # Context fields
    task: str  # Normalized task description
    context: Dict[str, Any]  # Additional context
    roster: List[str]  # Available workers
    
    # Result fields
    last_result: Optional[WorkerResult]  # Last worker output
    
    # Metadata
    metadata: Dict[str, Any]  # Execution metadata
```

### Worker Input Contract

```python
@dataclass
class WorkerInputContract:
    """Contract for input to worker nodes."""
    
    # From supervisor
    task: str  # What to do
    context: Dict[str, Any]  # Additional context
    
    # From state
    messages: List[Message]  # Conversation for context
    
    # Configuration
    timeout: int  # Execution timeout
    stream: bool  # Whether to stream response
```

### Worker Output Contract

```python
@dataclass
class WorkerOutputContract:
    """Contract for output from worker nodes."""
    
    # Identification
    from_agent: str  # Worker name
    
    # Result
    output: ResultOutput
    # - type: "text" | "error" | "partial" | "structured"
    # - content: str
    # - sources: List[str]
    # - tool_calls: List[ToolCallRecord]
    
    # Metadata
    metadata: ResultMetadata
    # - tokens_used: int
    # - duration_ms: int
    # - tools_invoked: List[str]
    # - model_used: str
```

### Supervisor Decision Contract

```python
@dataclass
class SupervisorDecisionContract:
    """Contract for supervisor routing decisions."""
    
    # Decision
    next: str  # Worker name, "ext::name", or "END"
    
    # Reasoning (for debugging)
    reasoning: str  # Why this decision
    
    # Optional message
    message: Optional[str]  # Message to include in state
    
    # Human-in-the-loop
    await_input: bool  # Whether waiting for user
    clarification_request: Optional[str]  # What to ask user
```

### A2A Message Contract

```python
@dataclass
class A2AMessageContract:
    """Contract for A2A communication."""
    
    # Request
    method: str  # "message/send" | "message/stream" | "tasks/get"
    task_content: str  # Task description
    timeout: int  # Request timeout
    stream: bool  # Whether to stream
    
    # Response
    task_id: str  # A2A task ID
    status: TaskStatus  # SUBMITTED, WORKING, COMPLETED, etc.
    result_content: Optional[str]  # Result text
    error: Optional[str]  # Error if failed
```

### Error Contract

```python
@dataclass
class ErrorContract:
    """Contract for error responses."""
    
    # Classification
    code: str  # Error code
    category: str  # "validation", "execution", "timeout", "external"
    
    # Details
    message: str  # Human-readable message
    source: Optional[str]  # Component that failed
    
    # Recovery
    retryable: bool  # Can be retried
    retry_after: Optional[int]  # Seconds to wait
    
    # Debug
    details: Dict[str, Any]  # Additional debug info
    stack_trace: Optional[str]  # For internal errors
```

### Error Codes

| Code | Category | Description |
|------|----------|-------------|
| `VALIDATION_ERROR` | validation | Request validation failed |
| `CONFIG_ERROR` | validation | Configuration invalid |
| `LLM_ERROR` | execution | LLM provider error |
| `TOOL_ERROR` | execution | MCP tool execution failed |
| `A2A_ERROR` | external | External agent error |
| `TIMEOUT_ERROR` | timeout | Operation timed out |
| `MAX_ITERATIONS` | execution | Supervisor loop limit |
| `INTERNAL_ERROR` | execution | Unexpected internal error |

---

## Related Documents

- D24: APIServer Module
- D45-D50: Data Models
- D51: Local Development Setup

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Architecture Team | Initial draft |
