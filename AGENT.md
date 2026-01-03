# AGENT.md - AI Coding Agent Implementation Guide

> Instructions for Cursor, GitHub Copilot, Cody, and other AI coding assistants to implement the Multi-Agent Orchestration System (MAOS).

---

## Quick Context

This project implements a **config-driven multi-agent orchestration system**:

- **LangGraph** - Supervisor routing pattern for orchestration
- **Any-Agent** - Framework-agnostic agent runtime
- **MCP** - Model Context Protocol for tools
- **A2A** - Agent-to-Agent protocol for external agents
- **FastAPI** - REST API with SSE streaming

**68 design documents** are in `docs/`. Read them for specifications.

---

## Project Structure

```
maos/
├── maos/                    # Main Python package
│   ├── config/             # Configuration loading & validation
│   ├── llm/                # LLM provider adapters
│   ├── mcp/                # MCP tool integration
│   ├── tools/              # Tool registry
│   ├── skills/             # Skill/Skillset management
│   ├── agents/             # Agent factory & registry
│   ├── a2a/                # A2A discovery & client
│   ├── graph/              # LangGraph orchestration
│   │   └── nodes/          # Graph nodes (supervisor, worker, external)
│   └── api/                # FastAPI server
│       └── routes/         # API route handlers
├── tests/                  # Test suite
├── docs/                   # Design documents (68 files)
├── config/                 # Example configurations
└── mcp-servers/            # Example MCP tool servers
```

---

## Key Dependencies

```python
# Core
langgraph = "^0.2"
any-agent = {version = "^0.1", extras = ["langchain", "openai"]}
fastapi = "^0.115"
uvicorn = "^0.32"
pydantic = "^2.9"
httpx = "^0.27"

# MCP
mcp = "^1.0"

# LLM Providers
openai = "^1.50"
anthropic = "^0.39"
google-generativeai = "^0.8"

# Utils
structlog = "^24.4"
pyyaml = "^6.0"
```

---

## Implementation Tasks

### Task 1: Configuration System

**Files to create:**
- `maos/config/models.py` - Pydantic config models
- `maos/config/loader.py` - YAML/JSON loader
- `maos/config/validator.py` - Validation logic

**Reference:** `docs/D10-D24-module-specifications.md` (D10 section)

**Key interfaces:**
```python
class ConfigLoader:
    def load(self, path: str) -> Config: ...
    def load_from_string(self, content: str) -> Config: ...
    def validate(self, config: Config) -> List[ValidationError]: ...
```

---

### Task 2: LLM Registry

**Files to create:**
- `maos/llm/base.py` - LLMAdapter protocol
- `maos/llm/factory.py` - Adapter factory
- `maos/llm/registry.py` - Registry
- `maos/llm/adapters/{openai,anthropic,google,ollama}.py`

**Reference:** `docs/D10-D24-module-specifications.md` (D11 section)

**Key interfaces:**
```python
class LLMAdapter(Protocol):
    async def invoke(self, messages: List[Message], tools: Optional[List[Tool]] = None) -> LLMResponse: ...
    async def stream(self, messages: List[Message], tools: Optional[List[Tool]] = None) -> AsyncIterator[LLMChunk]: ...

class LLMRegistry:
    def register(self, name: str, config: LLMConfig) -> None: ...
    def get(self, name: str) -> Optional[LLMAdapter]: ...
```

---

### Task 3: MCP Integration

**Files to create:**
- `maos/mcp/registry.py` - MCPRegistry
- `maos/mcp/connection.py` - MCPConnection
- `maos/mcp/transports/base.py` - Transport protocol
- `maos/mcp/transports/stdio.py` - Stdio transport
- `maos/mcp/transports/http.py` - HTTP transport

**Reference:** `docs/D10-D24-module-specifications.md` (D12 section)

**Key pattern:**
```python
class MCPRegistry:
    async def connect(self, name: str, config: MCPServerConfig) -> MCPConnection: ...
    async def disconnect(self, name: str) -> None: ...
    async def get_tools(self, name: str) -> List[ToolDefinition]: ...
```

---

### Task 4: Tool/Skill System

**Files to create:**
- `maos/tools/models.py` - Tool, ToolCall, ToolResult
- `maos/tools/registry.py` - ToolRegistry
- `maos/skills/models.py` - Skill, Skillset
- `maos/skills/registry.py` - SkillRegistry, SkillsetRegistry

