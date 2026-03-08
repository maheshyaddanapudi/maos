# Plan: Integrate any-agent for Multi-Framework Worker Agents

## Current State

### What works today
- `GraphFactory.build()` creates worker agents using **hardcoded** `create_react_agent` from `langgraph.prebuilt` (line 212 of `graph/factory.py`)
- The `framework` field is defined in `AgentConfig` (accepts: `langchain`, `openai`, `google`, `smolagents`, `llamaindex`, `agno`, `tinyagent`) but is **stored and never read** at execution time
- LLM creation goes through `LLMFactory.create_chat_model()` which returns a `BaseChatModel` — LangChain-only
- Tools are converted to LangChain `BaseTool` via `_convert_to_langchain_tool()` in the graph factory
- The supervisor uses `langgraph-supervisor`'s `create_supervisor()` which expects agents as compiled `StateGraph` objects
- All of this works. 536 tests pass.

### What's broken
- `framework: openai` in config.yaml → silently ignored, agent uses LangChain anyway
- README promises "7+ frameworks via config" — fiction
- `any-agent` is not installed, not imported, not used

---

## Architecture Insight: The Key Constraint

The **supervisor** (`create_supervisor()`) expects each worker to be a **compiled LangGraph StateGraph**. This is non-negotiable — it's how `langgraph-supervisor` routes tasks.

Today, each worker is: `create_react_agent(model=langchain_model, tools=[], name="worker", prompt="...")`

`create_react_agent` returns a compiled `StateGraph`. The supervisor calls workers via handoff tools (`transfer_to_<worker>`), passing messages through the graph state.

**any-agent doesn't return a StateGraph.** It returns an `AnyAgent` instance with `.run()` / `.run_async()` methods that accept a string prompt and return an `AgentTrace`.

Therefore: **any-agent workers must be wrapped in a StateGraph node**, exactly like we already do for external A2A agents in `create_external_agent_graph()`.

---

## Design: Non-Breaking Integration

### Principle: `framework: langchain` stays on the fast path

When `framework: langchain` (the default), the current code path is used unchanged — `create_react_agent` with LangChain model + LangChain tools. Zero regression risk.

When `framework: openai|google|smolagents|llamaindex|agno|tinyagent`, we create the worker via `any-agent`, wrap it in a StateGraph node, and hand it to the supervisor just like an external agent.

### The integration point

In `GraphFactory.build()`, the worker creation loop (lines 196-219) currently does:

```python
for name, worker in self._agent_registry.get_workers():
    worker_model = self._llm_factory.create_chat_model(worker_llm_config)
    tools = self._get_worker_tools(worker.tool_ids)
    worker_agent = create_react_agent(model=worker_model, tools=tools, name=name, prompt=worker.system_prompt)
    worker_agents.append(worker_agent)
```

After this change:

```python
for name, worker in self._agent_registry.get_workers():
    if worker.framework == "langchain":
        # EXISTING PATH — unchanged
        worker_model = self._llm_factory.create_chat_model(worker_llm_config)
        tools = self._get_worker_tools(worker.tool_ids)
        worker_agent = create_react_agent(model=worker_model, tools=tools, name=name, prompt=worker.system_prompt)
    else:
        # NEW PATH — any-agent
        worker_agent = self._create_any_agent_worker(name, worker, worker_llm_config)
    worker_agents.append(worker_agent)
```

---

## Detailed Implementation Plan

### Step 1: Add `any-agent` dependency

**File: `pyproject.toml`**

Add to dependencies:
```toml
"any-agent[langchain]>=1.14.0",
```

Add new optional dependency group for extended framework support:
```toml
[project.optional-dependencies]
frameworks = [
    "any-agent[openai]>=1.14.0",
    "any-agent[google]>=1.14.0",
    "any-agent[smolagents]>=1.14.0",
    "any-agent[llama-index]>=1.14.0",
    "any-agent[agno]>=1.14.0",
]
```

Also add to mypy overrides:
```toml
"any_agent",
"any_agent.*",
```

