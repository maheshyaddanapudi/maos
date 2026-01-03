# D27: Config Examples Catalog

## Config-Driven Multi-Agent Orchestration System

**Document ID:** D27  
**Version:** 1.0  
**Status:** Draft  
**Last Updated:** January 2026

---

## 1. Overview

This document provides complete, working configuration examples for various deployment scenarios. Each example is self-contained and can be used as a starting point.

---

## 2. Example 1: Minimal Configuration

The simplest possible configuration with one LLM and a supervisor-only setup.

```yaml
# config-minimal.yaml
# Minimal configuration - supervisor only, no workers

llms:
  default:
    provider: openai
    model: gpt-4o
    temperature: 0.7

agents:
  supervisor:
    kind: supervisor
    llm: default
    system_prompt: |
      You are a helpful assistant. Answer questions directly.
      You have no specialist workers, so handle all requests yourself.
    tools: ["send_message"]

# Uses all defaults for serving (127.0.0.1:7777)
```

---

## 3. Example 2: Research Team Configuration

A research-focused setup with web research and analysis capabilities.

```yaml
# config-research-team.yaml
# Research team with web search and analysis workers

llms:
  default:
    provider: openai
    model: gpt-4o
    temperature: 0.7

  supervisor:
    provider: openai
    model: gpt-4-turbo
    temperature: 0.1

mcp_servers:
  web:
    transport: stdio
    command: ["python", "-m", "mcp_server_web"]
    timeout_seconds: 45

  analysis:
    transport: stdio
    command: ["python", "-m", "mcp_server_analysis"]

tools:
  search_web:
    server: web
    tool_name: "search.web"
  
  fetch_page:
    server: web
    tool_name: "fetch.page"
  
  summarize:
    server: web
    tool_name: "summarize.text"
  
  analyze_data:
    server: analysis
    tool_name: "analyze.structured"
  
  create_chart:
    server: analysis
    tool_name: "visualize.chart"

skills:
  web_research:
    tools: ["search_web", "fetch_page", "summarize"]
    description: "Search and analyze web content"
  
  data_analysis:
    tools: ["analyze_data", "create_chart"]
    description: "Analyze data and create visualizations"

skillsets:
  researcher:
    skills: ["web_research"]
  
  analyst:
    skills: ["data_analysis", "web_research"]

agents:
  supervisor:
    kind: supervisor
    llm: supervisor
    system_prompt: |
      You are the research team supervisor. Route requests to specialists:
      
      - research_agent: Web searches, finding information, summarizing content
      - analysis_agent: Data analysis, creating charts, interpreting numbers
      
      Available workers: {roster}
      
      For general questions, route to research_agent first.
      Use send_message to clarify ambiguous requests.
    tools: ["send_message"]

  research_agent:
    kind: native_worker
    framework: langchain
    llm: default
    skillset: researcher
    system_prompt: |
      You are a research specialist. Find and summarize information from the web.
      Always cite your sources with URLs.
    description: "Web research and information gathering"

  analysis_agent:
    kind: native_worker
    framework: langchain
    llm: default
    skillset: analyst
    system_prompt: |
      You are a data analysis specialist. Analyze data and create visualizations.
      Explain your findings clearly with supporting charts.
    description: "Data analysis and visualization"

graph:
  max_iterations: 10
  timeouts:
    tool_call_seconds: 60
    total_execution_seconds: 300

serving:
  api:
    host: "127.0.0.1"
    port: 7777
    openai_compatible: true
```

---

## 4. Example 3: Development Team Configuration

A software development team with coding, testing, and documentation workers.