**Reference:** `docs/D10-D24-module-specifications.md` (D13-D15 sections)

---

### Task 5: Agent Layer

**Files to create:**
- `maos/agents/models.py` - Agent type definitions
- `maos/agents/factory.py` - AgentFactory (wraps Any-Agent)
- `maos/agents/registry.py` - AgentRegistry

**Reference:** `docs/D10-D24-module-specifications.md` (D16 section)

**Any-Agent usage:**
```python
from any_agent import AnyAgent

agent = AnyAgent.create(
    framework=config.framework,  # "langchain", "openai", etc.
    model_id=llm_config.model,
    tools=materialized_tools,
    system_prompt=config.system_prompt
)
result = await agent.run(task)
```

---

### Task 6: A2A Discovery

**Files to create:**
- `maos/a2a/models.py` - AgentCard, DiscoveredAgent
- `maos/a2a/discovery.py` - A2ADiscovery
- `maos/a2a/client.py` - A2AClient

**Reference:** `docs/D10-D24-module-specifications.md` (D17 section)

---

### Task 7: LangGraph Orchestration

**Files to create:**
- `maos/graph/state.py` - GraphState TypedDict
- `maos/graph/factory.py` - GraphFactory
- `maos/graph/nodes/base.py` - BaseNode
- `maos/graph/nodes/supervisor.py` - SupervisorNode
- `maos/graph/nodes/worker.py` - NativeWorkerNode
- `maos/graph/nodes/external.py` - ExternalAgentNode

**Reference:** `docs/D10-D24-module-specifications.md` (D18-D21 sections)

**Critical: Supervisor with send_message tool:**
```python
from langgraph.types import interrupt

class SupervisorNode:
    async def run(self, state: GraphState) -> GraphState:
        response = await self._llm.invoke(state["messages"], self._tools)
        
        for tool_call in response.tool_calls or []:
            if tool_call.name == "send_message":
                # PAUSE graph, wait for user input
                user_input = interrupt({
                    "type": "input_required",
                    "prompt": tool_call.arguments["message"]
                })
                # Resume with user's response
                return {
                    **state,
                    "messages": state["messages"] + [
                        {"role": "assistant", "content": tool_call.arguments["message"]},
                        {"role": "user", "content": user_input}
                    ]
                }
        
        # Normal routing
        return self._route(response, state)
```

---

### Task 8: API Server

**Files to create:**
- `maos/api/server.py` - FastAPI app factory
- `maos/api/models.py` - Request/Response Pydantic models
- `maos/api/routes/chat.py` - `/chat`, `/chat/resume`
- `maos/api/routes/agents.py` - `/agents`
- `maos/api/routes/health.py` - `/health`
- `maos/api/streaming.py` - SSE helpers

**Reference:** `docs/D29-D33-api-interface-specifications.md`

**Critical: Resume endpoint for human-in-the-loop:**
```python
@router.post("/chat/resume")
async def resume_chat(request: ResumeRequest):
    """Resume paused conversation with user input."""
    config = {"configurable": {"thread_id": request.thread_id}}
    result = await graph.ainvoke(Command(resume=request.input), config)
    return ChatResponse(...)
```

**SSE events to emit:**
- `chunk` - Text content
- `tool_call` - Tool invocation started
- `tool_result` - Tool completed
- `routing` - Agent routing decision
- `input_required` - Human input needed (HITL)
- `done` - Stream complete
- `error` - Error occurred

---

### Task 9: Entry Point

**Files to create:**
- `maos/main.py` - CLI entry point
- `maos/__init__.py` - Package init

```python
# maos/main.py
import asyncio
import argparse
from maos.config.loader import ConfigLoader
from maos.api.server import create_app

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    
    config = ConfigLoader().load(args.config)
    app = await create_app(config)
    
    import uvicorn
    uvicorn.run(app, host=config.serving.api.host, port=config.serving.api.port)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Code Patterns to Follow

### 1. Async Everything

```python
# ✅ Good
async def fetch_agent_card(url: str) -> AgentCard:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{url}/.well-known/agent.json")
        return AgentCard.model_validate(response.json())

# ❌ Bad
def fetch_agent_card(url: str) -> AgentCard:
    response = requests.get(f"{url}/.well-known/agent.json")  # Blocks!
    return AgentCard.model_validate(response.json())
