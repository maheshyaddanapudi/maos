# Multi-Agent Orchestration System (MAOS)

> A config-driven multi-agent orchestration system using LangGraph Supervisor, Any-Agent runtime, MCP tools, and A2A agent communication.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [UI Integration](#ui-integration)
- [Human-in-the-Loop](#human-in-the-loop)
- [MCP Tool Integration](#mcp-tool-integration)
- [A2A External Agents](#a2a-external-agents)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Documentation](#documentation)
- [Roadmap](#roadmap)
- [Contributing](#contributing)

---

## Overview

MAOS is a **100% config-driven** orchestration system that enables flexible AI agent workflows without code changes. It combines:

- **LangGraph Supervisor** - Intelligent routing between specialist agents
- **Any-Agent** - Framework-agnostic agent runtime (LangChain, OpenAI, Google ADK, etc.)
- **MCP (Model Context Protocol)** - Standardized tool integration
- **A2A (Agent-to-Agent)** - External agent discovery and communication

### Why MAOS?

| Challenge | MAOS Solution |
|-----------|---------------|
| Framework lock-in | Any-Agent supports 7+ frameworks via config |
| Tool integration complexity | MCP protocol standardizes all tools |
| External agent silos | A2A protocol enables interoperability |
| Rigid architectures | 100% YAML config, zero code changes |
| Complex orchestration | LangGraph handles routing automatically |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MAOS Architecture                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│    ┌──────────┐         ┌─────────────────────────────────────────────┐     │
│    │  Chat UI │◄───────►│              API Server (FastAPI)           │     │
│    │(Any Client)        │  REST | SSE Streaming | OpenAI-Compatible   │     │
│    └──────────┘         └───────────────────┬─────────────────────────┘     │
│                                             │                                │
│                         ┌───────────────────▼───────────────────┐           │
│                         │        LangGraph Supervisor           │           │
│                         │   • Routing decisions                 │           │
│                         │   • send_message tool (HITL)          │           │
│                         │   • Iteration control                 │           │
│                         └───────────────────┬───────────────────┘           │
│                                             │                                │
│           ┌─────────────────────────────────┼─────────────────────────────┐ │
│           │                                 │                             │ │
│  ┌────────▼────────┐           ┌────────────▼────────┐      ┌────────────▼─┐│
│  │  Native Worker  │           │   Native Worker     │      │External Agent││
│  │  (Any-Agent)    │           │   (Any-Agent)       │      │   (A2A)      ││
│  │                 │           │                     │      │              ││
│  │  Framework:     │           │  Framework:         │      │ Discovered   ││
│  │  • LangChain    │           │  • OpenAI           │      │ via Agent    ││
│  │  • TinyAgent    │           │  • Google ADK       │      │ Cards        ││
│  │  • Smolagents   │           │  • Agno             │      │              ││
│  └────────┬────────┘           └──────────┬──────────┘      └──────┬───────┘│
│           │                               │                        │        │
│  ┌────────▼────────┐           ┌──────────▼──────────┐      ┌──────▼───────┐│
│  │   MCP Tools     │           │    MCP Tools        │      │   Remote     ││
│  │   (stdio/HTTP)  │           │    (stdio/HTTP)     │      │   Service    ││
│  └─────────────────┘           └─────────────────────┘      └──────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Flow

```
User Request
     │
     ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ API Server  │───►│ Supervisor  │───►│   Worker    │───►│  MCP Tool   │
│             │    │  (routes)   │    │ (executes)  │    │  (action)   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
     ▲                   │                   │                   │
     │                   │                   │                   │
     └───────────────────┴───────────────────┴───────────────────┘
                              Response Flow
```

---

## Features

### Core Features

- ✅ **Config-Driven Architecture** - Add agents, tools, LLMs via YAML
- ✅ **Multi-Framework Support** - LangChain, OpenAI, Google ADK, TinyAgent, Smolagents, Agno, LlamaIndex
- ✅ **MCP Tool Protocol** - Standardized tool integration (stdio & HTTP transports)
- ✅ **A2A Agent Protocol** - Discover and use external agents
- ✅ **Multiple LLM Providers** - OpenAI, Anthropic, Google, Ollama, Azure
- ✅ **Streaming Responses** - Real-time SSE streaming to UI
- ✅ **Human-in-the-Loop** - Supervisor can request user input mid-flow
- ✅ **OpenAI-Compatible API** - Drop-in replacement for existing UIs

### Prototype Scope

| Feature | Status | Notes |
|---------|--------|-------|
| LangGraph Supervisor | 🎯 Core | Routing loop with iteration limits |
| Native Workers | 🎯 Core | Any-Agent with configurable frameworks |
| MCP Integration | 🎯 Core | stdio and HTTP transports |
| A2A Discovery | 🎯 Core | Agent Cards, host index |
| REST API | 🎯 Core | FastAPI with validation |
| SSE Streaming | 🎯 Core | Token-level streaming |
| Human-in-Loop | 🎯 Core | send_message tool |
| Authentication | 📋 Phase 2 | Extension points ready |
| Multi-tenancy | 📋 Phase 2 | Extension points ready |
| Horizontal Scale | 📋 Phase 3 | Architecture supports it |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for MCP servers)
- API keys for LLM providers (OpenAI, Anthropic, etc.)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/maos.git
cd maos

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Install Any-Agent with desired frameworks
pip install 'any-agent[langchain,openai]'
```

### Configuration

```bash
# Copy example config
cp config/config.example.yaml config/config.yaml

# Set environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Run

```bash
# Start the server
python -m maos.main --config config/config.yaml

# Or with environment override
MAOS_CONFIG=config/config.yaml python -m maos.main
```

### Test

```bash
# Health check
curl http://localhost:7777/health

# Send a chat message
curl -X POST http://localhost:7777/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}]}'

# Stream a response
curl -X POST "http://localhost:7777/chat?stream=true" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Tell me about AI agents"}]}'
```

---

## Configuration

MAOS is entirely configured via YAML. Here's a minimal example:

```yaml
# config.yaml

# LLM Providers
llms:
  default:
    provider: openai
    model: gpt-4o
    temperature: 0.7

# MCP Tool Servers
mcp_servers:
  knowledge:
    transport: stdio
    command: ["python", "-m", "mcp_server_knowledge"]

# Tools (from MCP servers)
tools:
  search:
    server: knowledge
    tool_name: "search.documents"

# Skills (groups of tools)
skills:
  research:
    tools: ["search"]
    description: "Research capabilities"

# Skillsets (groups of skills)
skillsets:
  researcher:
    skills: ["research"]

# Agents
agents:
  supervisor:
    kind: supervisor
    llm: default
    system_prompt: |
      You coordinate tasks between specialist agents.
      Available workers: research_agent
      Route appropriately based on the task.

  research_agent:
    kind: native_worker
    framework: langchain
    llm: default
    skillset: researcher
    system_prompt: "You are a research specialist."
    description: "Expert at finding and synthesizing information"

# Graph Configuration
graph:
  max_iterations: 10
  timeouts:
    worker_seconds: 60
    tool_call_seconds: 30

# API Server
serving:
  api:
    host: "0.0.0.0"
    port: 7777
```

See [docs/D26-config-reference-guide.md](docs/D26-config-reference-guide.md) for complete reference.

---

## API Reference

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | Send chat message |
| `POST` | `/chat?stream=true` | Stream chat response |
| `POST` | `/chat/resume` | Resume after human-in-loop |
| `GET` | `/agents` | List available agents |
| `GET` | `/health` | Health check |
| `POST` | `/v1/chat/completions` | OpenAI-compatible endpoint |

### Chat Request

```json
{
  "messages": [
    {"role": "user", "content": "Research AI trends"}
  ],
  "thread_id": "optional-thread-id",
  "config": {
    "max_iterations": 5
  }
}
```

### Chat Response

```json
{
  "thread_id": "uuid",
  "messages": [...],
  "final_response": "Here's what I found...",
  "routing_history": ["supervisor", "research_agent", "supervisor"],
  "tool_calls": [...],
  "usage": {"total_tokens": 1500}
}
```

### SSE Stream Events

```
event: chunk
data: {"content": "Here's", "agent": "research_agent"}

event: tool_call
data: {"tool": "search", "arguments": {"query": "AI trends"}}

event: tool_result
data: {"tool": "search", "result": "..."}

event: routing
data: {"from": "supervisor", "to": "research_agent", "reasoning": "..."}

event: input_required
data: {"prompt": "Please clarify...", "thread_id": "..."}

event: done
data: {"thread_id": "...", "total_tokens": 1500}
```

See [docs/D29-D33-api-interface-specifications.md](docs/D29-D33-api-interface-specifications.md) for complete API docs.

---

## UI Integration

MAOS is designed to work with any chat UI via multiple interfaces:

### Option 1: OpenAI-Compatible (Easiest)

Works with Open WebUI, ChatGPT-style interfaces, and any OpenAI client:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:7777/v1",
    api_key="not-needed"  # MAOS handles auth differently
)

response = client.chat.completions.create(
    model="maos",  # Ignored, uses config
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True
)

for chunk in response:
    print(chunk.choices[0].delta.content, end="")
```

### Option 2: Direct REST + SSE

For custom UIs with full control:

```javascript
// React example
const [messages, setMessages] = useState([]);
const [isWaitingForInput, setIsWaitingForInput] = useState(false);

async function sendMessage(content) {
  const response = await fetch('/chat?stream=true', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      messages: [...messages, {role: 'user', content}],
      thread_id: threadId
    })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const {done, value} = await reader.read();
    if (done) break;

    const lines = decoder.decode(value).split('\n');
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const event = JSON.parse(line.slice(6));
        
        if (event.type === 'chunk') {
          // Append to current message
          appendToMessage(event.content);
        } else if (event.type === 'input_required') {
          // Show input prompt to user
          setIsWaitingForInput(true);
          setInputPrompt(event.prompt);
        }
      }
    }
  }
}

