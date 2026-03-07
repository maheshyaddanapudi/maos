# MAOS Module Reference

## config

**Purpose**: Load and validate YAML/JSON configuration into typed Pydantic models.

| File | Key Classes | Description |
|------|-------------|-------------|
| `models.py` | `Config`, `LLMConfig`, `AgentConfig`, `MCPServerConfig`, `ToolConfig`, `SkillConfig`, `SkillsetConfig`, `GraphConfig`, `A2AConfig`, `ServingConfig` | Root config and all nested models |
| `loader.py` | `ConfigLoader` | Loads YAML/JSON, validates, returns `Config` |

## llm

**Purpose**: Abstraction layer over LLM providers using LangChain adapters.

| File | Key Classes | Description |
|------|-------------|-------------|
| `base.py` | `LLMAdapter` (Protocol) | Interface for LLM interaction |
| `factory.py` | `LLMFactory` | Creates LangChain ChatModel from `LLMConfig` |
| `registry.py` | `LLMRegistry` | Name-based adapter lookup |
| `adapters/langchain_adapter.py` | `LangChainAdapter` | Unified adapter wrapping LangChain chat models |

**Supported providers**: OpenAI, Anthropic, Google, Ollama, OpenAI-compatible, Azure OpenAI.

## mcp

**Purpose**: Connect to MCP (Model Context Protocol) servers for tool access.

| File | Key Classes | Description |
|------|-------------|-------------|
| `official_client.py` | `OfficialMCPClient` | Client using the official MCP SDK |
| `registry.py` | `MCPRegistry` | Manages connections to multiple MCP servers |

**Supported transports**: stdio, HTTP, SSE.

## tools

**Purpose**: Materialize MCP tools into callable tool objects.

| File | Key Classes | Description |
|------|-------------|-------------|
| `models.py` | `Tool`, `ToolCall`, `ToolResult` | Tool data models |
| `registry.py` | `ToolRegistry` | Materializes and stores tools from MCP servers |

## skills

**Purpose**: Group tools into skills and skills into skillsets for agent assignment.

| File | Key Classes | Description |
|------|-------------|-------------|
| `models.py` | `Skill`, `Skillset` | Skill grouping models |
| `registry.py` | `SkillRegistry`, `SkillsetRegistry` | Build and query skill/skillset trees |

## agents

**Purpose**: Create and manage agent executors.

| File | Key Classes | Description |
|------|-------------|-------------|
| `models.py` | Agent type definitions | Agent model types |
| `factory.py` | `AgentFactory` | Creates agent executors from config |
| `registry.py` | `AgentRegistry` | Builds all agents, manages supervisor/worker ordering |
| `executor.py` | Agent execution logic | Runs agent with tools and LLM |

## graph

**Purpose**: Build and compile the LangGraph orchestration graph.

| File | Key Classes | Description |
|------|-------------|-------------|
| `state.py` | `GraphState` (TypedDict) | Graph state with messages, routing info |
| `factory.py` | `GraphFactory` | Builds LangGraph with supervisor + worker nodes |
| `checkpointer.py` | Checkpointer setup | Memory, SQLite, or Postgres persistence |

## a2a

**Purpose**: Agent-to-Agent protocol for external agent discovery and communication.

| File | Key Classes | Description |
|------|-------------|-------------|
| `models.py` | `AgentCard`, `DiscoveredAgent` | A2A data models |
| `discovery.py` | `A2ADiscovery` | Discovers agents from seed URLs |
| `client.py` | `A2AClient` | Sends tasks to external agents |
| `agents/base.py` | `ExternalAgentServer` | Base class for hosting agents as A2A servers |
| `agents/title_generator.py` | `TitleGeneratorAgent` | Built-in title generator |
| `server/host.py` | A2A host server | Hosts multiple agent endpoints |
| `server/individual.py` | Individual agent server | Single agent endpoint |

## api

**Purpose**: FastAPI REST API exposing MAOS functionality.

| File | Key Classes | Description |
|------|-------------|-------------|
| `server.py` | `create_app()` | FastAPI app factory with CORS, routes |
| `models.py` | `ChatRequest`, `ChatResponse`, etc. | Request/response Pydantic models |
| `streaming.py` | SSE helpers | Server-Sent Events streaming |
| `thread_id.py` | Thread ID utils | Generation and validation |
| `routes/chat.py` | `/chat`, `/chat/resume` | Chat and resume endpoints |
| `routes/agents.py` | `/agents` | List available agents |
| `routes/health.py` | `/health` | Health check |
| `routes/tasks.py` | Task endpoints | Task management |
| `routes/conversations.py` | Conversation endpoints | History and management |
| `routes/openai_compat.py` | OpenAI-compatible API | `/v1/chat/completions` etc. |
| `routes/langgraph_studio.py` | LangGraph Studio | Studio integration endpoints |
