"""
Test Configuration Fixtures.
"""

# Valid minimal configuration
VALID_MINIMAL_CONFIG = """
llms:
  default:
    provider: openai
    model: gpt-4o-mini

agents:
  supervisor:
    kind: supervisor
    system_prompt: "You are a supervisor."
"""

# Valid full configuration
VALID_FULL_CONFIG = """
llms:
  default:
    provider: openai
    model: gpt-4o-mini
    temperature: 0.7
    max_tokens: 4096
    api_key_env: OPENAI_API_KEY

  claude:
    provider: anthropic
    model: claude-3-sonnet-20240229
    api_key_env: ANTHROPIC_API_KEY

mcp_servers:
  tools:
    transport: stdio
    command: ["python", "-m", "mock_server"]
    timeout_seconds: 30

tools:
  search_web:
    server: tools
    tool_name: search.web
    description_override: "Search the web"
    timeout_seconds: 20

  summarize:
    server: tools
    tool_name: text.summarize

skills:
  web_research:
    tools:
      - search_web
      - summarize
    description: "Web research skill"

skillsets:
  researcher:
    skills:
      - web_research
    description: "Research skillset"

agents:
  supervisor:
    kind: supervisor
    llm: default
    system_prompt: "You are a supervisor."
    description: "Main supervisor"

  research_agent:
    kind: native_worker
    llm: default
    skillset: researcher
    system_prompt: "You are a research agent."
    description: "Performs research tasks"
    timeout_seconds: 120

graph:
  max_iterations: 10
  timeouts:
    worker_seconds: 60
    tool_call_seconds: 30

serving:
  api:
    host: "127.0.0.1"
    port: 7777
    cors_origins:
      - "*"
"""

# Invalid configuration - missing required fields
INVALID_MISSING_LLMS = """
agents:
  supervisor:
    kind: supervisor
    system_prompt: "Test"
"""

# Invalid configuration - bad reference
INVALID_BAD_REFERENCE = """
llms:
  default:
    provider: openai
    model: gpt-4

agents:
  supervisor:
    kind: supervisor
    llm: nonexistent
    system_prompt: "Test"
"""

# Invalid configuration - wrong type
INVALID_WRONG_TYPE = """
llms:
  default:
    provider: openai
    model: gpt-4
    temperature: "hot"

agents:
  supervisor:
    kind: supervisor
    system_prompt: "Test"
"""
