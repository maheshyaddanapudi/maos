# graph/ — LangGraph Orchestration

Builds and compiles the LangGraph supervisor graph.

## Key Files
- `state.py` — `GraphState` TypedDict with `Annotated[list, add_messages]` for message accumulation
- `factory.py` — `GraphFactory` builds the graph: supervisor node + worker nodes + external agent nodes. Uses `langgraph-supervisor` package.
- `checkpointer.py` — Creates checkpointers (MemorySaver, SQLite, Postgres) from config

## Conventions
- Never mutate `GraphState` — return new state dicts from node functions
- The supervisor uses `send_message` tool + `interrupt()` for human-in-the-loop
- `max_iterations` guards against infinite routing loops
- Worker nodes are created from `AgentRegistry` entries
