---
paths:
  - "maos/**/*.py"
---

# Async Python Rules

- All I/O operations MUST use `async/await`. Never use synchronous I/O in library code.
- Use `asyncio` primitives for concurrency (gather, create_task, etc.).
- Never call `time.sleep()` — use `asyncio.sleep()` instead.
- External HTTP calls must use `httpx.AsyncClient`, not `requests`.
- MCP connections, LLM invocations, and A2A calls are all async.
