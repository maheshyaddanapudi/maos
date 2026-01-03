# D51-D56: Setup and Operations

## Config-Driven Multi-Agent Orchestration System

**Document ID:** D51-D56  
**Version:** 1.0  
**Status:** Draft  
**Last Updated:** January 2026

---

## Document Index

| Doc ID | Document | Description |
|--------|----------|-------------|
| D51 | Local Development Setup | Prerequisites, install, run |
| D52 | Docker Compose Spec | Full stack deployment |
| D53 | Directory & Project Structure | Where everything lives |
| D54 | Dependency Matrix | All packages with versions |
| D55 | Health Check & Observability | Monitoring, logging |
| D56 | Troubleshooting Guide | Common issues and fixes |

---

## D51: Local Development Setup Guide

### Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.11+ | Runtime (Any-Agent requires 3.11+) |
| pip | Latest | Package management |
| Node.js | 18+ | Optional: for some MCP servers |
| Git | Latest | Source control |
| Docker | Latest | Optional: for containerized MCP servers |

### Step 1: Clone and Setup

```bash
# Clone repository
git clone https://github.com/your-org/multi-agent-orchestrator.git
cd multi-agent-orchestrator

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

### Step 2: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit with your API keys
nano .env  # or use your preferred editor
```

Required environment variables:
```bash
# At least one LLM provider
OPENAI_API_KEY=sk-...

# Optional providers
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
```

### Step 3: Create Configuration

```bash
# Copy example config
cp config.example.yaml config.yaml

# Edit configuration
nano config.yaml
```

Minimal config for testing:
```yaml
llms:
  default:
    provider: openai
    model: gpt-4o

agents:
  supervisor:
    kind: supervisor
    system_prompt: "You are a helpful assistant."
    tools: ["send_message"]
```

### Step 4: Run the System

```bash
# Start the server
python -m maos.main

# Or with specific config
python -m maos.main --config config.yaml

# Or with debug mode
DEBUG=true python -m maos.main
```

### Step 5: Verify Installation

```bash
# Health check
curl http://localhost:7777/health

# List agents
curl http://localhost:7777/agents

# Test chat
curl -X POST http://localhost:7777/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}]}'
```

### Development Workflow

```bash
# Run tests
pytest

# Run with auto-reload (development)
uvicorn maos.api:app --reload --port 7777

# Run linting
ruff check .

# Run type checking
mypy maos/
```

---

## D52: Docker Compose Specification

### docker-compose.yaml

```yaml
version: '3.8'

services:
  # Main orchestrator
  orchestrator:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "7777:7777"
    environment:
      - CONFIG_PATH=/app/config/config.yaml
      - API_HOST=0.0.0.0
      - API_PORT=7777
      - LOG_LEVEL=INFO
    env_file:
      - .env
    volumes:
      - ./config:/app/config:ro
      - ./data:/app/data
    depends_on:
      - mcp-knowledge
      - mcp-github
    networks:
      - agent-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7777/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # MCP Knowledge Server
  mcp-knowledge:
    build:
      context: ./mcp-servers/knowledge
      dockerfile: Dockerfile
    ports:
      - "8081:8080"
    environment:
      - KNOWLEDGE_DB_PATH=/data/knowledge.db
    volumes:
      - ./data/knowledge:/data
    networks:
      - agent-network

  # MCP GitHub Server
  mcp-github:
    build:
      context: ./mcp-servers/github
      dockerfile: Dockerfile
    ports:
      - "8089:8080"
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
    networks:
      - agent-network

  # External A2A Agent Host (optional)
  a2a-host:
    build:
      context: ./a2a-agents
      dockerfile: Dockerfile
    ports:
      - "9001:9001"
    environment:
      - HOST=0.0.0.0
      - PORT=9001
    networks:
      - agent-network

  # Ollama (optional, for local LLM)
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    networks:
      - agent-network
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

networks:
  agent-network:
    driver: bridge

volumes:
  ollama-data:
```

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY maos/ ./maos/
COPY config/ ./config/

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 7777

# Run application
CMD ["python", "-m", "maos.main"]
```

### Running with Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f orchestrator

# Stop all services
docker-compose down

# Rebuild after changes
docker-compose up -d --build
```

---

## D53: Directory & Project Structure