**Why `any-agent[langchain]` in core deps?** Because any-agent's langchain adapter internally uses `create_react_agent` just like we do — it won't introduce conflicts. And it lets us use any-agent's tool loading for all frameworks consistently.

### Step 2: Create `AnyAgentWorkerWrapper` in graph factory

**File: `maos/graph/factory.py`**

Add a new function `create_any_agent_worker_graph()` that follows the exact same pattern as the existing `create_external_agent_graph()`:

```python
def create_any_agent_worker_graph(
    name: str,
    framework: str,
    model_id: str,
    system_prompt: str,
    tools: list[BaseTool],
    api_key: str | None = None,
    api_base: str | None = None,
    model_args: dict | None = None,
) -> StateGraph:
    """
    Create a LangGraph wrapper for an any-agent worker.

    This creates a graph node that:
    1. Receives messages from the supervisor
    2. Extracts the task from the last human/AI message
    3. Runs the any-agent agent with the task
    4. Returns the response as an AIMessage
    """
    from typing import TypedDict

    class AnyAgentState(TypedDict):
        messages: Annotated[list, add_messages]

    # Create the any-agent instance once at graph build time
    from any_agent import AgentConfig as AnyAgentConfig, AnyAgent

    # Map MAOS framework names to any-agent framework names
    FRAMEWORK_MAP = {
        "openai": "openai",
        "google": "google",
        "smolagents": "smolagents",
        "llamaindex": "llama_index",
        "agno": "agno",
        "tinyagent": "tinyagent",
    }

    any_framework = FRAMEWORK_MAP.get(framework, framework)

    # Convert LangChain tools to callables for any-agent
    tool_callables = _convert_langchain_tools_to_callables(tools)

    agent_config = AnyAgentConfig(
        model_id=model_id,
        instructions=system_prompt,
        tools=tool_callables,
        api_key=api_key,
        api_base=api_base,
        model_args=model_args or {},
    )

    any_agent = AnyAgent.create(any_framework, agent_config)

    async def call_any_agent(state: AnyAgentState) -> dict:
        """Call the any-agent worker."""
        messages = state.get("messages", [])

        # Extract task from latest message (same pattern as external agent wrapper)
        task = ""
        for msg in reversed(messages):
            if hasattr(msg, "content") and hasattr(msg, "type"):
                if msg.type == "human":
                    task = msg.content
                    break
            elif isinstance(msg, dict) and msg.get("role") == "user":
                task = msg.get("content", "")
                break

        if not task:
            return {"messages": [AIMessage(content="No task provided.", name=name)]}

        try:
            trace = await any_agent.run_async(task)
            content = str(trace.final_output) if trace.final_output else "No response."
            return {"messages": [AIMessage(content=content, name=name)]}
        except Exception as e:
            logger.error("any_agent_worker_failed", agent=name, framework=framework, error=str(e))
            return {"messages": [AIMessage(content=f"Agent '{name}' encountered an error.", name=name)]}

    graph = StateGraph(AnyAgentState)
    graph.add_node("call", call_any_agent)
    graph.set_entry_point("call")
    graph.add_edge("call", END)

    return graph.compile(name=name)
```

### Step 3: Helper to convert LangChain tools to callables

**File: `maos/graph/factory.py`**

any-agent expects tools as plain Python callables (functions). We already have MAOS tools converted to LangChain `StructuredTool`. We need to unwrap them back to callables:

```python
def _convert_langchain_tools_to_callables(tools: list[BaseTool]) -> list:
    """Convert LangChain tools to plain callables for any-agent."""
    callables = []
    for tool in tools:
        # StructuredTool wraps a coroutine - extract it
        if hasattr(tool, "coroutine") and tool.coroutine:
            func = tool.coroutine
        elif hasattr(tool, "func") and tool.func:
            func = tool.func
        else:
            # Wrap the tool's invoke as a callable
            async def make_wrapper(t=tool):
                async def wrapper(**kwargs):
                    return await t.ainvoke(kwargs)
                wrapper.__name__ = t.name
                wrapper.__doc__ = t.description
                return wrapper
            func = asyncio.get_event_loop().run_until_complete(make_wrapper())

        # Preserve metadata for any-agent's tool introspection
        if not hasattr(func, "__name__"):
            func.__name__ = tool.name
        if not hasattr(func, "__doc__") or not func.__doc__:
            func.__doc__ = tool.description

        callables.append(func)
    return callables
```

