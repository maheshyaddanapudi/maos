# D66-D68: Testing Documentation

## Config-Driven Multi-Agent Orchestration System

**Document ID:** D66-D68  
**Version:** 1.0  
**Status:** Draft  
**Last Updated:** January 2026

---

## Document Index

| Doc ID | Document | Description |
|--------|----------|-------------|
| D66 | Test Strategy | Unit, integration, E2E approach |
| D67 | Test Cases Catalog | Key scenarios to validate |
| D68 | Mock/Stub Specifications | How to mock MCP, A2A, LLMs |

---

# D66: Test Strategy

## Overview

This document defines the testing strategy for the Multi-Agent Orchestration System, covering unit tests, integration tests, and end-to-end tests.

---

## 1. Testing Pyramid

```
                    ┌─────────┐
                    │   E2E   │  Few, slow, high confidence
                    │  Tests  │
                    └────┬────┘
                   ┌─────┴─────┐
                   │Integration│  Medium count, moderate speed
                   │   Tests   │
                   └─────┬─────┘
              ┌──────────┴──────────┐
              │     Unit Tests      │  Many, fast, focused
              └─────────────────────┘
```

| Level | Count | Speed | Coverage Focus |
|-------|-------|-------|----------------|
| Unit | 200+ | < 1s each | Individual functions, classes |
| Integration | 50+ | 1-10s each | Module interactions |
| E2E | 10-20 | 10-60s each | Full user flows |

---

## 2. Test Categories

### 2.1 Unit Tests

**Scope:** Individual functions and classes in isolation.

**Targets:**
- Config parsing and validation
- Registry operations (add, get, list)
- State transformations
- Data model serialization
- Utility functions

**Mocking:** All external dependencies mocked.

**Location:** `tests/unit/`

### 2.2 Integration Tests

**Scope:** Interaction between modules within the system.

**Targets:**
- ConfigLoader → Registries flow
- AgentFactory → AnyAgent integration
- GraphFactory → LangGraph compilation
- MCPRegistry → Tool materialization
- A2ADiscovery → AgentRegistry

**Mocking:** External services (LLMs, MCP servers, A2A agents) mocked.

**Location:** `tests/integration/`

### 2.3 End-to-End Tests

**Scope:** Full system behavior from API to response.

**Targets:**
- Complete chat flows
- Streaming responses
- Multi-turn conversations
- Error scenarios
- Human-in-the-loop flows

**Mocking:** Minimal (may use test LLM or Ollama).

**Location:** `tests/e2e/`

---

## 3. Test Infrastructure

### 3.1 Framework and Tools

| Tool | Purpose |
|------|---------|
| `pytest` | Test framework |
| `pytest-asyncio` | Async test support |
| `pytest-mock` | Mocking utilities |
| `pytest-cov` | Coverage reporting |
| `respx` | HTTPX mocking |
| `factory_boy` | Test data factories |

### 3.2 Configuration

```python
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --cov=maos --cov-report=html"
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "e2e: End-to-end tests",
    "slow: Slow tests (>10s)",
]
```

### 3.3 Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# E2E tests only
pytest -m e2e

# With coverage
pytest --cov=maos --cov-report=html

# Specific module
pytest tests/unit/test_config.py

# Verbose with output
pytest -v -s
```

---

## 4. Test Environment

### 4.1 Environment Variables

```bash
# Test environment (.env.test)
OPENAI_API_KEY=sk-test-key-for-mocking
ANTHROPIC_API_KEY=sk-ant-test-key
TEST_MCP_TIMEOUT=5
TEST_A2A_TIMEOUT=5
LOG_LEVEL=DEBUG
```

### 4.2 Fixtures

```python
# tests/conftest.py

import pytest
from maos.config.loader import ConfigLoader
from maos.config.models import Config

@pytest.fixture
def sample_config() -> Config:
    """Minimal valid configuration."""
    return ConfigLoader().load_from_string("""
        llms:
          default:
            provider: openai
            model: gpt-4o
        agents:
          supervisor:
            kind: supervisor
            system_prompt: "Test supervisor"
            tools: []
    """)

@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "Test response"
            }
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20}
    }

