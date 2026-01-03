# D26: Config Reference Guide

## Config-Driven Multi-Agent Orchestration System

**Document ID:** D26  
**Version:** 1.0  
**Status:** Draft  
**Last Updated:** January 2026

---

## 1. Overview

This document provides detailed reference documentation for every configuration field in the Multi-Agent Orchestration System. For each field, we specify the type, default value, constraints, and usage examples.

---

## 2. Top-Level Structure

```yaml
llms: {}           # Required - LLM provider configurations
mcp_servers: {}    # Optional - MCP server connections
tools: {}          # Optional - Tool definitions
skills: {}         # Optional - Skill groupings
skillsets: {}      # Optional - Skillset groupings
agents: {}         # Required - Agent definitions
native_workers: {} # Optional - Native worker options
a2a: {}            # Optional - A2A discovery/import
graph: {}          # Optional - Graph execution settings
serving: {}        # Optional - API/UI settings
```

---

## 3. LLMs Section

### 3.1 Overview

```yaml
llms:
  <name>:
    provider: <provider_type>
    model: <model_id>
    # ... additional options
```

### 3.2 Field Reference

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `provider` | enum | Yes | - | Provider type: `openai`, `anthropic`, `google`, `openai_compatible`, `azure_openai`, `ollama` |
| `model` | string | Yes | - | Model identifier (provider-specific) |
| `base_url` | string (URI) | Conditional | - | Required for `openai_compatible`, `ollama` |
| `api_key_env` | string | No | Provider default | Environment variable name for API key |
| `temperature` | number | No | 0.7 | Sampling temperature (0.0-2.0) |
| `max_tokens` | integer | No | Model default | Maximum output tokens |
| `timeout_seconds` | integer | No | 60 | Request timeout |

### 3.3 Provider-Specific Defaults

| Provider | Default `api_key_env` | Notes |
|----------|----------------------|-------|
| `openai` | `OPENAI_API_KEY` | Standard OpenAI API |
| `anthropic` | `ANTHROPIC_API_KEY` | Claude models |
| `google` | `GOOGLE_API_KEY` | Gemini models |
| `openai_compatible` | `OPENAI_API_KEY` | Requires `base_url` |
| `azure_openai` | `AZURE_OPENAI_API_KEY` | Requires `base_url` |
| `ollama` | - (no key needed) | Local Ollama instance |

### 3.4 Examples

```yaml
llms:
  # OpenAI GPT-4
  default:
    provider: openai
    model: gpt-4o
    temperature: 0.7
    max_tokens: 4096

  # Anthropic Claude
  claude:
    provider: anthropic
    model: claude-3-sonnet-20240229
    temperature: 0.5
    api_key_env: ANTHROPIC_API_KEY

  # Local Ollama
  local:
    provider: ollama
    model: qwen2.5:latest
    base_url: "http://localhost:11434/v1"
    temperature: 0.2

  # Azure OpenAI
  azure:
    provider: azure_openai
    model: gpt-4-deployment
    base_url: "https://myinstance.openai.azure.com"
    api_key_env: AZURE_OPENAI_API_KEY

  # Supervisor with specific settings
  supervisor:
    provider: openai
    model: gpt-4-turbo
    temperature: 0.1  # Lower for more deterministic routing
```

---

## 4. MCP Servers Section

### 4.1 Overview

```yaml
mcp_servers:
  <server_name>:
    transport: <stdio|http|sse>
    # ... transport-specific options
```

### 4.2 Field Reference

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `transport` | enum | Yes | - | Transport type: `stdio`, `http`, `sse` |
| `command` | array[string] | stdio only | - | Command and arguments for subprocess |
| `url` | string (URI) | http/sse only | - | Server URL |
| `env` | object | No | {} | Environment variables for stdio subprocess |
| `timeout_seconds` | integer | No | 30 | Connection/request timeout |

### 4.3 Transport Comparison

| Transport | Use Case | Process Model | Scalability |
|-----------|----------|---------------|-------------|
| `stdio` | Local tools, CLI wrappers | Subprocess | Single client |
| `http` | Remote services, shared tools | External | Multi-client |
| `sse` | Remote with streaming | External | Multi-client |

### 4.4 Examples