```

### 2. Pydantic Models

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class ToolCall(BaseModel):
    id: str = Field(..., description="Unique call ID")
    name: str = Field(..., description="Tool name")
    arguments: dict = Field(default_factory=dict)

class LLMResponse(BaseModel):
    content: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    usage: dict = Field(default_factory=dict)
```

### 3. Protocol Classes

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class MCPTransport(Protocol):
    async def connect(self) -> None: ...
    async def send(self, message: dict) -> dict: ...
    async def disconnect(self) -> None: ...
```

### 4. Error Handling

```python
from maos.errors import ToolTimeoutError, LLMError

async def invoke_tool(self, tool_id: str, arguments: dict) -> ToolResult:
    tool = self._tools.get(tool_id)
    if not tool:
        raise ValueError(f"Tool not found: {tool_id}")
    
    try:
        result = await asyncio.wait_for(
            tool.execute(**arguments),
            timeout=tool.timeout_seconds
        )
        return ToolResult(tool_id=tool_id, output=result)
    except asyncio.TimeoutError:
        raise ToolTimeoutError(f"Tool {tool_id} timed out")
```

### 5. Logging

```python
import structlog

log = structlog.get_logger()

async def route(self, state: GraphState) -> str:
    log.info("supervisor_routing", 
             message_count=len(state["messages"]),
             iteration=state["iteration_count"])
    # ...
    log.info("routing_decision", next_worker=decision.next)
    return decision.next
```

---

## Testing Patterns

### Unit Test

```python
import pytest
from maos.config.loader import ConfigLoader

def test_load_valid_config():
    loader = ConfigLoader()
    config = loader.load("tests/fixtures/valid_config.yaml")
    
    assert "default" in config.llms
    assert config.llms["default"].provider == "openai"
```

### Integration Test

```python
import pytest
from maos.graph.factory import GraphFactory

@pytest.mark.integration
async def test_graph_routes_to_worker(sample_config, mock_llm):
    factory = GraphFactory(sample_config)
    graph = factory.build()
    
    result = await graph.ainvoke({
        "messages": [{"role": "user", "content": "Research AI"}]
    })
    
    assert "research_agent" in result.get("routing_history", [])
```

### E2E Test

```python
import pytest
from httpx import AsyncClient

@pytest.mark.e2e
async def test_chat_endpoint(test_client: AsyncClient):
    response = await test_client.post("/chat", json={
        "messages": [{"role": "user", "content": "Hello"}]
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "final_response" in data
```

---

## Files Reference

When implementing a component, check these docs:

| Component | Primary Doc | Supporting Docs |
|-----------|-------------|-----------------|
| Config | D10, D25-D28 | D03 (glossary) |
| LLM | D11 | D08 (integration) |
| MCP | D12 | D08, D63 (guide) |
| Tools | D13 | D45-D50 (models) |
| Skills | D14-D15 | D26 (config ref) |
| Agents | D16 | D60 (guide) |
| A2A | D17 | D61-D62 (guides) |
| Graph | D18-D21 | D34-D44 (diagrams) |
| API | D24, D29-D33 | D30 (streaming) |
| Testing | D66-D68 | - |

---

## Verification Checklist

After implementing each task:

- [ ] All Pydantic models validate correctly
- [ ] Async functions don't block
- [ ] Errors are handled gracefully
- [ ] Logging is present at key points
- [ ] Unit tests pass
- [ ] Integration with other components works

---

## Final Integration Test

The system is complete when this works:

```bash
# Start server
python -m maos.main --config config/config.yaml

# Test chat
curl -X POST http://localhost:7777/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Research AI agents"}]}'

# Test streaming
curl -N "http://localhost:7777/chat?stream=true" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Tell me about AI"}]}'

# Test human-in-the-loop (supervisor asks for clarification, then resume)
# 1. Send ambiguous request -> get input_required event
# 2. POST /chat/resume with user's clarification
# 3. Get final response
```

---

## Tips

1. **Start with config models** - Everything else depends on them
2. **Use the Mermaid diagrams** - They show exact data flows
3. **Test incrementally** - Don't wait until everything is built
4. **Check D10-D24 for interfaces** - They define the contracts
5. **The docs are the spec** - When in doubt, read the docs

---

**Good luck! The docs contain everything needed to build this system.**
