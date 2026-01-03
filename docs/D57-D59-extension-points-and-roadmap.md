# D57-D59: Extension Points & Future Roadmap

## Config-Driven Multi-Agent Orchestration System

**Document ID:** D57-D59  
**Version:** 1.0  
**Status:** Draft  
**Last Updated:** January 2026

---

## Document Index

| Doc ID | Document | Description |
|--------|----------|-------------|
| D57 | Security Extension Points | Where auth/RBAC/tenancy will plug in |
| D58 | Extensibility Guide | How to add frameworks, transports, providers |
| D59 | Roadmap Placeholder | Future phases and priorities |

---

# D57: Security Extension Points

## Overview

While security is out of scope for the prototype, the architecture includes explicit extension points for future authentication, authorization, and multi-tenancy.

---

## 1. Authentication Extension Points

### 1.1 API Layer Authentication

**Location:** `maos/api/middleware/auth.py`

```python
class AuthMiddleware:
    """
    Placeholder for authentication middleware.
    
    Future implementation will:
    - Validate JWT tokens
    - Extract user identity
    - Attach user context to request
    """
    
    async def __call__(self, request: Request, call_next):
        # EXTENSION POINT: Add token validation here
        return await call_next(request)
```

**Config Extension:**
```yaml
security:
  api:
    auth_enabled: true
    auth_provider: jwt  # jwt, oauth2, api_key
    jwt:
      secret_env: JWT_SECRET
      algorithm: HS256
```

### 1.2 A2A Client Authentication

**Location:** `maos/a2a/client.py`

```python
class A2AClient:
    async def _build_headers(self, agent: DiscoveredAgent) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        # EXTENSION POINT: Add auth headers from Agent Card
        return headers
```

### 1.3 MCP Server Authentication

**Location:** `maos/mcp/transports/http.py`

```python
class HTTPTransport:
    async def _build_request(self, message: dict) -> httpx.Request:
        headers = {}
        # EXTENSION POINT: Add MCP server auth
        return httpx.Request("POST", self._url, json=message, headers=headers)
```

---

## 2. Authorization Extension Points

### 2.1 Tool Access Control

**Location:** `maos/tools/registry.py`

```python
class ToolRegistry:
    def get(self, tool_id: str, context: Optional[AuthContext] = None) -> Optional[Tool]:
        tool = self._tools.get(tool_id)
        # EXTENSION POINT: Check tool access permissions
        return tool
```

### 2.2 Agent Access Control

**Location:** `maos/agents/registry.py`

```python
class AgentRegistry:
    def get_available_agents(self, context: Optional[AuthContext] = None) -> List[Agent]:
        agents = list(self._agents.values())
        # EXTENSION POINT: Filter agents by permission
        return agents
```

---

## 3. Multi-Tenancy Extension Points

### 3.1 Tenant Context

**Location:** `maos/core/context.py`

```python
@dataclass
class TenantContext:
    """Tenant context for multi-tenancy support."""
    tenant_id: str
    config_override: Optional[Dict] = None
    resource_limits: Optional[ResourceLimits] = None
```

### 3.2 Tenant Isolation Points

| Component | Isolation Strategy |
|-----------|-------------------|
| Config | Tenant-specific config overrides |
| LLM Registry | Per-tenant API keys, rate limits |
| MCP Registry | Tenant-scoped server access |
| Agent Registry | Tenant-specific agent pools |
| Logging | Tenant ID in all log entries |

---

## 4. Audit Logging Extension Points

**Location:** `maos/core/audit.py`

```python
class AuditLogger:
    async def log_event(self, event: AuditEvent) -> None:
        # EXTENSION POINT: Send to audit system
        pass

@dataclass
class AuditEvent:
    timestamp: datetime
    event_type: str
    user_id: Optional[str]
    tenant_id: Optional[str]
    resource: str
    action: str
    outcome: str
    details: Dict[str, Any]
```

---

# D58: Extensibility Guide

## Overview

This guide explains how to extend the system with new capabilities.

---

## 1. Adding a New LLM Provider

### Step 1: Create Adapter

