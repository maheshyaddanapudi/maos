# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MAOS (Multi-Agent Orchestration System) is a **config-driven multi-agent orchestration system** combining:
- **LangGraph Supervisor** for intelligent routing between agents
- **LangChain** adapters for LLM providers (OpenAI, Anthropic, Google, Ollama)
- **MCP** (Model Context Protocol) for tool integration
- **A2A** (Agent-to-Agent) for external agent communication
- **FastAPI** REST API with SSE streaming and OpenAI-compatible endpoints

The system is fully config-driven: agents, tools, skills, and LLM providers are defined in YAML and wired up at startup without code changes. See `config.example.yaml` for the full configuration reference.

68 design documents in `docs/` contain architectural specifications and Mermaid diagrams.

## Common Commands

```bash
# Install (editable with dev deps)
pip install -e ".[dev]"

# Run the server
maos serve --config config.example.yaml
# or: python -m maos serve --config config.example.yaml

# Validate a config file
maos validate --config config.example.yaml

# Run all tests (coverage enabled by default via pyproject.toml)
pytest

# Run a single test file
pytest tests/unit/test_config.py

# Run tests by marker
pytest -m unit
pytest -m integration
pytest -m e2e

# Run tests matching a pattern
pytest -k "test_supervisor"

# Lint
ruff check maos/ tests/
ruff format --check maos/ tests/

# Type check
mypy maos/
```

## Architecture

### Request Flow

User request → FastAPI (`api/routes/chat.py`) → LangGraph supervisor graph (`graph/factory.py`) → Supervisor node routes to worker agents → Workers execute with tools via MCP → Response streamed back via SSE.

Human-in-the-loop: The supervisor can call `send_message` tool, which triggers `langgraph.types.interrupt()` to pause the graph. The client receives an `input_required` SSE event and resumes via `POST /chat/resume` using `Command(resume=...)`.

### Module Dependency Chain

```
config/ → llm/ → mcp/ → tools/ → skills/ → agents/ → graph/ → api/
```

Each layer builds on the previous. The `main.py` entry point initializes them in this order during startup (see `initialize_system()`).

### Key Patterns

- **Registry pattern everywhere**: `LLMRegistry`, `MCPRegistry`, `ToolRegistry`, `SkillRegistry`, `AgentRegistry` — each holds named instances created from config at startup.
- **Graph factory** (`graph/factory.py`): Uses `langgraph-supervisor` to build a `StateGraph` with the supervisor + worker agents as nodes. The `create_graph()` function is also the LangGraph Studio entry point (see `langgraph.json`).
- **Checkpointer** (`graph/checkpointer.py`): Supports memory, SQLite, or PostgreSQL backends for conversation persistence. Selected via `config.graph.persistence`.
- **Multiple API interfaces**: Native REST (`/chat`), OpenAI-compatible (`/v1/chat/completions`), LangGraph Studio (`/assistants`, `/threads`, `/runs`), all served from the same FastAPI app.
- **Thread ID resolution** (`api/thread_id.py`): Unifies thread IDs across different API interfaces (path params, headers, body fields).

### External Agents (A2A)

External agents are defined in config under `agents` with `kind: external`. At startup, managed external agents (like `title_generator`) are launched as separate HTTP servers. The `a2a/discovery.py` module discovers agent cards, and `a2a/client.py` communicates with them. External agents appear as nodes in the LangGraph supervisor graph.

## Technical Constraints

- **Python >= 3.11** required
- **All I/O must be async** — never use blocking calls in the event loop
- **Pydantic v2** for all data models
- **Return new state dicts from graph nodes** — never mutate state in place
- **Line length: 100** (ruff config, E501 ignored)
- **pytest-asyncio mode: auto** — async test functions work without explicit markers

## Key Files for Understanding the System

- `maos/main.py` — CLI entry point, system initialization and shutdown lifecycle
- `maos/config/models.py` — All Pydantic config models (root `Config` class)
- `maos/graph/factory.py` — Builds the LangGraph supervisor graph from config
- `maos/graph/state.py` — `GraphState` TypedDict used by all graph nodes
- `maos/api/routes/chat.py` — Main chat endpoints with streaming support
- `maos/api/streaming.py` — SSE event formatting and interrupt handling
- `config.example.yaml` — Complete configuration reference with all options
- `docs/D10-D24-module-specifications.md` — Module interface contracts