### Step 4: Wire into `GraphFactory.build()`

**File: `maos/graph/factory.py`**

Modify the worker creation loop to branch on framework:

```python
def build(self) -> StateGraph:
    # ... existing supervisor setup ...

    worker_agents = []
    for name, worker in self._agent_registry.get_workers():
        worker_llm_config = self._config.llms.get(worker.llm_name or "default")
        if not worker_llm_config:
            logger.warning(f"LLM config not found for worker {name}, using default")
            worker_llm_config = self._config.llms.get("default")
        if not worker_llm_config:
            raise ValueError(f"No LLM config found for worker {name}")

        tools = self._get_worker_tools(worker.tool_ids)

        if worker.framework == "langchain":
            # Existing fast path — LangGraph native
            worker_model = self._llm_factory.create_chat_model(worker_llm_config)
            worker_agent = create_react_agent(
                model=worker_model,
                tools=tools if tools else [],
                name=name,
                prompt=worker.system_prompt,
            )
        else:
            # any-agent path
            worker_agent = self._create_any_agent_worker(
                name=name,
                worker=worker,
                llm_config=worker_llm_config,
                tools=tools,
            )

        worker_agents.append(worker_agent)
        logger.debug("created_worker_agent", name=name, framework=worker.framework, has_tools=bool(tools))

    # ... rest unchanged (external agents, supervisor creation) ...
```

### Step 5: Build `model_id` from MAOS LLM config

**File: `maos/graph/factory.py`**

any-agent uses `model_id` strings like `"openai/gpt-4o"` or `"anthropic/claude-3-5-sonnet"`. We need to map from MAOS's `LLMConfig`:

```python
def _build_any_agent_model_id(self, llm_config: LLMConfig) -> str:
    """Build an any-agent model_id from MAOS LLM config.

    any-agent uses litellm-style model IDs: "provider/model"
    """
    provider_map = {
        "openai": "",          # OpenAI models don't need prefix
        "anthropic": "anthropic/",
        "google": "gemini/",
        "ollama": "ollama/",
        "openai_compatible": "",
        "azure_openai": "azure/",
    }
    prefix = provider_map.get(llm_config.provider, "")
    return f"{prefix}{llm_config.model}"
```

### Step 6: The `_create_any_agent_worker` method

**File: `maos/graph/factory.py`**

```python
def _create_any_agent_worker(
    self,
    name: str,
    worker: WorkerAgent,
    llm_config: LLMConfig,
    tools: list[BaseTool],
) -> Any:
    """Create a worker agent via any-agent, wrapped in a StateGraph."""
    model_id = self._build_any_agent_model_id(llm_config)

    # Get API key for the provider
    api_key = None
    if llm_config.api_key_env:
        api_key = os.environ.get(llm_config.api_key_env)

    return create_any_agent_worker_graph(
        name=name,
        framework=worker.framework,
        model_id=model_id,
        system_prompt=worker.system_prompt,
        tools=tools,
        api_key=api_key,
        api_base=llm_config.base_url,
        model_args={"temperature": llm_config.temperature},
    )
```

### Step 7: Graceful degradation if framework not installed

If a user sets `framework: openai` but hasn't installed `any-agent[openai]`, we should fail fast with a clear error at startup, not at runtime.

**File: `maos/graph/factory.py`** — in `_create_any_agent_worker`:

```python
try:
    from any_agent import AgentConfig as AnyAgentConfig, AnyAgent
except ImportError:
    raise ImportError(
        f"Agent '{name}' uses framework '{worker.framework}' which requires any-agent. "
        f"Install it with: pip install 'any-agent[{worker.framework}]'"
    )
```

### Step 8: Update config validation

**File: `maos/config/models.py`** — in `Config.validate_references()`:

