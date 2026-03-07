---
paths:
  - "maos/graph/**/*.py"
---

# LangGraph State Rules

- `GraphState` is a `TypedDict` — never mutate it in place.
- Node functions must return new state dicts with updated fields.
- Messages use `Annotated[list, add_messages]` for automatic accumulation.
- Use `interrupt()` from `langgraph.types` for human-in-the-loop pauses.
- `max_iterations` in `GraphConfig` guards against infinite loops.
- The supervisor node decides routing; workers execute and return results.
