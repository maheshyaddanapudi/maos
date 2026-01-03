# CLAUDE.md - Claude Code Implementation Guide

> This file provides Claude Code with the context and instructions needed to implement the Multi-Agent Orchestration System (MAOS) from the design documents.

---

## Project Overview

You are implementing a **config-driven multi-agent orchestration system** that combines:
- **LangGraph Supervisor** for intelligent routing
- **Any-Agent** for framework-agnostic worker execution
- **MCP** (Model Context Protocol) for tool integration
- **A2A** (Agent-to-Agent) for external agent communication

The complete design is in **68 documents** in the `docs/` directory with **56+ Mermaid diagrams**.

---

## Critical Documents to Read First

Before writing any code, read these documents in order:

1. **D01-executive-summary.md** - Project scope and goals
2. **D02-architecture-vision-and-goals.md** - Design principles
3. **D03-glossary-and-terminology.md** - Terminology definitions
4. **D06-component-overview-c4-l3.md** - Component architecture
5. **D07-data-flow-architecture.md** - How data flows through system
6. **D10-D24-module-specifications.md** - Module interfaces (CRITICAL)
7. **D53-directory-project-structure.md** - Project layout

---

## Implementation Order

Follow this exact order to build the system incrementally:

### Phase 1: Foundation (Week 1)

```
1. Project Setup
   ├── Create project structure (see D53)
   ├── Set up pyproject.toml with dependencies (see D54)
   ├── Create __init__.py files
   └── Set up logging (structlog)

2. Configuration (D10, D25-D28)
   ├── maos/config/models.py - Pydantic models for config
   ├── maos/config/loader.py - YAML/JSON loading
   ├── maos/config/schema.json - JSON Schema
   └── maos/config/validator.py - Validation logic

3. LLM Layer (D11)
   ├── maos/llm/base.py - LLMAdapter protocol
   ├── maos/llm/registry.py - LLMRegistry class
   ├── maos/llm/factory.py - LLMFactory class
   └── maos/llm/adapters/
       ├── openai.py
       ├── anthropic.py
       ├── google.py
       └── ollama.py
```

### Phase 2: Tools & Skills (Week 1-2)

```
4. MCP Integration (D12)
   ├── maos/mcp/registry.py - MCPRegistry
   ├── maos/mcp/connection.py - MCPConnection
   └── maos/mcp/transports/
       ├── base.py - MCPTransport protocol
       ├── stdio.py - StdioTransport
       └── http.py - HTTPTransport

5. Tool Management (D13)
   ├── maos/tools/models.py - Tool, ToolCall, ToolResult
   └── maos/tools/registry.py - ToolRegistry

6. Skills & Skillsets (D14-D15)
   ├── maos/skills/models.py - Skill, Skillset
   └── maos/skills/registry.py - SkillRegistry, SkillsetRegistry
```

### Phase 3: Agents (Week 2)

```
7. Agent Layer (D16)
   ├── maos/agents/models.py - Agent types
   ├── maos/agents/factory.py - AgentFactory (Any-Agent wrapper)
   └── maos/agents/registry.py - AgentRegistry

8. A2A Integration (D17)
   ├── maos/a2a/models.py - AgentCard, DiscoveredAgent
   ├── maos/a2a/discovery.py - A2ADiscovery
   └── maos/a2a/client.py - A2AClient
```

### Phase 4: Graph (Week 2-3)

```
9. Graph State (D45)
   └── maos/graph/state.py - GraphState TypedDict

10. Graph Nodes (D19-D21)
    └── maos/graph/nodes/
        ├── base.py - BaseNode
        ├── supervisor.py - SupervisorNode (with send_message tool)
        ├── worker.py - NativeWorkerNode
        └── external.py - ExternalAgentNode

11. Graph Factory (D18)
    └── maos/graph/factory.py - GraphFactory (builds LangGraph)
```

### Phase 5: API (Week 3)

```
12. API Server (D24, D29-D33)
    ├── maos/api/server.py - FastAPI app factory
    ├── maos/api/models.py - Request/Response models
    ├── maos/api/routes/
    │   ├── chat.py - /chat, /chat/resume endpoints
    │   ├── agents.py - /agents endpoint
    │   └── health.py - /health endpoint
    └── maos/api/streaming.py - SSE streaming helpers

13. Entry Point
    └── maos/main.py - CLI entry point
```

### Phase 6: Testing (Week 3-4)

```
14. Test Infrastructure (D66-D68)
    ├── tests/conftest.py - Fixtures
    ├── tests/mocks/ - Mock implementations
    ├── tests/unit/ - Unit tests
    ├── tests/integration/ - Integration tests
    └── tests/e2e/ - End-to-end tests
```

---

## Key Technical Decisions

### 1. Use Async Throughout

All I/O operations must be async:

```python
# Good
async def invoke_tool(self, tool_id: str, arguments: dict) -> ToolResult:
    tool = self._tools.get(tool_id)
    return await tool.execute(**arguments)

# Bad - blocks event loop
def invoke_tool(self, tool_id: str, arguments: dict) -> ToolResult:
    tool = self._tools.get(tool_id)
    return tool.execute(**arguments)  # Sync call!
```

