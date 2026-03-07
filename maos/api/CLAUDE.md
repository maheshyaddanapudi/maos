# api/ — FastAPI REST Layer

Exposes MAOS functionality via HTTP with SSE streaming.

## Key Files
- `server.py` — `create_app()` factory with CORS config and route registration
- `models.py` — Request/Response Pydantic models (`ChatRequest`, `ChatResponse`, etc.)
- `streaming.py` — SSE streaming helpers for graph execution events
- `thread_id.py` — Thread ID generation and validation
- `routes/` — Endpoint handlers (chat, agents, health, tasks, conversations, OpenAI compat, LangGraph Studio)

## Conventions
- All route handlers are async
- SSE events: `chunk`, `tool_call`, `tool_result`, `input_required`, `done`
- `/chat/resume` resumes interrupted graphs via `Command(resume=...)`
- OpenAI-compatible endpoints at `/v1/chat/completions`
- CORS origins configured via `serving.api.cors_origins`