@pytest.fixture
async def test_client(sample_config):
    """Test client for API testing."""
    from httpx import AsyncClient
    from maos.api.server import create_app
    
    app = await create_app(sample_config)
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
```

---

## 5. Coverage Requirements

| Module | Minimum Coverage |
|--------|-----------------|
| `config/` | 90% |
| `llm/` | 85% |
| `mcp/` | 80% |
| `tools/` | 85% |
| `agents/` | 85% |
| `a2a/` | 80% |
| `graph/` | 85% |
| `api/` | 80% |
| **Overall** | **85%** |

---

## 6. CI/CD Integration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run unit tests
        run: pytest -m unit --cov=maos
      
      - name: Run integration tests
        run: pytest -m integration
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

# D67: Test Cases Catalog

## Overview

This document catalogs key test scenarios organized by component and priority.

---

## 1. Configuration Tests

### Unit Tests

| ID | Test Case | Priority |
|----|-----------|----------|
| CFG-U01 | Load valid YAML config | High |
| CFG-U02 | Load valid JSON config | High |
| CFG-U03 | Reject invalid YAML syntax | High |
| CFG-U04 | Reject missing required fields | High |
| CFG-U05 | Reject invalid field values | High |
| CFG-U06 | Apply default values | Medium |
| CFG-U07 | Override config from env vars | Medium |
| CFG-U08 | Validate cross-references (tool→server) | High |
| CFG-U09 | Handle empty optional sections | Medium |
| CFG-U10 | Reject duplicate keys | Low |

### Integration Tests

| ID | Test Case | Priority |
|----|-----------|----------|
| CFG-I01 | Config loads all registries correctly | High |
| CFG-I02 | Invalid config prevents startup | High |
| CFG-I03 | Config reload (if supported) | Low |

---

## 2. LLM Tests

### Unit Tests

| ID | Test Case | Priority |
|----|-----------|----------|
| LLM-U01 | Create OpenAI adapter | High |
| LLM-U02 | Create Anthropic adapter | High |
| LLM-U03 | Create Google adapter | Medium |
| LLM-U04 | Create Ollama adapter | Medium |
| LLM-U05 | Handle missing API key | High |
| LLM-U06 | Convert messages to provider format | High |
| LLM-U07 | Convert tools to provider format | High |
| LLM-U08 | Parse tool calls from response | High |
| LLM-U09 | Handle rate limit errors | Medium |
| LLM-U10 | Handle timeout errors | Medium |

### Integration Tests

| ID | Test Case | Priority |
|----|-----------|----------|
| LLM-I01 | LLM registry resolves by name | High |
| LLM-I02 | Default LLM fallback | Medium |
| LLM-I03 | Per-agent LLM override | High |

---

## 3. MCP Tests

### Unit Tests

| ID | Test Case | Priority |
|----|-----------|----------|
| MCP-U01 | Parse stdio transport config | High |
| MCP-U02 | Parse HTTP transport config | High |
| MCP-U03 | Validate tool schema | High |
| MCP-U04 | Handle connection failure | High |
| MCP-U05 | Handle tool execution timeout | High |
| MCP-U06 | Parse tool list response | High |
| MCP-U07 | Parse tool call response | High |
| MCP-U08 | Handle MCP errors | Medium |

### Integration Tests

| ID | Test Case | Priority |
|----|-----------|----------|
| MCP-I01 | Connect to stdio server | High |
| MCP-I02 | Connect to HTTP server | High |
| MCP-I03 | Materialize tools from server | High |
| MCP-I04 | Tool invocation end-to-end | High |
| MCP-I05 | Handle server crash/restart | Medium |

---

## 4. A2A Tests

### Unit Tests

| ID | Test Case | Priority |
|----|-----------|----------|
| A2A-U01 | Parse Agent Card JSON | High |
| A2A-U02 | Parse host index JSON | High |
| A2A-U03 | Apply include_tags filter | High |
| A2A-U04 | Apply exclude_names filter | High |
| A2A-U05 | Apply max_agents limit | Medium |
| A2A-U06 | Build A2A request | High |
| A2A-U07 | Parse A2A response | High |
| A2A-U08 | Handle A2A errors | High |
| A2A-U09 | Extract skills from Agent Card | Medium |

### Integration Tests

| ID | Test Case | Priority |
|----|-----------|----------|
| A2A-I01 | Discover from individual agent URL | High |
| A2A-I02 | Discover from host index | High |
| A2A-I03 | Import as langgraph_nodes | High |
| A2A-I04 | Import as tools_only | High |
| A2A-I05 | Skill-based tool assignment | Medium |
| A2A-I06 | Handle discovery timeout | Medium |
| A2A-I07 | Handle unreachable agent | Medium |

---

## 5. Graph Tests

### Unit Tests

| ID | Test Case | Priority |
|----|-----------|----------|
| GRF-U01 | Create supervisor node | High |
| GRF-U02 | Create worker node | High |
| GRF-U03 | Create external node | High |
| GRF-U04 | Build routing edges | High |
| GRF-U05 | Parse supervisor decision | High |
| GRF-U06 | Handle END decision | High |
| GRF-U07 | Handle iteration limit | High |
| GRF-U08 | Build roster prompt | Medium |

### Integration Tests

| ID | Test Case | Priority |
|----|-----------|----------|
| GRF-I01 | Graph compiles successfully | High |
| GRF-I02 | Supervisor routes to worker | High |
| GRF-I03 | Worker returns to supervisor | High |
| GRF-I04 | Multi-hop routing | Medium |
| GRF-I05 | Human-in-the-loop flow | Medium |
| GRF-I06 | Timeout handling | Medium |
| GRF-I07 | Error propagation | Medium |

---

## 6. API Tests

### Unit Tests

| ID | Test Case | Priority |
|----|-----------|----------|
| API-U01 | Validate chat request | High |
| API-U02 | Format chat response | High |
| API-U03 | Format SSE chunk | High |
| API-U04 | Format OpenAI-compatible response | Medium |
| API-U05 | Handle invalid request | High |
| API-U06 | Format error response | High |

### Integration Tests

| ID | Test Case | Priority |
|----|-----------|----------|
| API-I01 | POST /chat returns response | High |
| API-I02 | POST /chat streams response | High |
| API-I03 | GET /agents lists all agents | Medium |
| API-I04 | GET /health returns status | Medium |
| API-I05 | POST /v1/chat/completions works | Medium |
| API-I06 | Handle concurrent requests | Medium |

---

## 7. End-to-End Tests

| ID | Test Case | Priority |
|----|-----------|----------|
| E2E-01 | Simple question → single worker → response | High |
| E2E-02 | Complex question → multiple workers → response | High |
| E2E-03 | Tool-using worker completes task | High |
| E2E-04 | External agent called successfully | High |
| E2E-05 | Streaming response works end-to-end | High |
| E2E-06 | Human-in-the-loop flow works | Medium |
| E2E-07 | Error in worker handled gracefully | Medium |
| E2E-08 | Timeout handled gracefully | Medium |
| E2E-09 | OpenAI-compatible endpoint works with client | Medium |
| E2E-10 | Multi-turn conversation maintains context | Medium |

---

# D68: Mock/Stub Specifications

## Overview

This document specifies how to mock external dependencies for testing.

---

## 1. LLM Mocking

### Mock LLM Client

```python
# tests/mocks/llm.py