Add a check that warns if non-langchain frameworks are used:

```python
# Check framework availability
for agent_name, agent in self.agents.items():
    if agent.kind == AgentKind.NATIVE_WORKER and agent.framework != "langchain":
        try:
            import any_agent  # noqa: F401
        except ImportError:
            errors.append(
                f"Agent '{agent_name}' uses framework '{agent.framework}' "
                f"which requires any-agent. Install: pip install 'any-agent[{agent.framework}]'"
            )
            break  # One warning is enough
```

### Step 9: Tests

**File: `tests/unit/test_any_agent_integration.py`** — NEW

```python
"""Tests for any-agent framework integration."""

class TestAnyAgentWorkerGraph:
    """Test creating workers via any-agent."""

    # Test that framework="langchain" still uses create_react_agent (fast path)
    # Test that framework="openai" creates an any-agent wrapper graph
    # Test that the wrapper graph has correct state schema
    # Test task extraction from messages
    # Test error handling when any-agent fails
    # Test graceful error when any-agent not installed
    # Test model_id building from LLMConfig
    # Test tool conversion from LangChain to callables
```

Mock `AnyAgent.create()` and `agent.run_async()` — no real LLM calls needed.

### Step 10: Update pyproject.toml mypy and README

- Add `any_agent` to mypy ignore_missing_imports
- README: no changes needed (it already promises this; now it's true)
- Update config.example.yaml with a commented example showing `framework: openai`

---

## Files Changed (Summary)

| File | Change Type | Description |
|------|-------------|-------------|
| `pyproject.toml` | MODIFY | Add `any-agent` dependency + `frameworks` extra + mypy config |
| `maos/graph/factory.py` | MODIFY | Add framework branching, `create_any_agent_worker_graph()`, `_convert_langchain_tools_to_callables()`, `_build_any_agent_model_id()`, `_create_any_agent_worker()` |
| `maos/config/models.py` | MODIFY | Add framework availability check in `validate_references()` |
| `config.example.yaml` | MODIFY | Add commented `framework: openai` example |
| `tests/unit/test_any_agent_integration.py` | NEW | Tests for any-agent wrapper, tool conversion, model_id mapping |

---

## What Does NOT Change

- `maos/agents/factory.py` — untouched (framework already stored on WorkerAgent)
- `maos/agents/models.py` — untouched (framework field already exists)
- `maos/llm/factory.py` — untouched (still used for LangChain fast path)
- `maos/llm/adapters/langchain_adapter.py` — untouched
- `maos/api/` — untouched (no API changes)
- `maos/a2a/` — untouched
- Supervisor creation — untouched (all workers are still compiled StateGraphs)
- All existing tests — should still pass unchanged

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| any-agent version breaks | Pin `>=1.14.0,<2.0.0` |
| Tool conversion loses schema | Test with real MCP tools in integration test |
| any-agent .run_async() blocks | Already async, runs in LangGraph's async executor |
| Performance regression for langchain | Zero — fast path is unchanged, no imports triggered |
| Import time for any_agent | Lazy import — only imported when non-langchain framework used |
| any-agent MCP tool conflict | We pass plain callables, not MCP configs — no conflict |

---

## User Experience After Implementation

```yaml
# config.yaml — This Just Works
agents:
  supervisor:
    kind: supervisor
    llm: default
    system_prompt: "Route tasks to workers."

  # Uses LangChain (existing fast path)
  researcher:
    kind: native_worker
    framework: langchain        # or omit — langchain is default
    llm: default
    system_prompt: "You research topics."

  # Uses OpenAI Agents SDK via any-agent
  writer:
    kind: native_worker
    framework: openai
    llm: default
    system_prompt: "You write content."

  # Uses Google ADK via any-agent
  analyst:
    kind: native_worker
    framework: google
    llm: default
    system_prompt: "You analyze data."
```

All three workers appear to the supervisor as identical compiled StateGraphs. The supervisor routes to them using `transfer_to_researcher`, `transfer_to_writer`, `transfer_to_analyst` — completely transparent.
