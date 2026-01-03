# D28: Environment Variables & Secrets

## Config-Driven Multi-Agent Orchestration System

**Document ID:** D28  
**Version:** 1.0  
**Status:** Draft  
**Last Updated:** January 2026

---

## 1. Overview

This document specifies all environment variables used by the Multi-Agent Orchestration System, including API keys, configuration overrides, and runtime settings. Proper handling of secrets is critical even for internal prototypes.

---

## 2. Environment Variable Categories

```mermaid
flowchart TB
    subgraph Secrets["🔐 Secrets (API Keys)"]
        LLMKeys["LLM Provider Keys"]
        MCPKeys["MCP Server Keys"]
        A2AKeys["A2A Auth Keys"]
    end

    subgraph Config["⚙️ Configuration Overrides"]
        Paths["File Paths"]
        Ports["Network Ports"]
        Timeouts["Timeout Overrides"]
    end

    subgraph Runtime["🏃 Runtime Settings"]
        LogLevel["Logging"]
        Debug["Debug Flags"]
        Features["Feature Flags"]
    end

    Secrets --> App["Application"]
    Config --> App
    Runtime --> App
```

---

## 3. LLM Provider API Keys

### 3.1 Required Keys by Provider

| Provider | Environment Variable | Description |
|----------|---------------------|-------------|
| OpenAI | `OPENAI_API_KEY` | OpenAI API key |
| Anthropic | `ANTHROPIC_API_KEY` | Anthropic API key |
| Google | `GOOGLE_API_KEY` | Google AI API key |
| Azure OpenAI | `AZURE_OPENAI_API_KEY` | Azure OpenAI key |
| Azure OpenAI | `AZURE_OPENAI_ENDPOINT` | Azure endpoint URL |

### 3.2 Custom Key References

LLM configs can reference custom environment variables via `api_key_env`:

```yaml
llms:
  custom_openai:
    provider: openai
    model: gpt-4o
    api_key_env: MY_CUSTOM_OPENAI_KEY  # Uses $MY_CUSTOM_OPENAI_KEY
```

### 3.3 Ollama (No Key Required)

```yaml
llms:
  local:
    provider: ollama
    model: qwen2.5:latest
    base_url: "http://localhost:11434/v1"
    # No api_key_env needed
```

---

## 4. MCP Server Environment Variables

### 4.1 Server-Specific Variables

MCP servers running via stdio can receive environment variables:

```yaml
mcp_servers:
  knowledge:
    transport: stdio
    command: ["python", "-m", "mcp_server_knowledge"]
    env:
      KNOWLEDGE_DB_PATH: "/data/knowledge.db"
      KNOWLEDGE_API_KEY: "${KNOWLEDGE_SERVICE_KEY}"  # Reference env var
```

### 4.2 Common MCP Server Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `MCP_TIMEOUT` | Default MCP operation timeout | `30` |
| `MCP_LOG_LEVEL` | MCP server log level | `INFO` |

---

## 5. A2A Configuration Variables

### 5.1 Discovery Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `A2A_DISCOVERY_TIMEOUT` | `10` | Timeout for Agent Card fetching (seconds) |
| `A2A_DISCOVERY_PARALLEL` | `true` | Enable parallel discovery |

### 5.2 Authentication Variables (Future)

Reserved for future authentication support:

| Variable | Description |
|----------|-------------|
| `A2A_AUTH_TOKEN` | Default bearer token for A2A calls |
| `A2A_AUTH_HEADER` | Custom auth header name |
| `A2A_CLIENT_CERT` | Path to client certificate |
| `A2A_CLIENT_KEY` | Path to client key |

---

## 6. Application Configuration Variables

### 6.1 Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CONFIG_PATH` | `./config.yaml` | Path to configuration file |
| `CONFIG_FORMAT` | `auto` | Config format: `yaml`, `json`, `auto` |

### 6.2 Server Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `127.0.0.1` | API server bind host |
| `API_PORT` | `7777` | API server bind port |
| `CORS_ORIGINS` | `*` | Comma-separated CORS origins |

### 6.3 Timeout Overrides

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_MAX_ITERATIONS` | `12` | Override max supervisor iterations |
| `EXTERNAL_AGENT_TIMEOUT` | `40` | Override A2A call timeout (seconds) |
| `TOOL_CALL_TIMEOUT` | `30` | Override MCP tool timeout (seconds) |
| `TOTAL_EXECUTION_TIMEOUT` | `300` | Override total execution timeout |

---

## 7. Logging and Debug Variables

### 7.1 Logging Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | `json` | Log format: `json`, `text` |
| `LOG_FILE` | - | Optional log file path |

### 7.2 Debug Flags

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug mode |
| `DEBUG_LANGGRAPH` | `false` | Enable LangGraph debug logging |
| `DEBUG_MCP` | `false` | Enable MCP protocol debug logging |
| `DEBUG_A2A` | `false` | Enable A2A protocol debug logging |
| `DEBUG_TOOLS` | `false` | Log all tool calls and results |

### 7.3 Tracing Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TRACING_ENABLED` | `false` | Enable OpenInference tracing |
| `TRACING_ENDPOINT` | - | Tracing collector endpoint |
| `TRACING_SERVICE_NAME` | `multi-agent-orchestrator` | Service name in traces |

---

## 8. Feature Flags

| Variable | Default | Description |
|----------|---------|-------------|
| `FEATURE_STREAMING` | `true` | Enable response streaming |
| `FEATURE_OPENAI_COMPAT` | `true` | Enable OpenAI-compatible endpoint |
| `FEATURE_A2A_DISCOVERY` | `true` | Enable A2A agent discovery |
| `FEATURE_PARALLEL_TOOLS` | `false` | Enable parallel tool execution |

