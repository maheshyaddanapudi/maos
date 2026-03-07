# MAOS Repository Map

## Project Structure

```
maos/                          # Root package
├── __init__.py
├── __main__.py                # python -m maos entry
├── main.py                    # CLI entry point (serve, interactive, validate)
│
├── config/                    # Configuration layer
│   ├── models.py              # Pydantic v2 config models (Config, LLMConfig, AgentConfig, etc.)
│   └── loader.py              # YAML/JSON config loading and validation
│
├── llm/                       # LLM abstraction layer
│   ├── base.py                # LLMAdapter protocol
│   ├── factory.py             # LLMFactory — creates LangChain ChatModel instances
│   ├── registry.py            # LLMRegistry — name→adapter mapping
│   └── adapters/
│       └── langchain_adapter.py  # Unified LangChain adapter (OpenAI, Anthropic, Google, Ollama)
│
├── mcp/                       # MCP (Model Context Protocol) integration
│   ├── official_client.py     # MCP client using official SDK
│   └── registry.py            # MCPRegistry — manages MCP server connections
│
├── tools/                     # Tool management
│   ├── models.py              # Tool, ToolCall, ToolResult models
│   └── registry.py            # ToolRegistry — materializes tools from MCP servers
│
├── skills/                    # Skill & Skillset grouping
│   ├── models.py              # Skill, Skillset models
│   └── registry.py            # SkillRegistry, SkillsetRegistry
│
├── agents/                    # Agent management
│   ├── models.py              # Agent type models
│   ├── factory.py             # AgentFactory — creates agent executors
│   ├── registry.py            # AgentRegistry — builds and stores agents
│   └── executor.py            # Agent execution logic
│
├── graph/                     # LangGraph orchestration
│   ├── state.py               # GraphState TypedDict
│   ├── factory.py             # GraphFactory — builds and compiles the LangGraph
│   └── checkpointer.py        # Checkpointer setup (Memory, SQLite, Postgres)
│
├── a2a/                       # Agent-to-Agent protocol
│   ├── models.py              # AgentCard, DiscoveredAgent models
│   ├── discovery.py           # A2ADiscovery — finds external agents
│   ├── client.py              # A2AClient — communicates with external agents
│   ├── agents/
│   │   ├── base.py            # ExternalAgentServer base class
│   │   └── title_generator.py # Built-in title generator agent
│   └── server/
│       ├── host.py            # A2A host server
│       └── individual.py      # Individual agent server
│
└── api/                       # FastAPI REST layer
    ├── server.py              # FastAPI app factory
    ├── models.py              # Request/Response Pydantic models
    ├── streaming.py           # SSE streaming helpers
    ├── thread_id.py           # Thread ID generation and validation
    └── routes/
        ├── __init__.py        # Route registration
        ├── chat.py            # POST /chat, /chat/resume
        ├── agents.py          # GET /agents
        ├── health.py          # GET /health
        ├── tasks.py           # Task management endpoints
        ├── conversations.py   # Conversation history endpoints
        ├── openai_compat.py   # OpenAI-compatible API endpoints
        └── langgraph_studio.py # LangGraph Studio integration endpoints

tests/                         # Test suite
├── conftest.py                # Shared fixtures
├── mocks/
│   ├── llm.py                 # Mock LLM adapters
│   └── mcp.py                 # Mock MCP servers
├── unit/                      # Unit tests
│   ├── test_config.py
│   ├── test_llm.py
│   ├── test_graph.py
│   ├── test_api.py
│   ├── test_conversations.py
│   ├── test_openai_compat.py
│   ├── test_thread_id.py
│   └── test_langgraph_studio.py
├── integration/               # Integration tests
│   ├── test_graph_integration.py
│   └── test_toolchain.py
├── e2e/                       # End-to-end tests
│   ├── test_chat_e2e.py
│   ├── test_full_stack_e2e.py
│   └── test_real_api_e2e.py
└── mcp_servers/
    └── test_tools_server.py   # Test MCP server

docs/                          # Design documentation (68 documents)
├── D01-executive-summary.md
├── D02-architecture-vision-and-goals.md
├── D03-glossary-and-terminology.md
├── D06-component-overview-c4-l3.md
├── D07-data-flow-architecture.md
├── D10-D24-module-specifications.md
├── D25-master-config-schema.md
├── D26-config-reference-guide.md
├── D29-D33-api-interface-specifications.md
├── D34-D44-sequence-and-state-diagrams.md
├── D45-D50-data-models.md
├── D51-D56-setup-and-operations.md
├── D53-directory-project-structure.md
├── D57-D59-extension-points-and-roadmap.md
├── D60-D65-implementation-guides.md
├── D66-D68-testing-documentation.md
└── ...
```

## Key Data Flow

```
User Request
  → FastAPI /chat endpoint
    → LangGraph compiled graph
      → Supervisor node (routes via LLM)
        → Worker node (executes via AgentFactory)
          → Tools (via MCP servers)
        → External agent node (via A2A client)
      → Supervisor evaluates result
        → Route to another worker, or
        → Return final response to user
    → SSE stream back to client
```

## Module Dependencies

```
config ← (all modules read config)
llm ← agents, graph
mcp ← tools
tools ← skills ← agents
agents ← graph
graph ← api
a2a ← agents, graph
api → (exposes everything via HTTP)
```