### 2. Pydantic v2 for All Models

```python
from pydantic import BaseModel, Field
from typing import Optional, List

class ToolConfig(BaseModel):
    server: str = Field(..., description="MCP server name")
    tool_name: str = Field(..., description="Tool name on server")
    timeout_seconds: Optional[int] = Field(None, ge=1)
```

### 3. Protocol Classes for Interfaces

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class LLMAdapter(Protocol):
    async def invoke(self, messages: List[Message], tools: Optional[List[Tool]] = None) -> LLMResponse: ...
    async def stream(self, messages: List[Message], tools: Optional[List[Tool]] = None) -> AsyncIterator[LLMChunk]: ...
```

### 4. LangGraph State Management

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class GraphState(TypedDict):
    messages: Annotated[list, add_messages]
    next: str
    last_worker: Optional[str]
    last_result: Optional[WorkerResult]
    iteration_count: int
```

### 5. Any-Agent Integration

```python
from any_agent import AgentConfig, AnyAgent

# Create agent from config
agent = AnyAgent.create(
    framework=config.framework,  # "langchain", "openai", etc.
    model_id=llm_config.model,
    tools=tools,
    system_prompt=config.system_prompt
)

# Execute
result = await agent.run(task)
```

---

## Human-in-the-Loop Implementation

The `send_message` tool is CRITICAL for UI interaction:

### Supervisor Node with send_message

```python
# maos/graph/nodes/supervisor.py

from langgraph.types import interrupt

class SupervisorNode:
    def __init__(self, llm: LLMAdapter, roster: List[str]):
        self._llm = llm
        self._roster = roster
        self._tools = [self._create_send_message_tool()]
    
    def _create_send_message_tool(self) -> Tool:
        return Tool(
            name="send_message",
            description="Send a message to the user and wait for their response. Use when you need clarification or user input.",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message to send to the user"
                    }
                },
                "required": ["message"]
            }
        )
    
    async def run(self, state: GraphState) -> GraphState:
        # Build prompt with roster
        response = await self._llm.invoke(
            messages=state["messages"],
            tools=self._tools + self._routing_tools
        )
        
        # Check if supervisor wants to send a message
        if response.tool_calls:
            for tc in response.tool_calls:
                if tc.name == "send_message":
                    # INTERRUPT - this pauses the graph
                    user_response = interrupt({
                        "type": "input_required",
                        "prompt": tc.arguments["message"],
                        "thread_id": state.get("thread_id")
                    })
                    
                    # When resumed, user_response contains their input
                    return {
                        **state,
                        "messages": state["messages"] + [
                            {"role": "assistant", "content": tc.arguments["message"]},
                            {"role": "user", "content": user_response}
                        ]
                    }
        
        # Normal routing decision
        return self._parse_routing_decision(response, state)
```

### API Resume Endpoint

```python
# maos/api/routes/chat.py

@router.post("/chat/resume")
async def resume_chat(request: ResumeRequest, graph: CompiledGraph = Depends(get_graph)):
    """Resume a paused conversation with user input."""
    
    config = {"configurable": {"thread_id": request.thread_id}}
    
    # Resume the graph with the user's input
    result = await graph.ainvoke(
        Command(resume=request.input),
        config=config
    )
    
    return ChatResponse(
        thread_id=request.thread_id,
        messages=result["messages"],
        final_response=result["messages"][-1]["content"]
    )
```

### SSE Streaming with Interrupts

```python
# maos/api/streaming.py

async def stream_response(graph: CompiledGraph, request: ChatRequest):
    """Stream graph execution, handling interrupts."""
    
    config = {"configurable": {"thread_id": request.thread_id or str(uuid4())}}
    
    async for event in graph.astream_events(
        {"messages": request.messages},
        config=config,
        version="v2"
    ):
        if event["event"] == "on_chain_stream":
            chunk = event["data"]["chunk"]
            yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"
        
        elif event["event"] == "on_tool_start":
            yield f"event: tool_call\ndata: {json.dumps(event['data'])}\n\n"
        
        elif event["event"] == "on_tool_end":
            yield f"event: tool_result\ndata: {json.dumps(event['data'])}\n\n"
    
    # Check if graph is interrupted
    state = await graph.aget_state(config)
    if state.next:  # Graph is waiting
        # Get the interrupt value
        interrupt_value = state.tasks[0].interrupts[0].value if state.tasks else None
        if interrupt_value and interrupt_value.get("type") == "input_required":
            yield f"event: input_required\ndata: {json.dumps(interrupt_value)}\n\n"
            return
    
    yield f"event: done\ndata: {json.dumps({'thread_id': config['configurable']['thread_id']})}\n\n"
```

---

## File Templates

### Config Model Template