```yaml
mcp_servers:
  # Local filesystem server (stdio)
  filesystem:
    transport: stdio
    command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/data"]
    timeout_seconds: 30

  # Python MCP server (stdio)
  knowledge:
    transport: stdio
    command: ["python", "-m", "mcp_server_knowledge"]
    env:
      KNOWLEDGE_DB_PATH: "/data/knowledge.db"

  # Remote HTTP server
  github:
    transport: http
    url: "http://localhost:8089/mcp"
    timeout_seconds: 45

  # Remote SSE server
  search:
    transport: sse
    url: "http://localhost:5001/api/sse"
    timeout_seconds: 60
```

---

## 5. Tools Section

### 5.1 Overview

```yaml
tools:
  <tool_id>:
    server: <mcp_server_name>
    tool_name: <mcp_tool_name>
    # ... optional overrides
```

### 5.2 Field Reference

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `server` | string | Yes | - | Reference to MCP server in `mcp_servers` |
| `tool_name` | string | Yes | - | Tool name as exposed by the MCP server |
| `description_override` | string | No | - | Override MCP-provided description |
| `timeout_seconds` | integer | No | Server default | Tool-specific timeout |

### 5.3 Tool ID Naming Convention

- Use `snake_case` for tool IDs
- Keep names descriptive but concise
- Avoid prefixes that duplicate server name

### 5.4 Examples

```yaml
tools:
  # Web search tool
  search_web:
    server: knowledge
    tool_name: "search.web"
    description_override: "Search the web for current information"
    timeout_seconds: 45

  # Text summarization
  summarize:
    server: knowledge
    tool_name: "summarize.text"

  # GitHub tools
  gh_search_code:
    server: github
    tool_name: "github.search_code"

  gh_open_pr:
    server: github
    tool_name: "github.open_pr"
    timeout_seconds: 60  # PRs may take longer

  # Filesystem tools
  read_file:
    server: filesystem
    tool_name: "read_file"

  write_file:
    server: filesystem
    tool_name: "write_file"
```

---

## 6. Skills Section

### 6.1 Overview

```yaml
skills:
  <skill_name>:
    tools: [<tool_id>, ...]
    description: <optional_description>
```

### 6.2 Field Reference

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `tools` | array[string] | Yes | - | List of tool IDs from `tools` section |
| `description` | string | No | - | Human-readable skill description |

### 6.3 Skill Design Guidelines

- Group related tools that serve a common purpose
- Keep skills focused (3-7 tools typically)
- Use skills to express agent capabilities for routing
- Skill names should be descriptive verbs or noun phrases

### 6.4 Examples

```yaml
skills:
  # Research capabilities
  web_research:
    tools: ["search_web", "summarize"]
    description: "Search and summarize web content"

  # Data analysis capabilities
  data_analysis:
    tools: ["analyze_data", "visualize_chart", "export_csv"]
    description: "Analyze datasets and create visualizations"

  # Repository operations
  repo_ops:
    tools: ["gh_search_code", "gh_open_pr", "gh_list_issues"]
    description: "GitHub repository operations"

  # File operations
  file_ops:
    tools: ["read_file", "write_file", "list_directory"]
    description: "Local filesystem operations"

  # Code execution
  code_execution:
    tools: ["run_python", "run_shell"]
    description: "Execute code safely in sandbox"
```

---

## 7. Skillsets Section

### 7.1 Overview

```yaml
skillsets:
  <skillset_name>:
    skills: [<skill_name>, ...]
    description: <optional_description>
```

### 7.2 Field Reference

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `skills` | array[string] | Yes | - | List of skill names from `skills` section |
| `description` | string | No | - | Human-readable skillset description |

### 7.3 Skillset Design Guidelines

- Skillsets define agent personas/roles
- Multiple agents can share skillsets
- Skillsets can overlap in skills (tool overlap is fine)

### 7.4 Examples

```yaml
skillsets:
  # Research agent capabilities
  researcher:
    skills: ["web_research", "data_analysis"]
    description: "Research and analyze information"

  # Developer agent capabilities
  developer:
    skills: ["repo_ops", "file_ops", "code_execution", "web_research"]
    description: "Software development and coding tasks"

  # Analyst agent capabilities
  analyst:
    skills: ["data_analysis", "web_research"]
    description: "Data analysis and insights"

  # Operations agent capabilities
  ops:
    skills: ["file_ops", "code_execution"]
    description: "System operations and automation"
```