```yaml
# config-dev-team.yaml
# Development team with coding, testing, and docs workers

llms:
  default:
    provider: openai
    model: gpt-4o
    temperature: 0.3  # Lower for code accuracy

  supervisor:
    provider: openai
    model: gpt-4-turbo
    temperature: 0.1

  local:
    provider: ollama
    model: qwen2.5-coder:32b
    base_url: "http://localhost:11434/v1"
    temperature: 0.2

mcp_servers:
  github:
    transport: http
    url: "http://localhost:8089/mcp"
    timeout_seconds: 60

  filesystem:
    transport: stdio
    command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/workspace"]

  executor:
    transport: stdio
    command: ["python", "-m", "mcp_server_executor"]
    env:
      SANDBOX_MODE: "true"

tools:
  # GitHub tools
  gh_search:
    server: github
    tool_name: "github.search_code"
  
  gh_get_file:
    server: github
    tool_name: "github.get_file"
  
  gh_create_pr:
    server: github
    tool_name: "github.create_pr"
  
  gh_list_issues:
    server: github
    tool_name: "github.list_issues"
  
  # Filesystem tools
  read_file:
    server: filesystem
    tool_name: "read_file"
  
  write_file:
    server: filesystem
    tool_name: "write_file"
  
  list_dir:
    server: filesystem
    tool_name: "list_directory"
  
  # Execution tools
  run_python:
    server: executor
    tool_name: "execute.python"
  
  run_tests:
    server: executor
    tool_name: "execute.pytest"
  
  run_lint:
    server: executor
    tool_name: "execute.lint"

skills:
  repo_ops:
    tools: ["gh_search", "gh_get_file", "gh_create_pr", "gh_list_issues"]
    description: "GitHub repository operations"
  
  file_ops:
    tools: ["read_file", "write_file", "list_dir"]
    description: "Local file operations"
  
  code_execution:
    tools: ["run_python", "run_tests", "run_lint"]
    description: "Code execution and testing"

skillsets:
  coder:
    skills: ["repo_ops", "file_ops", "code_execution"]
    description: "Full coding capabilities"
  
  reviewer:
    skills: ["repo_ops", "file_ops", "code_execution"]
    description: "Code review capabilities"
  
  docs_writer:
    skills: ["file_ops", "repo_ops"]
    description: "Documentation capabilities"

agents:
  supervisor:
    kind: supervisor
    llm: supervisor
    system_prompt: |
      You are the development team lead. Route tasks to specialists:
      
      - code_agent: Writing code, implementing features, fixing bugs
      - review_agent: Code review, finding issues, suggesting improvements
      - docs_agent: Writing documentation, README files, API docs
      
      Available workers: {roster}
      
      For feature requests, start with code_agent.
      For bug reports, consider review_agent first to analyze.
      Use send_message for unclear requirements.
    tools: ["send_message"]

  code_agent:
    kind: native_worker
    framework: langchain
    llm: default
    skillset: coder
    system_prompt: |
      You are a senior software developer. Write clean, efficient, well-documented code.
      Follow best practices:
      - Write tests for new code
      - Use type hints
      - Add docstrings
      - Handle errors gracefully
    description: "Code implementation and feature development"
    timeout_seconds: 180

  review_agent:
    kind: native_worker
    framework: openai
    llm: default
    skillset: reviewer
    system_prompt: |
      You are a code reviewer. Analyze code for:
      - Bugs and security issues
      - Performance problems
      - Style and best practices
      - Test coverage
      
      Provide actionable feedback with specific suggestions.
    description: "Code review and quality analysis"
    timeout_seconds: 120

  docs_agent:
    kind: native_worker
    framework: tinyagent
    llm: local  # Use local model for docs
    skillset: docs_writer
    system_prompt: |
      You are a technical writer. Create clear documentation:
      - README files
      - API documentation
      - User guides
      - Code comments
      
      Write for clarity and completeness.
    description: "Documentation and technical writing"
    timeout_seconds: 90

graph:
  max_iterations: 15
  timeouts:
    tool_call_seconds: 60
    total_execution_seconds: 600
  retry_policy:
    max_retries: 2
    exponential_backoff: true

serving:
  api:
    host: "0.0.0.0"
    port: 7777
    cors_origins: ["http://localhost:3000"]
    openai_compatible: true
```

---

## 5. Example 4: External Agents with langgraph_nodes Mode

Configuration using external A2A agents as first-class graph nodes.