```python
# maos/config/models.py

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal
from enum import Enum

class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OLLAMA = "ollama"

class LLMConfig(BaseModel):
    provider: LLMProvider
    model: str
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None

class MCPServerConfig(BaseModel):
    transport: Literal["stdio", "http", "sse"] = "stdio"
    command: Optional[List[str]] = None
    url: Optional[str] = None
    timeout_seconds: int = Field(default=30, ge=1)

class ToolConfig(BaseModel):
    server: str
    tool_name: str
    timeout_seconds: Optional[int] = None

class SkillConfig(BaseModel):
    tools: List[str]
    description: str

class SkillsetConfig(BaseModel):
    skills: List[str]
    description: Optional[str] = None

class AgentKind(str, Enum):
    SUPERVISOR = "supervisor"
    NATIVE_WORKER = "native_worker"
    EXTERNAL = "external"

class AgentConfig(BaseModel):
    kind: AgentKind
    llm: str = "default"
    framework: Optional[str] = None
    skillset: Optional[str] = None
    system_prompt: str
    description: Optional[str] = None
    timeout_seconds: int = 60
    tools: Optional[List[str]] = None

class GraphConfig(BaseModel):
    max_iterations: int = Field(default=10, ge=1)
    
    class Timeouts(BaseModel):
        worker_seconds: int = 60
        tool_call_seconds: int = 30
    
    timeouts: Timeouts = Timeouts()

class ServingConfig(BaseModel):
    class APIConfig(BaseModel):
        host: str = "0.0.0.0"
        port: int = 7777
        cors_origins: List[str] = ["*"]
    
    api: APIConfig = APIConfig()

class A2AConfig(BaseModel):
    class DiscoveryConfig(BaseModel):
        seeds: List[str] = []
        host_index_path: str = "/a2a/index.json"
        well_known_paths: List[str] = ["/.well-known/agent.json"]
        timeout_seconds: int = 10
    
    class ImportPolicy(BaseModel):
        enabled: bool = True
        mode: Literal["langgraph_nodes", "tools_only"] = "langgraph_nodes"
        prefix: str = "ext::"
        include_tags: List[str] = []
        exclude_names: List[str] = []
        max_agents: int = 50
    
    discovery: DiscoveryConfig = DiscoveryConfig()
    import_policy: ImportPolicy = ImportPolicy()

class Config(BaseModel):
    """Root configuration model."""
    llms: Dict[str, LLMConfig]
    mcp_servers: Dict[str, MCPServerConfig] = {}
    tools: Dict[str, ToolConfig] = {}
    skills: Dict[str, SkillConfig] = {}
    skillsets: Dict[str, SkillsetConfig] = {}
    agents: Dict[str, AgentConfig]
    graph: GraphConfig = GraphConfig()
    serving: ServingConfig = ServingConfig()
    a2a: A2AConfig = A2AConfig()
```

### Registry Template

```python
# maos/llm/registry.py

from typing import Dict, Optional
from maos.config.models import LLMConfig
from maos.llm.base import LLMAdapter
from maos.llm.factory import LLMFactory

class LLMRegistry:
    """Registry for LLM adapters."""
    
    def __init__(self):
        self._adapters: Dict[str, LLMAdapter] = {}
        self._factory = LLMFactory()
    
    def register(self, name: str, config: LLMConfig) -> None:
        """Register an LLM adapter from config."""
        adapter = self._factory.create(config)
        self._adapters[name] = adapter
    
    def get(self, name: str) -> Optional[LLMAdapter]:
        """Get an LLM adapter by name."""
        return self._adapters.get(name)
    
    def get_or_default(self, name: Optional[str]) -> LLMAdapter:
        """Get adapter by name, falling back to 'default'."""
        if name and name in self._adapters:
            return self._adapters[name]
        if "default" in self._adapters:
            return self._adapters["default"]
        raise ValueError("No LLM adapter found and no default configured")
    
    def list(self) -> List[str]:
        """List all registered adapter names."""
        return list(self._adapters.keys())
```

---

## Testing Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=maos --cov-report=html

# Run specific test file
pytest tests/unit/test_config.py

# Run tests matching pattern
pytest -k "test_supervisor"

# Run with verbose output
pytest -v -s
```

---

## Common Pitfalls to Avoid

1. **Don't block the event loop** - Use `async/await` for all I/O
2. **Don't hardcode paths** - Use config values
3. **Don't skip validation** - Validate all inputs with Pydantic
4. **Don't forget error handling** - Wrap external calls in try/except
5. **Don't mutate state** - Return new state dicts from graph nodes
6. **Don't forget thread safety** - Registries may be accessed concurrently

---

## When Stuck

1. Check the relevant document in `docs/`
2. Look at the Mermaid diagrams for flow understanding
3. Review the module interface in D10-D24
4. Check the test cases in D67 for expected behavior

---

## Success Criteria

The implementation is complete when:

1. ✅ All unit tests pass
2. ✅ Integration tests pass
3. ✅ E2E chat flow works
4. ✅ Streaming works
5. ✅ Human-in-the-loop works
6. ✅ MCP tools can be called
7. ✅ A2A agents can be discovered and used
8. ✅ Config-only agent addition works (no code changes)

---

**Remember: The documentation is the source of truth. When in doubt, refer to the docs.**