---

## 8. Agents Section

### 8.1 Overview

```yaml
agents:
  <agent_name>:
    kind: <supervisor|native_worker>
    # ... agent configuration
```

### 8.2 Field Reference

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `kind` | enum | Yes | - | Agent type: `supervisor`, `native_worker` |
| `framework` | enum | No | `langchain` | Any-Agent framework |
| `llm` | string | No | `default` | Reference to LLM config |
| `skillset` | string | workers only | - | Reference to skillset |
| `tools` | array[string] | No | [] | Direct tool references |
| `system_prompt` | string | Yes | - | System instructions |
| `description` | string | No | - | Description for routing |
| `timeout_seconds` | integer | No | Graph default | Agent-level timeout |
| `retry_policy` | object | No | Graph default | Retry configuration |

### 8.3 Framework Options

| Framework | Description | Best For |
|-----------|-------------|----------|
| `langchain` | LangChain/LangGraph native | General purpose |
| `openai` | OpenAI Agents SDK | OpenAI-optimized workflows |
| `google` | Google ADK | Gemini-optimized |
| `smolagents` | HuggingFace smolagents | Lightweight agents |
| `llamaindex` | LlamaIndex agents | RAG-focused |
| `agno` | Agno framework | Minimal agents |
| `tinyagent` | TinyAgent | Ultra-lightweight |

### 8.4 Examples

```yaml
agents:
  # Supervisor (required)
  supervisor:
    kind: supervisor
    llm: supervisor  # Reference to llms.supervisor
    system_prompt: |
      You are the orchestration supervisor. Your role is to:
      1. Understand the user's request
      2. Route to the appropriate specialist worker
      3. Synthesize results from workers
      4. Ask for clarification using send_message when needed
      
      Available workers: {roster}
      
      Choose the best worker for each task, or END if complete.
    tools: ["send_message"]  # Human-in-the-loop tool
    description: "Routes tasks to specialist workers"

  # Research worker
  research_agent:
    kind: native_worker
    framework: langchain
    llm: default
    skillset: researcher
    system_prompt: |
      You are a research specialist. Your expertise:
      - Finding information from web sources
      - Analyzing and summarizing content
      - Providing well-sourced answers
      
      Always cite your sources.
    description: "Expert at web research and information synthesis"
    timeout_seconds: 120

  # Code worker
  code_agent:
    kind: native_worker
    framework: openai  # Use OpenAI framework for this worker
    llm: default
    skillset: developer
    system_prompt: |
      You are a coding specialist. Your expertise:
      - Writing clean, efficient code
      - Debugging and code review
      - Repository management
      
      Follow best practices and explain your changes.
    description: "Expert at coding and software development"
    timeout_seconds: 180
    retry_policy:
      max_retries: 2
      exponential_backoff: true

  # Analysis worker
  analysis_agent:
    kind: native_worker
    framework: tinyagent  # Lightweight framework
    llm: local  # Use local Ollama
    skillset: analyst
    system_prompt: |
      You are a data analysis specialist. Analyze data and provide insights.
    description: "Expert at data analysis and visualization"
```

---

## 9. Native Workers Section

### 9.1 Overview

```yaml
native_workers:
  ignore_workers: [<agent_name>, ...]
```

### 9.2 Field Reference

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `ignore_workers` | array[string] | No | [] | Worker agent names to exclude from graph |

### 9.3 Use Cases

- Disable workers during development
- A/B testing different worker configurations
- Temporarily exclude problematic workers

### 9.4 Examples

```yaml
native_workers:
  # Exclude these workers from the graph
  ignore_workers:
    - code_agent       # Under development
    - legacy_worker    # Deprecated
```

---

## 10. A2A Section

### 10.1 Overview

```yaml
a2a:
  discovery:
    seeds: [...]
    # ... discovery options
  import_policy:
    mode: <langgraph_nodes|tools_only>
    # ... import options
```