from typing import List, Optional, AsyncIterator
from maos.llm.base import LLMAdapter, LLMResponse, LLMChunk

class MockLLMAdapter(LLMAdapter):
    """Mock LLM adapter for testing."""
    
    def __init__(self, responses: List[str] = None, tool_calls: List[dict] = None):
        self._responses = responses or ["Mock response"]
        self._tool_calls = tool_calls or []
        self._call_count = 0
        self._calls = []
    
    async def invoke(self, messages, tools=None) -> LLMResponse:
        self._calls.append({"messages": messages, "tools": tools})
        response_idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        
        return LLMResponse(
            content=self._responses[response_idx],
            tool_calls=self._tool_calls,
            usage={"prompt_tokens": 10, "completion_tokens": 20}
        )
    
    async def stream(self, messages, tools=None) -> AsyncIterator[LLMChunk]:
        response = await self.invoke(messages, tools)
        words = response.content.split()
        for i, word in enumerate(words):
            yield LLMChunk(content=word + " ", done=i == len(words) - 1)
    
    def assert_called_with(self, **kwargs):
        """Assert last call contained expected values."""
        last_call = self._calls[-1]
        for key, value in kwargs.items():
            assert last_call.get(key) == value
```

### Using Mock LLM

```python
# tests/unit/test_supervisor.py