// Resume after user provides input
async function resumeWithInput(userInput) {
  await fetch('/chat/resume', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      thread_id: threadId,
      input: userInput
    })
  });
  setIsWaitingForInput(false);
}
```

### Option 3: WebSocket (Optional)

For bidirectional real-time communication:

```javascript
const ws = new WebSocket('ws://localhost:7777/ws/chat');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle messages, interrupts, etc.
};

ws.send(JSON.stringify({
  type: 'message',
  content: 'Hello!'
}));
```

---

## Human-in-the-Loop

The supervisor has a special `send_message` tool for requesting user input:

### How It Works

1. Supervisor decides it needs clarification
2. Calls `send_message` tool with a prompt
3. Graph execution **pauses** (LangGraph interrupt)
4. API sends `input_required` SSE event to UI
5. UI displays prompt and collects user input
6. User submits response via `POST /chat/resume`
7. Graph execution **resumes** with user's input
8. Supervisor continues with the new information

### Sequence Diagram

```
User        UI          API         Supervisor      Worker
 │           │           │              │             │
 │──"Help"──►│           │              │             │
 │           │──POST────►│              │             │
 │           │           │──invoke─────►│             │
 │           │           │              │──need info──│
 │           │           │              │             │
 │           │           │◄─interrupt───│             │
 │           │◄─SSE: input_required─────│             │
 │◄─"Please clarify..."──│              │             │
 │           │           │              │             │
 │──"I meant X"─────────►│              │             │
 │           │──POST /resume───────────►│             │
 │           │           │──resume─────►│             │
 │           │           │              │──continue──►│
 │           │◄─SSE: chunk──────────────│◄────────────│
 │◄─"Got it, here's..."──│              │             │