```yaml
# config-external-nodes.yaml
# External A2A agents imported as LangGraph nodes

llms:
  default:
    provider: openai
    model: gpt-4o
    temperature: 0.5

  supervisor:
    provider: openai
    model: gpt-4-turbo
    temperature: 0.1

mcp_servers:
  local_tools:
    transport: stdio
    command: ["python", "-m", "mcp_server_tools"]

tools:
  search_local:
    server: local_tools
    tool_name: "search.local"

skills:
  local_search:
    tools: ["search_local"]

skillsets:
  basic:
    skills: ["local_search"]

agents:
  supervisor:
    kind: supervisor
    llm: supervisor
    system_prompt: |
      You are the orchestration supervisor. Route tasks to the best worker.
      
      You have both local workers and external specialist agents.
      External agents are prefixed with "ext::".
      
      Available workers: {roster}
      
      Choose based on the task requirements.
      Use send_message for clarification.
    tools: ["send_message"]

  local_agent:
    kind: native_worker
    framework: langchain
    llm: default
    skillset: basic
    system_prompt: |
      You are a local assistant for basic tasks.
    description: "Local general-purpose assistant"

a2a:
  discovery:
    seeds:
      # Multi-agent host with analytics and ML agents
      - "http://localhost:9001"
      # Individual specialist agents
      - "http://localhost:9010"  # Legal agent
      - "http://localhost:9011"  # Finance agent
    well_known_paths:
      - "/.well-known/agent.json"
    host_index_path: "/a2a/index.json"
    timeout_seconds: 15
    parallel_discovery: true

  import_policy:
    enabled: true
    mode: langgraph_nodes  # Import as full graph nodes
    max_agents: 20
    include_tags: ["production", "internal"]
    exclude_names: ["test-agent", "deprecated-agent"]

graph:
  max_iterations: 15
  timeouts:
    external_agent_call_seconds: 60
    tool_call_seconds: 30
    total_execution_seconds: 600

serving:
  api:
    host: "0.0.0.0"
    port: 7777
```

---

## 6. Example 5: External Agents with tools_only Mode

Configuration using external A2A agents as tools attached to workers.

```yaml
# config-external-tools.yaml
# External A2A agents imported as tools

llms:
  default:
    provider: openai
    model: gpt-4o
    temperature: 0.5

  supervisor:
    provider: openai
    model: gpt-4-turbo
    temperature: 0.1

mcp_servers:
  knowledge:
    transport: stdio
    command: ["python", "-m", "mcp_server_knowledge"]

tools:
  search_web:
    server: knowledge
    tool_name: "search.web"
  
  summarize:
    server: knowledge
    tool_name: "summarize.text"

skills:
  web_research:
    tools: ["search_web", "summarize"]

  # Note: External A2A agents will add tools to workers via skill_overlap
  data_analysis:
    tools: []  # Placeholder - external analytics agent will match this

skillsets:
  researcher:
    skills: ["web_research", "data_analysis"]

agents:
  supervisor:
    kind: supervisor
    llm: supervisor
    system_prompt: |
      You are the supervisor. Route to research_agent for all tasks.
      The research agent has access to both local tools and external specialists.
      
      Available workers: {roster}
    tools: ["send_message"]

  research_agent:
    kind: native_worker
    framework: langchain
    llm: default
    skillset: researcher
    system_prompt: |
      You are a research specialist with access to:
      - Web search and summarization
      - External analytics capabilities (via tool calls)
      
      Use the appropriate tool for each task.
    description: "Research with local and external tools"

a2a:
  discovery:
    seeds:
      - "http://localhost:9001"  # Analytics host
      - "http://localhost:9010"  # ML agent
    timeout_seconds: 15

  import_policy:
    enabled: true
    mode: tools_only  # Import as callable tools
    
    tools_assignment:
      strategy: skill_overlap  # Match external agent skills to worker skillsets
      fallback: supervisor     # If no match, attach to supervisor
      explicit:
        # Override: attach this specific agent to research_agent
        "ext::special-analytics": "research_agent"
    
    max_agents: 10
    include_tags: ["analytics", "ml"]

graph:
  max_iterations: 12
  timeouts:
    external_agent_call_seconds: 45
    tool_call_seconds: 30

serving:
  api:
    port: 7777
```

---

## 7. Example 6: Multi-LLM Configuration

Using different LLM providers for different agents.