```python
# maos/llm/adapters/newprovider.py

class NewProviderAdapter(LLMAdapter):
    def __init__(self, config: LLMConfig):
        self._client = NewProviderClient(api_key=os.getenv(config.api_key_env))
        self._model = config.model
    
    async def invoke(self, messages, tools=None) -> LLMResponse:
        # Implementation
        pass
    
    async def stream(self, messages, tools=None) -> AsyncIterator[LLMChunk]:
        # Implementation
        pass
```

### Step 2: Register Adapter

```python
# maos/llm/factory.py
PROVIDER_ADAPTERS = {
    "openai": OpenAIAdapter,
    "newprovider": NewProviderAdapter,  # Add here
}
```

### Step 3: Use in Config

```yaml
llms:
  my_llm:
    provider: newprovider
    model: newprovider-large
    api_key_env: NEWPROVIDER_API_KEY
```

---

## 2. Adding a New MCP Transport

### Step 1: Implement Transport

```python
# maos/mcp/transports/websocket.py

class WebSocketTransport(MCPTransport):
    async def connect(self) -> None:
        self._ws = await websockets.connect(self._url)
    
    async def send(self, message: dict) -> dict:
        await self._ws.send(json.dumps(message))
        return json.loads(await self._ws.recv())
```

### Step 2: Register Transport

```python
# maos/mcp/registry.py
TRANSPORTS = {
    "stdio": StdioTransport,
    "http": HTTPTransport,
    "websocket": WebSocketTransport,  # Add here
}
```

---

## 3. Adding Custom Tools (Without MCP)

```python
# maos/tools/custom/my_tool.py

class MyCustomTool(CustomTool):
    name = "my_custom_tool"
    description = "Does something custom"
    
    input_schema = {
        "type": "object",
        "properties": {"param1": {"type": "string"}},
        "required": ["param1"]
    }
    
    async def execute(self, param1: str) -> str:
        return await self._do_something(param1)
```

---

## 4. Adding Custom Graph Nodes

```python
# maos/graph/nodes/custom_node.py

class CustomProcessingNode(BaseNode):
    async def run(self, state: GraphState) -> GraphState:
        processed = await self._process(state.last_result)
        return {**state, "last_result": processed}
```

---

# D59: Roadmap Placeholder

## Phase 1: Prototype (Current)

**Timeline:** Weeks 1-5

- [x] Architecture design and documentation
- [ ] Core orchestration with LangGraph Supervisor
- [ ] Native workers via Any-Agent
- [ ] MCP tool integration
- [ ] A2A external agent discovery
- [ ] REST API with streaming

---

## Phase 2: Hardening

**Timeline:** Weeks 6-10

- [ ] Authentication middleware (JWT/OAuth2)
- [ ] Basic authorization (role-based)
- [ ] Persistent conversation state
- [ ] Improved error handling
- [ ] Comprehensive test suite

---

## Phase 3: Scale

**Timeline:** Weeks 11-16

- [ ] Multi-tenancy support
- [ ] Horizontal scaling architecture
- [ ] Distributed state management
- [ ] Advanced observability
- [ ] Admin dashboard

---

## Phase 4: Enterprise

**Timeline:** Weeks 17-24

- [ ] Full RBAC with fine-grained permissions
- [ ] Audit logging and compliance
- [ ] SSO integration (SAML, OIDC)
- [ ] Data encryption at rest
- [ ] Disaster recovery

---

## Feature Roadmap Visualization

```
        Prototype     Hardening      Scale        Enterprise
        (Wks 1-5)    (Wks 6-10)   (Wks 11-16)   (Wks 17-24)
            │             │            │             │
Core        ████████████──┤            │             │
Auth        │             ████████─────┤             │
Multi-tenant│             │            █████████────┤
Scale       │             │            ████████████─┤
Enterprise  │             │            │             ████████████
```

---

## Technical Debt Backlog

| Item | Phase | Effort |
|------|-------|--------|
| Comprehensive input validation | Phase 2 | Low |
| Request tracing | Phase 2 | Medium |
| MCP connection pooling | Phase 3 | Medium |
| LLM response caching | Phase 3 | High |
| Config hot reload | Phase 3 | High |

---

## Related Documents

- D01: Executive Summary
- D02: Architecture Vision
- D51-D56: Setup and Operations

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Architecture Team | Initial draft |