import pytest
from tests.mocks.llm import MockLLMAdapter

@pytest.fixture
def mock_llm():
    return MockLLMAdapter(responses=[
        '{"next": "research_agent", "reasoning": "Task requires research"}'
    ])

async def test_supervisor_routes_correctly(mock_llm):
    supervisor = SupervisorNode(llm=mock_llm, roster=["research_agent"])
    state = {"messages": [{"role": "user", "content": "Research AI"}]}
    
    result = await supervisor.run(state)
    
    assert result["next"] == "research_agent"
```

---

## 2. MCP Server Mocking

### Mock MCP Server

```python
# tests/mocks/mcp.py

from typing import Dict, Any, List

class MockMCPServer:
    """Mock MCP server for testing."""
    
    def __init__(self, tools: List[Dict[str, Any]] = None):
        self._tools = tools or []
        self._tool_results = {}
        self._calls = []
    
    def set_tool_result(self, tool_name: str, result: Any):
        """Set result for a tool call."""
        self._tool_results[tool_name] = result
    
    async def list_tools(self) -> List[Dict]:
        """Return tool definitions."""
        return self._tools
    
    async def call_tool(self, name: str, arguments: Dict) -> Any:
        """Call a tool and return result."""
        self._calls.append({"name": name, "arguments": arguments})
        
        if name in self._tool_results:
            result = self._tool_results[name]
            if callable(result):
                return result(arguments)
            return result
        
        return f"Mock result for {name}"
    
    def assert_tool_called(self, name: str, **expected_args):
        """Assert tool was called with expected arguments."""
        matching = [c for c in self._calls if c["name"] == name]
        assert matching, f"Tool {name} was not called"
        if expected_args:
            assert matching[-1]["arguments"] == expected_args

class MockMCPConnection:
    """Mock MCP connection for testing."""
    
    def __init__(self, server: MockMCPServer):
        self._server = server
        self.status = "connected"
    
    async def invoke_tool(self, tool_name: str, arguments: Dict) -> Any:
        return await self._server.call_tool(tool_name, arguments)
```

### Using Mock MCP

```python
# tests/integration/test_tools.py

import pytest
from tests.mocks.mcp import MockMCPServer, MockMCPConnection

@pytest.fixture
def mock_mcp():
    server = MockMCPServer(tools=[
        {"name": "search_web", "description": "Search the web"},
        {"name": "summarize", "description": "Summarize text"}
    ])
    server.set_tool_result("search_web", "Search results: AI trends...")
    return server

async def test_tool_invocation(mock_mcp):
    connection = MockMCPConnection(mock_mcp)
    
    result = await connection.invoke_tool("search_web", {"query": "AI"})
    
    assert "Search results" in result
    mock_mcp.assert_tool_called("search_web", query="AI")
```

---

## 3. A2A Agent Mocking

### Mock A2A Agent

```python
# tests/mocks/a2a.py

from typing import Dict, Any, Optional, List
import json

class MockA2AAgent:
    """Mock A2A agent for testing."""
    
    def __init__(self, name: str, skills: List[str] = None):
        self.name = name
        self.skills = skills or []
        self._responses = {}
        self._calls = []
    
    def get_agent_card(self) -> Dict:
        """Return Agent Card."""
        return {
            "protocolVersion": "1.0",
            "name": self.name,
            "description": f"Mock {self.name} agent",
            "version": "1.0.0",
            "supportedInterfaces": [
                {"url": f"http://mock/{self.name}", "protocolBinding": "JSONRPC"}
            ],
            "skills": [
                {"id": s, "name": s, "tags": ["mock"]}
                for s in self.skills
            ]
        }
    
    def set_response(self, response: str):
        """Set response for next call."""
        self._responses["default"] = response
    
    async def handle_request(self, request: Dict) -> Dict:
        """Handle A2A request."""
        self._calls.append(request)
        
        response_text = self._responses.get("default", f"Mock response from {self.name}")
        
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "task": {
                    "id": f"task-{request.get('id')}",
                    "status": "COMPLETED",
                    "result": {
                        "role": "agent",
                        "parts": [{"type": "text", "text": response_text}]
                    }
                }
            }
        }

