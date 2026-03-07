# CLAUDE.md — MAOS (Multi-Agent Orchestration System)

## Project Overview

MAOS is a config-driven multi-agent orchestration system combining:
- **LangGraph** for supervisor-based routing
- **LangChain** for LLM adapters
- **MCP** (Model Context Protocol) for tool integration
- **A2A** (Agent-to-Agent) for external agent communication
- **FastAPI** for REST API with SSE streaming

**Status**: Greenfield / Alpha (v0.1.0)
**Python**: >= 3.11 | **Build**: hatchling | **Linter**: ruff | **Types**: mypy

## Quick Commands

```bash
# Install
pip install -e ".[dev]"

# Test (all)
pytest

# Test (unit only)
pytest tests/unit/

# Lint
ruff check maos/ tests/

# Format
ruff format maos/ tests/

# Type check
mypy maos/

# Run server
maos serve -c config.yaml

# Validate config
maos validate -c config.yaml
```

## Architecture

```
User → FastAPI → LangGraph (Supervisor → Workers → MCP Tools / A2A Agents) → SSE Response
```

**Key modules**: `config/` (Pydantic models + YAML loading), `llm/` (LangChain adapters), `mcp/` (MCP client), `tools/` (tool registry), `skills/` (skill grouping), `agents/` (agent factory + registry), `graph/` (LangGraph factory + state), `a2a/` (agent-to-agent), `api/` (FastAPI routes + streaming).

See `docs/architecture/repo-map.md` for full structure and `docs/architecture/module-reference.md` for module details.

## Design Documentation

68 design documents live in `docs/`. Key references:
- **D01**: Executive summary
- **D02**: Architecture vision
- **D06**: Component overview (C4 L3)
- **D07**: Data flow architecture
- **D10-D24**: Module specifications (interfaces, protocols)
- **D25-D28**: Configuration schema and examples
- **D29-D33**: API interface specifications
- **D45-D50**: Data models
- **D66-D68**: Testing documentation

**The design docs are the source of truth.** When in doubt, read the relevant doc.

## Code Conventions

- **Async everywhere**: All I/O must use `async/await`. Never block the event loop.
- **Pydantic v2**: All data models use Pydantic v2 with `Field()` descriptors.
- **Protocol classes**: Interfaces defined with `typing.Protocol` and `@runtime_checkable`.
- **Immutable state**: Graph nodes return new state dicts; never mutate in place.
- **Structured logging**: Use `structlog` throughout. No `print()` in library code.
- **Config-driven**: Agent behavior is defined in YAML config, not hardcoded.
- **Line length**: 100 chars (ruff configured).
- **Test markers**: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`.
- **Async tests**: `asyncio_mode = "auto"` in pyproject.toml — no need for `@pytest.mark.asyncio`.

## Testing Strategy

- **Unit tests** (`tests/unit/`): Test individual modules in isolation with mocks.
- **Integration tests** (`tests/integration/`): Test module interactions (graph + agents, tools + MCP).
- **E2E tests** (`tests/e2e/`): Full stack tests with real or mock LLMs.
- **Mock infrastructure** (`tests/mocks/`): `MockLLM`, `MockMCPServer` for testing without external services.
- **Test MCP servers** (`tests/mcp_servers/`): Actual MCP servers for integration testing.

## Task Delegation

Map tasks to the appropriate agent based on the work required:

| Task Type | Agent | Execution |
|-----------|-------|-----------|
| Feature planning, architecture decisions, impact analysis | `planner` | Foreground |
| Code implementation, refactoring, bug fixes | `implementer` | Foreground |
| Integration wiring, cross-module compatibility, A2A/MCP issues | `integration-specialist` | Foreground |
| Writing/updating tests, coverage analysis | `test-engineer` | Foreground |
| Code review, quality checks | `reviewer` | Background |
| Security scanning, vulnerability assessment | `security-auditor` | Background |

### Workflow Chain (New Feature)

```
planner → implementer → integration-specialist → test-engineer → reviewer
```

For bug fixes, use a shorter chain:
```
planner → implementer → test-engineer → reviewer
```

### Post-Review Decision Gate

After the `reviewer` agent completes, evaluate its structured verdict:

```
IF verdict == "APPROVE":
    → Task is complete. Report results to user.
IF verdict == "REQUEST_CHANGES":
    → Check current remediation cycle count against max_review_remediate_cycles (default: 2)
    → IF cycles_remaining > 0:
        → Route critical findings back to `implementer` with Fix instructions
        → Re-run `test-engineer` to verify fixes
        → Re-run `reviewer` for re-evaluation
        → Increment cycle count
    → IF cycles_remaining == 0:
        → Stop auto-remediation
        → Report remaining findings to user for manual decision
```

The `max_review_remediate_cycles` value is configured in `.claude/workflow-config.yml`.

**Subagent constraint**: Subagents cannot spawn other subagents. The reviewer flags issues; the main agent orchestrates remediation.

## Important Warnings

- **Do not hardcode API keys**. Use `api_key_env` in config to reference environment variables.
- **Do not mutate `GraphState`** directly. Return new dicts from node functions.
- **Do not use synchronous I/O** in any module that runs within the async event loop.
- **Validate all config cross-references** before starting the system (use `Config.validate_references()`).
- **Thread safety**: Registries may be accessed concurrently — use appropriate patterns.