---

## 9. Environment File Template

### 9.1 Development (.env.development)

```bash
# ===========================================
# Multi-Agent Orchestration - Development
# ===========================================

# --- LLM Provider Keys ---
OPENAI_API_KEY=sk-your-openai-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here
GOOGLE_API_KEY=your-google-api-key-here

# --- Configuration ---
CONFIG_PATH=./config.yaml
API_HOST=127.0.0.1
API_PORT=7777

# --- Logging ---
LOG_LEVEL=DEBUG
LOG_FORMAT=text
DEBUG=true
DEBUG_LANGGRAPH=true
DEBUG_MCP=true
DEBUG_A2A=true

# --- Timeouts (generous for debugging) ---
EXTERNAL_AGENT_TIMEOUT=120
TOOL_CALL_TIMEOUT=60
TOTAL_EXECUTION_TIMEOUT=600

# --- Features ---
FEATURE_STREAMING=true
FEATURE_OPENAI_COMPAT=true
FEATURE_A2A_DISCOVERY=true
```

### 9.2 Production-Like (.env.production)

```bash
# ===========================================
# Multi-Agent Orchestration - Production-Like
# ===========================================

# --- LLM Provider Keys ---
OPENAI_API_KEY=${OPENAI_API_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
GOOGLE_API_KEY=${GOOGLE_API_KEY}

# --- Configuration ---
CONFIG_PATH=/app/config/config.yaml
API_HOST=0.0.0.0
API_PORT=7777

# --- Logging ---
LOG_LEVEL=INFO
LOG_FORMAT=json
DEBUG=false

# --- Timeouts ---
EXTERNAL_AGENT_TIMEOUT=40
TOOL_CALL_TIMEOUT=30
TOTAL_EXECUTION_TIMEOUT=300

# --- Tracing ---
TRACING_ENABLED=true
TRACING_ENDPOINT=http://jaeger:4317
TRACING_SERVICE_NAME=multi-agent-orchestrator

# --- Features ---
FEATURE_STREAMING=true
FEATURE_OPENAI_COMPAT=true
FEATURE_A2A_DISCOVERY=true
```

### 9.3 Local Ollama Only (.env.local)

```bash
# ===========================================
# Multi-Agent Orchestration - Local Only
# ===========================================

# No cloud API keys needed

# --- Configuration ---
CONFIG_PATH=./config-local.yaml
API_HOST=127.0.0.1
API_PORT=7777

# --- Logging ---
LOG_LEVEL=INFO
LOG_FORMAT=text
DEBUG=false

# --- Features ---
FEATURE_STREAMING=true
FEATURE_A2A_DISCOVERY=false  # No external agents
```

---

## 10. Loading Environment Variables

### 10.1 Using python-dotenv

```python
from dotenv import load_dotenv
import os

# Load from .env file
load_dotenv()

# Or load specific file
load_dotenv(".env.development")

# Access variables
openai_key = os.getenv("OPENAI_API_KEY")
log_level = os.getenv("LOG_LEVEL", "INFO")  # With default
```

### 10.2 Precedence Order

1. System environment variables (highest priority)
2. .env file in current directory
3. Default values in code (lowest priority)

### 10.3 Config Reference Resolution

When config references `api_key_env`:

```python
def resolve_api_key(config: LLMConfig) -> str:
    env_var = config.api_key_env or get_default_key_env(config.provider)
    api_key = os.getenv(env_var)
    if not api_key:
        raise ConfigError(f"Missing environment variable: {env_var}")
    return api_key
```

---

## 11. Security Best Practices

### 11.1 Do's

✅ Use `.env` files for local development  
✅ Add `.env*` to `.gitignore`  
✅ Use different keys for dev/staging/prod  
✅ Rotate keys regularly  
✅ Use least-privilege API keys  
✅ Log key presence, not values  

### 11.2 Don'ts

❌ Never commit API keys to git  
❌ Never log API key values  
❌ Never hardcode keys in source code  
❌ Never share keys across environments  
❌ Never use production keys for development  

### 11.3 Validation Logging

```python
def log_env_status():
    """Log which required variables are set (without values)."""
    required = ["OPENAI_API_KEY"]
    optional = ["ANTHROPIC_API_KEY", "GOOGLE_API_KEY"]
    
    for var in required:
        status = "✓ SET" if os.getenv(var) else "✗ MISSING"
        logger.info(f"{var}: {status}")
    
    for var in optional:
        status = "✓ SET" if os.getenv(var) else "○ NOT SET"
        logger.info(f"{var}: {status}")
```

---

## 12. Docker Environment

### 12.1 Docker Compose Example

```yaml
version: '3.8'

services:
  orchestrator:
    build: .
    ports:
      - "7777:7777"
    environment:
      - CONFIG_PATH=/app/config/config.yaml
      - API_HOST=0.0.0.0
      - API_PORT=7777
      - LOG_LEVEL=INFO
    env_file:
      - .env  # Load secrets from .env file
    volumes:
      - ./config:/app/config:ro
```

### 12.2 Kubernetes Secrets (Future Reference)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: llm-api-keys
type: Opaque
stringData:
  OPENAI_API_KEY: "sk-..."
  ANTHROPIC_API_KEY: "sk-ant-..."
```

---

## 13. Related Documents

- D25: Master Config Schema
- D26: Config Reference Guide
- D51: Local Development Setup Guide

---

## 14. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Architecture Team | Initial draft |