```

### Configuration

```yaml
agents:
  supervisor:
    kind: supervisor
    llm: default
    tools:
      - send_message  # Built-in HITL tool
    system_prompt: |
      You can use the send_message tool to ask the user for clarification.
      Use it when the request is ambiguous or you need more information.
```

### Resume Endpoint

```bash
curl -X POST http://localhost:7777/chat/resume \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "abc-123",
    "input": "I meant the quarterly report from Q3"
  }'
```

---

## MCP Tool Integration

MAOS uses MCP (Model Context Protocol) for standardized tool integration.

### Supported Transports

| Transport | Use Case | Config |
|-----------|----------|--------|
| `stdio` | Local process tools | `command: ["python", "-m", "server"]` |
| `http` | Remote HTTP servers | `url: "http://localhost:8080/mcp"` |
| `sse` | Server-sent events | `url: "http://localhost:8080/sse"` |

### Creating an MCP Server

```python
# mcp_server_example/__main__.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Example Tools")

@mcp.tool()
async def search_documents(query: str, limit: int = 10) -> str:
    """Search internal documents."""
    results = await do_search(query, limit)
    return format_results(results)

@mcp.tool()
def calculate(expression: str) -> float:
    """Evaluate a math expression."""
    return eval(expression)  # Use safe eval in production!

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### Configuring Tools