```
multi-agent-orchestrator/
├── maos/                          # Main package
│   ├── __init__.py
│   ├── main.py                    # Entry point
│   │
│   ├── config/                    # Configuration handling
│   │   ├── __init__.py
│   │   ├── loader.py              # ConfigLoader
│   │   ├── schema.py              # JSON Schema
│   │   └── models.py              # Pydantic models
│   │
│   ├── llm/                       # LLM integration
│   │   ├── __init__.py
│   │   ├── factory.py             # LLMFactory
│   │   ├── registry.py            # LLMRegistry
│   │   └── adapters/              # Provider adapters
│   │       ├── openai.py
│   │       ├── anthropic.py
│   │       ├── google.py
│   │       └── ollama.py
│   │
│   ├── mcp/                       # MCP integration
│   │   ├── __init__.py
│   │   ├── registry.py            # MCPRegistry
│   │   ├── connection.py          # MCPConnection
│   │   └── transports/            # Transport implementations
│   │       ├── stdio.py
│   │       └── http.py
│   │
│   ├── tools/                     # Tool handling
│   │   ├── __init__.py
│   │   ├── registry.py            # ToolRegistry
│   │   └── models.py              # Tool models
│   │
│   ├── skills/                    # Skills and skillsets
│   │   ├── __init__.py
│   │   ├── skill_registry.py      # SkillRegistry
│   │   └── skillset_registry.py   # SkillsetRegistry
│   │
│   ├── agents/                    # Agent handling
│   │   ├── __init__.py
│   │   ├── factory.py             # AgentFactory
│   │   ├── registry.py            # AgentRegistry
│   │   └── models.py              # Agent models
│   │
│   ├── a2a/                       # A2A integration
│   │   ├── __init__.py
│   │   ├── discovery.py           # A2ADiscovery
│   │   ├── client.py              # A2A client
│   │   ├── models.py              # A2A models
│   │   └── server/                # A2A server implementations
│   │       ├── host.py            # A2AHostServer
│   │       └── individual.py      # A2AIndividualServer
│   │
│   ├── graph/                     # LangGraph orchestration
│   │   ├── __init__.py
│   │   ├── factory.py             # GraphFactory
│   │   ├── state.py               # State schema
│   │   └── nodes/                 # Node implementations
│   │       ├── supervisor.py      # SupervisorNode
│   │       ├── worker.py          # NativeWorkerNode
│   │       └── external.py        # ExternalAgentNode
│   │
│   └── api/                       # API server
│       ├── __init__.py
│       ├── server.py              # FastAPI app
│       ├── routes/                # Route handlers
│       │   ├── chat.py
│       │   ├── agents.py
│       │   └── openai_compat.py
│       └── streaming.py           # Streaming helpers
│
├── mcp-servers/                   # MCP server implementations
│   ├── knowledge/
│   │   ├── server.py
│   │   └── Dockerfile
│   └── github/
│       ├── server.py
│       └── Dockerfile
│
├── a2a-agents/                    # A2A agent implementations
│   ├── analytics/
│   │   ├── agent.py
│   │   └── agent.json
│   └── ml/
│       ├── agent.py
│       └── agent.json
│
├── tests/                         # Test suite
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   ├── unit/                      # Unit tests
│   │   ├── test_config.py
│   │   ├── test_llm.py
│   │   └── ...
│   ├── integration/               # Integration tests
│   │   ├── test_mcp.py
│   │   ├── test_a2a.py
│   │   └── ...
│   └── e2e/                       # End-to-end tests
│       └── test_chat.py
│
├── config/                        # Configuration files
│   ├── config.yaml                # Main config
│   ├── config.example.yaml        # Example config
│   └── schema.json                # JSON Schema
│
├── docs/                          # Documentation
│   ├── design/                    # Design docs (this document set)
│   ├── api/                       # API documentation
│   └── guides/                    # How-to guides
│
├── scripts/                       # Utility scripts
│   ├── setup.sh                   # Setup script
│   ├── test.sh                    # Test runner
│   └── lint.sh                    # Linting
│
├── .env.example                   # Example environment
├── .gitignore
├── docker-compose.yaml
├── Dockerfile
├── pyproject.toml                 # Project metadata
├── requirements.txt               # Production dependencies
├── requirements-dev.txt           # Development dependencies
└── README.md
```

---

## D54: Dependency Matrix

### Production Dependencies