### 10.2 Discovery Subsection

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `seeds` | array[URI] | No | [] | Seed URLs for discovery |
| `well_known_paths` | array[string] | No | [`/.well-known/agent.json`] | Paths to check for Agent Cards |
| `host_index_path` | string | No | `/a2a/index.json` | Path for host index endpoint |
| `timeout_seconds` | integer | No | 10 | Discovery HTTP timeout |
| `parallel_discovery` | boolean | No | true | Fetch cards in parallel |

### 10.3 Import Policy Subsection

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enabled` | boolean | No | true | Enable/disable import |
| `mode` | enum | No | `langgraph_nodes` | Import mode |
| `max_agents` | integer | No | 25 | Maximum agents to import |
| `include_tags` | array[string] | No | [] | Only include these tags |
| `exclude_tags` | array[string] | No | [] | Exclude these tags |
| `include_names` | array[string] | No | [] | Only include these names |
| `exclude_names` | array[string] | No | [] | Exclude these names |
| `tools_assignment` | object | No | - | Settings for tools_only mode |

### 10.4 Tools Assignment Subsection

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `strategy` | enum | No | `skill_overlap` | Assignment strategy |
| `fallback` | enum | No | `supervisor` | Fallback if no match |
| `explicit` | object | No | {} | Manual mappings |

### 10.5 Examples

```yaml
a2a:
  discovery:
    seeds:
      - "http://localhost:9001"        # Multi-agent host
      - "http://localhost:9010"        # Individual agent
      - "http://localhost:9011"        # Individual agent
    well_known_paths:
      - "/.well-known/agent.json"
    host_index_path: "/a2a/index.json"
    timeout_seconds: 15
    parallel_discovery: true

  import_policy:
    enabled: true
    mode: langgraph_nodes  # Import as graph nodes
    max_agents: 25
    include_tags: ["internal", "proto"]
    exclude_names: ["unsafe-agent", "test-agent"]

# Alternative: tools_only mode
a2a:
  discovery:
    seeds:
      - "http://localhost:9001"
  import_policy:
    enabled: true
    mode: tools_only
    tools_assignment:
      strategy: skill_overlap
      fallback: supervisor
      explicit:
        "ext::special-agent": "research_agent"
```

---

## 11. Graph Section

### 11.1 Overview

```yaml
graph:
  max_iterations: <int>
  timeouts: {...}
  retry_policy: {...}
```

### 11.2 Field Reference

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `max_iterations` | integer | No | 12 | Max supervisor routing iterations |
| `timeouts.external_agent_call_seconds` | integer | No | 40 | A2A call timeout |
| `timeouts.tool_call_seconds` | integer | No | 30 | MCP tool call timeout |
| `timeouts.total_execution_seconds` | integer | No | 300 | Total graph execution timeout |
| `retry_policy` | object | No | - | Default retry policy |

### 11.3 Examples

```yaml
graph:
  max_iterations: 15
  timeouts:
    external_agent_call_seconds: 60
    tool_call_seconds: 45
    total_execution_seconds: 600
  retry_policy:
    max_retries: 2
    retry_delay_seconds: 2.0
    exponential_backoff: true
```

---

## 12. Serving Section

### 12.1 Overview

```yaml
serving:
  api: {...}
  ui: {...}
```

### 12.2 API Subsection

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `host` | string | No | `127.0.0.1` | Bind host |
| `port` | integer | No | 7777 | Bind port |
| `cors_origins` | array[string] | No | [`*`] | CORS allowed origins |
| `openai_compatible` | boolean | No | true | Enable OpenAI facade |

### 12.3 UI Subsection

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `mode` | enum | No | `none` | UI mode: `none`, `chainlit`, `openwebui_compatible` |

### 12.4 Examples

```yaml
serving:
  api:
    host: "0.0.0.0"  # Listen on all interfaces
    port: 7777
    cors_origins:
      - "http://localhost:3000"
      - "http://localhost:8080"
    openai_compatible: true

  ui:
    mode: chainlit  # Use Chainlit UI
```

---

## 13. Related Documents

- D25: Master Config Schema (JSON Schema)
- D27: Config Examples Catalog
- D28: Environment Variables & Secrets

---

## 14. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Architecture Team | Initial draft |
