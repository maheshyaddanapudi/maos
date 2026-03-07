---
paths:
  - "maos/api/**/*.py"
---

# API Route Rules

- All route handlers must be `async def`.
- Use Pydantic models for request/response validation.
- SSE streaming uses `sse-starlette` with event types: `chunk`, `tool_call`, `tool_result`, `input_required`, `done`.
- Thread IDs must be validated before use.
- CORS is configured via `serving.api.cors_origins` — never hardcode origins.
- OpenAI-compatible endpoints mirror the `/v1/chat/completions` spec.
