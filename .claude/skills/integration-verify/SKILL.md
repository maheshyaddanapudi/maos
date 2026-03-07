---
name: integration-verify
description: Verify cross-module integration wiring in MAOS (LangGraph, MCP, A2A, API)
allowed-tools: Read, Glob, Grep, Bash
---

# Integration Verification

## Cross-Module Checks

1. **Config → Registry wiring**: Verify `initialize_system()` in `maos/main.py` creates all registries from config
2. **LLM → Agent wiring**: Verify `AgentFactory` resolves LLM adapters via `LLMRegistry`
3. **MCP → Tool wiring**: Verify `ToolRegistry.materialize()` connects to MCP servers
4. **Skill → Skillset → Agent wiring**: Verify skill/tool chain resolves correctly
5. **Graph → Worker wiring**: Verify `GraphFactory` creates nodes for all registered agents
6. **A2A → Graph wiring**: Verify discovered agents are added as graph nodes or tools

## Integration Test Commands

```bash
pytest tests/integration/ -v
pytest tests/integration/test_graph_integration.py -v
pytest tests/integration/test_toolchain.py -v
```

## Common Integration Issues

- MCP server connection timeouts (check `timeout_seconds` in config)
- Missing LLM adapter registrations (check `llms` section has all referenced names)
- External agent discovery failures (check `a2a.discovery.seeds` URLs)
- Graph compilation errors (check agent kinds and supervisor existence)