```yaml
# config-multi-llm.yaml
# Different LLM providers for different agents

llms:
  # OpenAI for general tasks
  openai_default:
    provider: openai
    model: gpt-4o
    temperature: 0.7

  # Anthropic for careful reasoning
  anthropic_careful:
    provider: anthropic
    model: claude-3-sonnet-20240229
    temperature: 0.3
    api_key_env: ANTHROPIC_API_KEY

  # Google for fast responses
  google_fast:
    provider: google
    model: gemini-1.5-flash
    temperature: 0.5
    api_key_env: GOOGLE_API_KEY

  # Local Ollama for cost-sensitive tasks
  local_ollama:
    provider: ollama
    model: qwen2.5:32b
    base_url: "http://localhost:11434/v1"
    temperature: 0.2

  # Azure for enterprise
  azure_enterprise:
    provider: azure_openai
    model: gpt-4-deployment
    base_url: "https://mycompany.openai.azure.com"
    api_key_env: AZURE_OPENAI_API_KEY
    temperature: 0.5

mcp_servers:
  tools:
    transport: stdio
    command: ["python", "-m", "mcp_tools"]

tools:
  search: { server: tools, tool_name: "search" }
  analyze: { server: tools, tool_name: "analyze" }
  generate: { server: tools, tool_name: "generate" }

skills:
  search_skill: { tools: ["search"] }
  analysis_skill: { tools: ["analyze"] }
  generation_skill: { tools: ["generate"] }

skillsets:
  searcher: { skills: ["search_skill"] }
  analyst: { skills: ["analysis_skill"] }
  generator: { skills: ["generation_skill"] }

agents:
  supervisor:
    kind: supervisor
    llm: anthropic_careful  # Anthropic for careful routing decisions
    system_prompt: |
      You are a careful supervisor. Route tasks thoughtfully.
      Available workers: {roster}
    tools: ["send_message"]

  search_agent:
    kind: native_worker
    llm: google_fast  # Google for fast search
    skillset: searcher
    system_prompt: "Quick search specialist"
    description: "Fast web searches"

  analysis_agent:
    kind: native_worker
    llm: openai_default  # OpenAI for analysis
    skillset: analyst
    system_prompt: "Deep analysis specialist"
    description: "Detailed analysis"

  content_agent:
    kind: native_worker
    llm: local_ollama  # Local model for content (cost-saving)
    skillset: generator
    system_prompt: "Content generation specialist"
    description: "Generate content locally"

serving:
  api:
    port: 7777
```

---

## 8. Example 7: Full Production-Like Configuration

A comprehensive configuration demonstrating all features.