class MockA2AHost:
    """Mock A2A host with multiple agents."""
    
    def __init__(self):
        self._agents: Dict[str, MockA2AAgent] = {}
    
    def add_agent(self, agent: MockA2AAgent):
        self._agents[agent.name] = agent
    
    def get_host_index(self) -> Dict:
        return {
            "version": "1.0",
            "host": {"name": "Mock Host"},
            "agents": [
                {
                    "name": name,
                    "path": f"/a2a/{name}",
                    "agent_card_path": f"/a2a/{name}/.well-known/agent.json"
                }
                for name in self._agents
            ]
        }
```

### Using Mock A2A with respx

```python
# tests/integration/test_a2a_discovery.py

import pytest
import respx
from httpx import Response
from tests.mocks.a2a import MockA2AAgent, MockA2AHost

@pytest.fixture
def mock_a2a_host():
    host = MockA2AHost()
    host.add_agent(MockA2AAgent("analyzer", skills=["data_analysis"]))
    host.add_agent(MockA2AAgent("predictor", skills=["ml_prediction"]))
    return host

@respx.mock
async def test_discovery_from_host(mock_a2a_host):
    # Mock host index endpoint
    respx.get("http://localhost:9001/a2a/index.json").mock(
        return_value=Response(200, json=mock_a2a_host.get_host_index())
    )
    
    # Mock agent card endpoints
    for name, agent in mock_a2a_host._agents.items():
        respx.get(f"http://localhost:9001/a2a/{name}/.well-known/agent.json").mock(
            return_value=Response(200, json=agent.get_agent_card())
        )
    
    # Test discovery
    discovery = A2ADiscovery(httpx.AsyncClient())
    agents = await discovery.discover(A2AConfig(
        discovery=A2ADiscoveryConfig(seeds=["http://localhost:9001"])
    ))
    
    assert len(agents) == 2
    assert any(a.card.name == "analyzer" for a in agents)
```

---

## 4. Complete Test Example

```python
# tests/e2e/test_chat_flow.py

import pytest
import respx
from httpx import Response, AsyncClient
from tests.mocks.llm import MockLLMAdapter
from tests.mocks.mcp import MockMCPServer
from tests.mocks.a2a import MockA2AAgent

@pytest.fixture
def mock_llm():
    """LLM that routes to research_agent then completes."""
    return MockLLMAdapter(responses=[
        '{"next": "research_agent", "reasoning": "Needs research"}',
        '{"next": "END", "reasoning": "Task complete"}'
    ])

@pytest.fixture
def mock_mcp():
    server = MockMCPServer(tools=[
        {"name": "search_web", "description": "Search"}
    ])
    server.set_tool_result("search_web", "Found: AI is advancing rapidly")
    return server

@pytest.fixture
def mock_external():
    agent = MockA2AAgent("external_expert", skills=["analysis"])
    agent.set_response("External analysis complete")
    return agent

@pytest.mark.e2e
async def test_full_chat_flow(mock_llm, mock_mcp, mock_external, test_client):
    """Test complete chat flow with mocked dependencies."""
    
    response = await test_client.post("/chat", json={
        "messages": [
            {"role": "user", "content": "Research AI trends"}
        ]
    })
    
    assert response.status_code == 200
    data = response.json()
    
    assert "final_response" in data
    assert len(data["messages"]) > 1
    assert "AI" in data["final_response"]
```

---

## 5. Test Data Factories

```python
# tests/factories.py

import factory
from maos.config.models import LLMConfig, AgentConfig, ToolConfig

class LLMConfigFactory(factory.Factory):
    class Meta:
        model = LLMConfig
    
    provider = "openai"
    model = "gpt-4o"
    temperature = 0.7

class AgentConfigFactory(factory.Factory):
    class Meta:
        model = AgentConfig
    
    kind = "native_worker"
    framework = "langchain"
    llm = "default"
    skillset = "general"
    system_prompt = "You are a helpful assistant."
    description = "General purpose worker"

class ToolConfigFactory(factory.Factory):
    class Meta:
        model = ToolConfig
    
    server = "tools"
    tool_name = factory.Sequence(lambda n: f"tool_{n}")
```

---

## Related Documents

- D51: Local Development Setup
- D56: Troubleshooting Guide
- D60-D65: Implementation Guides

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Architecture Team | Initial draft |