| Package | Version | Purpose | Notes |
|---------|---------|---------|-------|
| **Core** |
| `langgraph` | >=0.2.0 | Graph orchestration | |
| `langgraph-supervisor` | >=0.1.0 | Supervisor pattern | |
| `any-agent` | >=1.14.0 | Agent abstraction | With extras |
| `fastapi` | >=0.100.0 | API framework | |
| `uvicorn` | >=0.23.0 | ASGI server | With standard extras |
| **Protocols** |
| `mcp` | >=1.0.0 | MCP client/server | |
| `a2a-sdk` | >=0.3.0 | A2A client/server | |
| **LLM Providers** |
| `openai` | >=1.0.0 | OpenAI client | |
| `anthropic` | >=0.25.0 | Anthropic client | |
| `google-generativeai` | >=0.5.0 | Google AI client | |
| `langchain-openai` | >=0.1.0 | LangChain adapter | |
| `langchain-anthropic` | >=0.1.0 | LangChain adapter | |
| `langchain-google-genai` | >=0.1.0 | LangChain adapter | |
| `langchain-community` | >=0.1.0 | Ollama support | |
| **Supporting** |
| `pydantic` | >=2.0.0 | Data validation | |
| `httpx` | >=0.25.0 | Async HTTP client | |
| `pyyaml` | >=6.0 | YAML parsing | |
| `jsonschema` | >=4.0.0 | Schema validation | |
| `sse-starlette` | >=1.6.0 | SSE streaming | |
| `python-dotenv` | >=1.0.0 | Env loading | |
| `structlog` | >=23.0.0 | Structured logging | |

### Development Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | >=7.0.0 | Test framework |
| `pytest-asyncio` | >=0.21.0 | Async test support |
| `pytest-mock` | >=3.0.0 | Mocking |
| `respx` | >=0.20.0 | HTTPX mocking |
| `ruff` | >=0.1.0 | Linting + formatting |
| `mypy` | >=1.0.0 | Type checking |
| `pre-commit` | >=3.0.0 | Git hooks |

---

## D55: Health Check & Observability

### Health Endpoints

```python
# GET /health
{
    "status": "healthy",  # healthy, degraded, unhealthy
    "version": "1.0.0",
    "uptime_seconds": 3600,
    "components": {
        "llm_openai": {"status": "healthy"},
        "mcp_knowledge": {"status": "healthy"},
        "mcp_github": {"status": "degraded", "message": "High latency"},
        "a2a_analytics": {"status": "healthy"}
    }
}
```

### Logging Configuration

```python
# structlog configuration
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() if production else 
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(log_level),
)
```

### Log Format

```json
{
    "timestamp": "2026-01-02T10:30:00.000Z",
    "level": "info",
    "event": "chat_request",
    "request_id": "req-123",
    "user_message_length": 150,
    "worker": "research_agent",
    "duration_ms": 3500
}
```

### Metrics (Extension Point)

| Metric | Type | Description |
|--------|------|-------------|
| `requests_total` | Counter | Total requests |
| `request_duration_ms` | Histogram | Request latency |
| `worker_invocations` | Counter | Worker calls by name |
| `tool_calls` | Counter | Tool invocations |
| `llm_tokens_total` | Counter | LLM tokens used |
| `errors_total` | Counter | Errors by type |

---

## D56: Troubleshooting Guide

### Common Issues

#### 1. "No module named 'any_agent'"

**Cause:** Any-Agent not installed or wrong extras.

**Fix:**
```bash
pip install 'any-agent[langchain,openai]'
```

#### 2. "OPENAI_API_KEY not set"

**Cause:** Environment variable missing.

**Fix:**
```bash
export OPENAI_API_KEY=sk-...
# Or add to .env file
```

#### 3. "MCP connection failed"

**Cause:** MCP server not running or wrong config.

**Checks:**
```bash
# Check if server process is running
ps aux | grep mcp_server

# Test MCP server directly
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | \
  python -m mcp_server_knowledge
```

#### 4. "A2A discovery timeout"

**Cause:** External agent not reachable.

**Checks:**
```bash
# Check if agent is running
curl http://localhost:9001/.well-known/agent.json

# Check network connectivity
curl -v http://localhost:9001/
```

#### 5. "Max iterations exceeded"

**Cause:** Supervisor stuck in loop.

**Fixes:**
- Increase `graph.max_iterations` in config
- Check supervisor prompt for clear termination conditions
- Review worker responses for clarity

#### 6. "Tool call timeout"

**Cause:** MCP tool taking too long.

**Fixes:**
- Increase `tools.<name>.timeout_seconds`
- Check MCP server performance
- Add caching to slow tools

#### 7. "LLM rate limit"

**Cause:** Too many requests to LLM provider.

**Fixes:**
- Add delays between requests
- Use multiple API keys
- Switch to local Ollama for development

### Debug Mode

```bash
# Enable all debug logging
DEBUG=true \
DEBUG_LANGGRAPH=true \
DEBUG_MCP=true \
DEBUG_A2A=true \
python -m maos.main
```

### Getting Help

1. Check logs: `tail -f logs/maos.log`
2. Enable debug mode for detailed traces
3. Use `/health` endpoint to check component status
4. Review configuration with schema validation
5. Test components individually before integration

---

## Related Documents

- D27: Config Examples Catalog
- D28: Environment Variables
- D60-D65: Implementation Guides

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Architecture Team | Initial draft |
