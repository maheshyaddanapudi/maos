# agents/ — Agent Management

Creates and manages agent executors from configuration.

## Key Files
- `models.py` — Agent type definitions
- `factory.py` — `AgentFactory` creates agent executors with LLM + tools + system prompt
- `registry.py` — `AgentRegistry` builds all agents from config, handles supervisor/worker ordering
- `executor.py` — Agent execution logic

## Conventions
- Agents are created from `AgentConfig` which specifies `kind` (supervisor/native_worker/external)
- `framework` field selects the LangChain backend (langchain, openai, google, etc.)
- Agents receive tools via skillsets or direct tool references
- External agents are managed via A2A protocol