```yaml
mcp_servers:
  example:
    transport: stdio
    command: ["python", "-m", "mcp_server_example"]
    timeout_seconds: 30

tools:
  search:
    server: example
    tool_name: "search_documents"
  
  calc:
    server: example
    tool_name: "calculate"

skills:
  research:
    tools: ["search"]
  math:
    tools: ["calc"]

skillsets:
  analyst:
    skills: ["research", "math"]
```

---

## A2A External Agents

MAOS can discover and communicate with external agents via A2A protocol.

### Discovery Process

1. At boot time, MAOS fetches Agent Cards from configured seed URLs
2. Agent Cards describe capabilities, skills, and endpoints
3. Based on `import_policy`, agents are imported as graph nodes or tools
4. During execution, supervisor can route to external agents

### Configuration

```yaml
a2a:
  discovery:
    seeds:
      - "http://analytics-agent.internal:9001"
      - "http://ml-agent.internal:9002"
    host_index_path: "/a2a/index.json"
    well_known_paths:
      - "/.well-known/agent.json"
    timeout_seconds: 10

  import_policy:
    enabled: true
    mode: langgraph_nodes  # or "tools_only"
    prefix: "ext::"
    include_tags: ["approved", "production"]
    exclude_names: ["experimental-agent"]
    max_agents: 20
```

### Creating an A2A Agent

See [docs/D61-implementing-external-a2a-agent.md](docs/D60-D65-implementation-guides.md) for complete guide.

```python
# Minimal A2A agent
from starlette.applications import Starlette
from starlette.responses import JSONResponse

AGENT_CARD = {
    "protocolVersion": "1.0",
    "name": "my-agent",
    "description": "My specialized agent",
    "supportedInterfaces": [
        {"url": "http://localhost:9010/a2a", "protocolBinding": "JSONRPC"}
    ],
    "skills": [
        {"id": "analyze", "name": "Data Analysis", "tags": ["analytics"]}
    ]
}

app = Starlette(routes=[
    Route("/.well-known/agent.json", lambda r: JSONResponse(AGENT_CARD)),
    Route("/a2a", handle_a2a, methods=["POST"]),
])
```

---

## Development

### Project Structure

```
maos/
├── maos/                    # Main package
│   ├── __init__.py
│   ├── main.py             # Entry point
│   ├── config/             # Configuration loading
│   │   ├── loader.py
│   │   ├── models.py
│   │   └── schema.json
│   ├── llm/                # LLM provider adapters
│   │   ├── factory.py
│   │   ├── registry.py
│   │   └── adapters/
│   ├── mcp/                # MCP integration
│   │   ├── registry.py
│   │   └── transports/
│   ├── tools/              # Tool management
│   │   ├── registry.py
│   │   └── models.py
│   ├── skills/             # Skill/Skillset management
│   │   └── registry.py
│   ├── agents/             # Agent management
│   │   ├── factory.py
│   │   └── registry.py
│   ├── a2a/                # A2A integration
│   │   ├── discovery.py
│   │   ├── client.py
│   │   └── models.py
│   ├── graph/              # LangGraph orchestration
│   │   ├── factory.py
│   │   ├── state.py
│   │   └── nodes/
│   │       ├── supervisor.py
│   │       ├── worker.py
│   │       └── external.py
│   └── api/                # FastAPI server
│       ├── server.py
│       ├── routes/
│       └── middleware/
├── mcp-servers/            # Example MCP servers
├── a2a-agents/             # Example A2A agents
├── config/                 # Configuration files
├── tests/                  # Test suite
├── docs/                   # Documentation (68 documents)
├── scripts/                # Utility scripts
├── requirements.txt
├── pyproject.toml
├── README.md               # This file
├── CLAUDE.md              # Instructions for Claude Code
└── AGENT.md               # Instructions for AI coding agents
```

