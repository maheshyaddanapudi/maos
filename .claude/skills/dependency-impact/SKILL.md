---
name: dependency-impact
description: Analyze impact of changes across MAOS module dependencies
allowed-tools: Read, Glob, Grep
---

# Dependency Impact Analysis

## Module Dependency Graph

```
config ← (all modules)
llm ← agents, graph
mcp ← tools
tools ← skills ← agents
agents ← graph
graph ← api
a2a ← agents, graph
api → (exposes all)
```

## Analysis Steps

1. Identify which module(s) the change touches
2. Trace downstream dependents using the dependency graph above
3. Check for breaking changes in Protocol/interface definitions (`base.py` files)
4. List affected test files that need updating
5. Check config model changes that could break existing YAML configs

## Key Files to Check

- `maos/llm/base.py` — LLMAdapter protocol (changes affect all LLM consumers)
- `maos/config/models.py` — Config schema (changes affect all config consumers)
- `maos/graph/state.py` — GraphState (changes affect all graph nodes)
- `maos/tools/models.py` — Tool models (changes affect skills and agents)