```yaml
# config-full.yaml
# Full configuration with all features

llms:
  default:
    provider: openai
    model: gpt-4o
    temperature: 0.7
    max_tokens: 4096
    timeout_seconds: 60

  supervisor:
    provider: openai
    model: gpt-4-turbo
    temperature: 0.1
    max_tokens: 2048

  fast:
    provider: google
    model: gemini-1.5-flash
    temperature: 0.5

  local:
    provider: ollama
    model: qwen2.5:latest
    base_url: "http://localhost:11434/v1"
    temperature: 0.3

mcp_servers:
  knowledge:
    transport: stdio
    command: ["python", "-m", "mcp_server_knowledge"]
    timeout_seconds: 30

  github:
    transport: http
    url: "http://localhost:8089/mcp"
    timeout_seconds: 60

  filesystem:
    transport: stdio
    command: ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/data"]

  executor:
    transport: stdio
    command: ["python", "-m", "mcp_server_executor"]
    env:
      SANDBOX_MODE: "true"
      MAX_EXECUTION_TIME: "30"

tools:
  # Knowledge tools
  search_web:
    server: knowledge
    tool_name: "search.web"
    timeout_seconds: 45
  
  summarize:
    server: knowledge
    tool_name: "summarize.text"
  
  # GitHub tools
  gh_search:
    server: github
    tool_name: "github.search_code"
  
  gh_get_file:
    server: github
    tool_name: "github.get_file"
  
  gh_create_pr:
    server: github
    tool_name: "github.create_pr"
  
  # Filesystem tools
  read_file:
    server: filesystem
    tool_name: "read_file"
  
  write_file:
    server: filesystem
    tool_name: "write_file"
  
  # Executor tools
  run_python:
    server: executor
    tool_name: "execute.python"

skills:
  web_research:
    tools: ["search_web", "summarize"]
    description: "Web search and summarization"
  
  repo_ops:
    tools: ["gh_search", "gh_get_file", "gh_create_pr"]
    description: "GitHub operations"
  
  file_ops:
    tools: ["read_file", "write_file"]
    description: "File system operations"
  
  code_execution:
    tools: ["run_python"]
    description: "Python code execution"

skillsets:
  researcher:
    skills: ["web_research"]
    description: "Research capabilities"
  
  developer:
    skills: ["repo_ops", "file_ops", "code_execution", "web_research"]
    description: "Full development capabilities"
  
  ops:
    skills: ["file_ops", "code_execution"]
    description: "Operations capabilities"

agents:
  supervisor:
    kind: supervisor
    llm: supervisor
    system_prompt: |
      You are the orchestration supervisor for a multi-agent system.
      
      Your responsibilities:
      1. Understand user requests thoroughly
      2. Route to the most appropriate specialist
      3. Synthesize results from multiple workers if needed
      4. Request clarification when requirements are unclear
      
      Available workers: {roster}
      
      Routing guidelines:
      - Research questions → research_agent
      - Coding tasks → code_agent
      - File/system operations → ops_agent
      - Complex tasks → may require multiple workers
      
      Always explain your routing decision briefly.
    tools: ["send_message"]
    description: "Routes tasks to specialist workers"

  research_agent:
    kind: native_worker
    framework: langchain
    llm: fast  # Use fast model for research
    skillset: researcher
    system_prompt: |
      You are a research specialist.
      
      Your capabilities:
      - Web search for current information
      - Summarizing content clearly
      - Citing sources properly
      
      Always provide sources for your findings.
    description: "Expert at finding and synthesizing information"
    timeout_seconds: 120

  code_agent:
    kind: native_worker
    framework: openai
    llm: default
    skillset: developer
    system_prompt: |
      You are a senior software developer.
      
      Your capabilities:
      - Writing clean, efficient code
      - GitHub repository operations
      - Code execution and testing
      
      Best practices:
      - Write tests for new code
      - Use type hints and docstrings
      - Handle errors gracefully
    description: "Expert at coding and development"
    timeout_seconds: 180
    retry_policy:
      max_retries: 2
      exponential_backoff: true

  ops_agent:
    kind: native_worker
    framework: tinyagent
    llm: local  # Use local model for ops
    skillset: ops
    system_prompt: |
      You are a systems operations specialist.
      
      Your capabilities:
      - File system operations
      - Script execution
      - Automation tasks
      
      Always validate operations before executing.
    description: "Expert at system operations"
    timeout_seconds: 90

native_workers:
  ignore_workers: []  # No workers ignored

a2a:
  discovery:
    seeds:
      - "http://localhost:9001"  # Multi-agent host
      - "http://localhost:9010"  # Individual agent
    well_known_paths:
      - "/.well-known/agent.json"
    host_index_path: "/a2a/index.json"
    timeout_seconds: 15
    parallel_discovery: true

  import_policy:
    enabled: true
    mode: langgraph_nodes
    max_agents: 25
    include_tags: ["production", "internal"]
    exclude_names: ["test-agent"]

graph:
  max_iterations: 15
  timeouts:
    external_agent_call_seconds: 60
    tool_call_seconds: 45
    total_execution_seconds: 600
  retry_policy:
    max_retries: 2
    retry_delay_seconds: 1.0
    exponential_backoff: true

serving:
  api:
    host: "0.0.0.0"
    port: 7777
    cors_origins:
      - "http://localhost:3000"
      - "http://localhost:8080"
    openai_compatible: true
  
  ui:
    mode: chainlit
```

---

## 9. Related Documents

- D25: Master Config Schema
- D26: Config Reference Guide
- D28: Environment Variables & Secrets

---

## 10. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Architecture Team | Initial draft |