### Development Setup

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run linting
ruff check maos/
mypy maos/

# Run tests
pytest

# Run with hot reload
uvicorn maos.api.server:app --reload --port 7777
```

### Code Style

- Python 3.11+ with type hints
- Async/await for all I/O operations
- Pydantic v2 for data models
- Ruff for linting, Black for formatting
- 85% minimum test coverage

---

## Testing

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest -m unit

# Integration tests
pytest -m integration

# E2E tests
pytest -m e2e

# With coverage
pytest --cov=maos --cov-report=html
```

### Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── unit/                # Unit tests
│   ├── test_config.py
│   ├── test_llm.py
│   ├── test_mcp.py
│   └── ...
├── integration/         # Integration tests
│   ├── test_graph.py
│   ├── test_a2a.py
│   └── ...
├── e2e/                 # End-to-end tests
│   ├── test_chat_flow.py
│   └── ...
└── mocks/               # Mock implementations
    ├── llm.py
    ├── mcp.py
    └── a2a.py
```

See [docs/D66-D68-testing-documentation.md](docs/D66-D68-testing-documentation.md) for complete testing guide.

---

## Deployment

### Docker

```bash
# Build image
docker build -t maos:latest .

# Run container
docker run -p 7777:7777 \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -v $(pwd)/config:/app/config \
  maos:latest
```

### Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f orchestrator

# Stop
docker-compose down
```

See [docs/D52-docker-compose-spec.md](docs/D51-D56-setup-and-operations.md) for complete Docker setup.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | If using OpenAI | OpenAI API key |
| `ANTHROPIC_API_KEY` | If using Anthropic | Anthropic API key |
| `GOOGLE_API_KEY` | If using Google | Google AI API key |
| `MAOS_CONFIG` | No | Config file path |
| `MAOS_LOG_LEVEL` | No | Log level (DEBUG, INFO, etc.) |

See [docs/D28-environment-variables-and-secrets.md](docs/D28-environment-variables-and-secrets.md) for complete list.

---

## Documentation

Complete documentation is in the `docs/` directory:

| Category | Documents |
|----------|-----------|
| **Executive** | D01: Executive Summary |
| **Architecture** | D02-D09: Vision, Glossary, C4 Diagrams, Tech Stack |
| **Configuration** | D25-D28: Schema, Reference, Examples, Environment |
| **Design** | D07-D08: Data Flow, Integration Architecture |
| **Specifications** | D10-D24: Module Specs, D29-D33: API Specs |
| **Diagrams** | D34-D44: Sequences, D45-D50: Data Models |
| **Operations** | D51-D56: Setup, Docker, Troubleshooting |
| **Implementation** | D60-D65: Step-by-step Guides |
| **Testing** | D66-D68: Strategy, Cases, Mocks |
| **Future** | D57-D59: Security Hooks, Extensibility, Roadmap |

**Total: 68 documents with 56+ Mermaid diagrams**

---

## Roadmap

### Phase 1: Prototype (Current)
- [x] Architecture design
- [x] Documentation (68 docs)
- [ ] Core implementation
- [ ] Basic testing

### Phase 2: Hardening
- [ ] Authentication/Authorization
- [ ] Persistent conversation state
- [ ] Comprehensive test coverage
- [ ] Performance optimization

### Phase 3: Scale
- [ ] Multi-tenancy
- [ ] Horizontal scaling
- [ ] Advanced observability
- [ ] Admin dashboard

### Phase 4: Enterprise
- [ ] Full RBAC
- [ ] Audit logging
- [ ] SSO integration
- [ ] Compliance features

---

## Contributing

1. Read the documentation in `docs/`
2. Check `CLAUDE.md` or `AGENT.md` for AI-assisted development
3. Follow the code style guidelines
4. Write tests for new features
5. Submit PR with clear description

---

## License

MIT License - See [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) - Graph-based orchestration
- [Any-Agent](https://github.com/mozilla-ai/any-agent) - Framework-agnostic agents
- [MCP](https://modelcontextprotocol.io/) - Model Context Protocol
- [A2A](https://github.com/google/a2a-spec) - Agent-to-Agent Protocol

---

**Built with ❤️ for the future of AI agent orchestration**
