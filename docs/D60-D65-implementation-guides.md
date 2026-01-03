# D60-D65: Implementation Guides

## Config-Driven Multi-Agent Orchestration System

**Document ID:** D60-D65  
**Version:** 1.0  
**Status:** Draft  
**Last Updated:** January 2026

---

## Document Index

| Doc ID | Guide | Description |
|--------|-------|-------------|
| D60 | Implementing a Native Worker | Step-by-step worker creation |
| D61 | Implementing an External A2A Agent (Individual) | Standalone A2A agent |
| D62 | Implementing an A2A Host (Multi-Agent) | Host multiple agents |
| D63 | Adding a New MCP Server | Custom tool server |
| D64 | Adding a New LLM Provider | Provider integration |
| D65 | Config-Driven Customization | Real-world scenarios |

---

# D60: Implementing a Native Worker

## Overview

This guide walks through creating a native worker agent that runs within the orchestration system using Any-Agent.

---

## Step 1: Define the Worker in Config

```yaml
# config.yaml

# First, ensure you have the required LLM
llms:
  default:
    provider: openai
    model: gpt-4o
    temperature: 0.7

# Define MCP server for tools (if needed)
mcp_servers:
  research_tools:
    transport: stdio
    command: ["python", "-m", "mcp_server_research"]

# Define tools
tools:
  search_web:
    server: research_tools
    tool_name: "search.web"
  
  summarize_text:
    server: research_tools
    tool_name: "summarize.text"

# Define skill
skills:
  web_research:
    tools: ["search_web", "summarize_text"]
    description: "Search and summarize web content"

# Define skillset
skillsets:
  researcher:
    skills: ["web_research"]
    description: "Research capabilities"

# Define the worker
agents:
  research_agent:
    kind: native_worker
    framework: langchain  # or openai, google, tinyagent, etc.
    llm: default
    skillset: researcher
    system_prompt: |
      You are a research specialist. Your job is to:
      1. Search the web for relevant information
      2. Summarize findings clearly
      3. Always cite your sources
      
      Be thorough but concise.
    description: "Expert at web research and information synthesis"
    timeout_seconds: 120
```

---

## Step 2: Create the MCP Server (if needed)

```python
# mcp_server_research/__main__.py

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Research Tools")

@mcp.tool()
async def search_web(query: str, limit: int = 5) -> str:
    """
    Search the web for information.
    
    Args:
        query: Search query string
        limit: Maximum number of results
    
    Returns:
        Search results as formatted text
    """
    # Implement search logic
    results = await perform_search(query, limit)
    return format_results(results)

@mcp.tool()
async def summarize_text(text: str, max_length: int = 200) -> str:
    """
    Summarize the given text.
    
    Args:
        text: Text to summarize
        max_length: Maximum summary length in words
    
    Returns:
        Summarized text
    """
    # Implement summarization
    return summarize(text, max_length)

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

---

## Step 3: Test the Worker Configuration

```bash
# Validate config
python -m maos.config.validate config.yaml

# Start with debug logging
DEBUG=true python -m maos.main --config config.yaml
```

---

## Step 4: Test the Worker

```bash
# Send a test request
curl -X POST http://localhost:7777/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Research the latest trends in AI agents"}
    ]
  }'
```

---

## Step 5: Customize Worker Behavior

### Different Frameworks

```yaml
agents:
  # Using OpenAI Agents SDK
  openai_worker:
    kind: native_worker
    framework: openai
    llm: default
    skillset: researcher
    system_prompt: "..."

  # Using lightweight TinyAgent
  light_worker:
    kind: native_worker
    framework: tinyagent
    llm: local  # Use local Ollama
    skillset: researcher
    system_prompt: "..."
```

### Custom Timeout and Retry

```yaml
agents:
  careful_worker:
    kind: native_worker
    framework: langchain
    llm: default
    skillset: researcher
    system_prompt: "..."
    timeout_seconds: 300  # 5 minutes
    retry_policy:
      max_retries: 3
      retry_delay_seconds: 2.0
      exponential_backoff: true
```

---

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| "Skillset not found" | Typo in skillset name | Check spelling matches |
| "Tool timeout" | MCP server slow | Increase timeout or optimize server |
| "LLM not found" | Missing LLM config | Add LLM to `llms` section |
| Worker not routing | Missing description | Add clear `description` field |

---

# D61: Implementing an External A2A Agent (Individual)

## Overview

This guide shows how to create a standalone A2A agent that can be discovered and used by the orchestration system.

---

## Step 1: Create the Agent Card

```json
// .well-known/agent.json
{
  "protocolVersion": "1.0",
  "name": "data-analysis-agent",
  "description": "Specialized agent for analyzing datasets and creating visualizations",
  "version": "1.0.0",
  "supportedInterfaces": [
    {
      "url": "http://localhost:9010/a2a",
      "protocolBinding": "JSONRPC"
    }
  ],
  "capabilities": {
    "streaming": true,
    "pushNotifications": false,
    "stateTransitionHistory": false
  },
  "defaultInputModes": ["text/plain", "application/json"],
  "defaultOutputModes": ["text/plain", "application/json"],
  "skills": [
    {
      "id": "analyze-data",
      "name": "Data Analysis",
      "description": "Analyze datasets and provide insights",
      "tags": ["analytics", "data", "insights"],
      "examples": [
        "Analyze this CSV data",
        "Find patterns in the dataset"
      ]
    },
    {
      "id": "create-chart",
      "name": "Chart Creation",
      "description": "Create visualizations from data",
      "tags": ["visualization", "charts"],
      "examples": [
        "Create a bar chart of sales",
        "Plot the trend over time"
      ]
    }
  ]
}
```

---

## Step 2: Implement the Agent Server

```python
# agent_server.py

import asyncio
from typing import Any, Dict
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from starlette.requests import Request
import json

# Load agent card
with open(".well-known/agent.json") as f:
    AGENT_CARD = json.load(f)

class DataAnalysisAgent:
    """The actual agent implementation."""
    
    async def process(self, message: str) -> str:
        """Process incoming message and return response."""
        # Your agent logic here
        if "analyze" in message.lower():
            return await self._analyze_data(message)
        elif "chart" in message.lower():
            return await self._create_chart(message)
        else:
            return "I can help with data analysis and visualization. What would you like me to do?"
    
    async def _analyze_data(self, message: str) -> str:
        # Implement data analysis
        return "Analysis complete: [your results here]"
    
    async def _create_chart(self, message: str) -> str:
        # Implement chart creation
        return "Chart created: [chart description or URL]"

agent = DataAnalysisAgent()

# A2A Endpoint Handlers
async def agent_card_endpoint(request: Request) -> JSONResponse:
    """Serve the Agent Card at /.well-known/agent.json"""
    return JSONResponse(AGENT_CARD)

async def a2a_endpoint(request: Request) -> JSONResponse:
    """Handle A2A JSON-RPC requests."""
    body = await request.json()
    
    method = body.get("method")
    params = body.get("params", {})
    request_id = body.get("id")
    
    if method == "message/send":
        # Extract message content
        message = params.get("message", {})
        parts = message.get("parts", [])
        text_content = " ".join(
            p.get("text", "") for p in parts if p.get("type") == "text"
        )
        
        # Process with agent
        result = await agent.process(text_content)
        
        # Return A2A response
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "task": {
                    "id": f"task-{request_id}",
                    "status": "COMPLETED",
                    "result": {
                        "role": "agent",
                        "parts": [{"type": "text", "text": result}]
                    }
                }
            }
        })
    
    return JSONResponse({
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"}
    })

# Create Starlette app
app = Starlette(
    routes=[
        Route("/.well-known/agent.json", agent_card_endpoint),
        Route("/a2a", a2a_endpoint, methods=["POST"]),
    ]
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9010)
```

---

## Step 3: Configure Discovery in Orchestrator

```yaml
# In main orchestrator config.yaml
a2a:
  discovery:
    seeds:
      - "http://localhost:9010"  # Your agent URL
    well_known_paths:
      - "/.well-known/agent.json"
    timeout_seconds: 10

  import_policy:
    enabled: true
    mode: langgraph_nodes  # or tools_only
    include_tags: ["analytics"]  # Match your agent's tags
```

---

## Step 4: Test the Agent

```bash
# Start the agent
python agent_server.py

# Test Agent Card
curl http://localhost:9010/.well-known/agent.json

# Test A2A endpoint
curl -X POST http://localhost:9010/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "id": "test-1",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"type": "text", "text": "Analyze my sales data"}]
      }
    }
  }'
```

---

# D62: Implementing an A2A Host (Multi-Agent)

## Overview

This guide shows how to host multiple A2A agents on a single server with a host index.

---

## Step 1: Create Host Index

```json
// /a2a/index.json
{
  "version": "1.0",
  "host": {
    "name": "Analytics Agent Host",
    "description": "Specialized analytics agents",
    "base_url": "http://localhost:9001"
  },
  "agents": [
    {
      "name": "data-analyzer",
      "path": "/a2a/data-analyzer",
      "agent_card_path": "/a2a/data-analyzer/.well-known/agent.json",
      "description": "Data analysis agent",
      "tags": ["analytics", "data"]
    },
    {
      "name": "ml-predictor",
      "path": "/a2a/ml-predictor",
      "agent_card_path": "/a2a/ml-predictor/.well-known/agent.json",
      "description": "ML prediction agent",
      "tags": ["ml", "prediction"]
    }
  ]
}
```

---

## Step 2: Implement Multi-Agent Host

```python
# host_server.py

from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
from starlette.requests import Request
import json

# Host index
HOST_INDEX = {
    "version": "1.0",
    "host": {
        "name": "Analytics Agent Host",
        "description": "Specialized analytics agents",
        "base_url": "http://localhost:9001"
    },
    "agents": [
        {
            "name": "data-analyzer",
            "path": "/a2a/data-analyzer",
            "agent_card_path": "/a2a/data-analyzer/.well-known/agent.json",
            "tags": ["analytics", "data"]
        },
        {
            "name": "ml-predictor",
            "path": "/a2a/ml-predictor",
            "agent_card_path": "/a2a/ml-predictor/.well-known/agent.json",
            "tags": ["ml", "prediction"]
        }
    ]
}

# Agent cards
AGENT_CARDS = {
    "data-analyzer": {
        "protocolVersion": "1.0",
        "name": "data-analyzer",
        "description": "Analyzes datasets",
        "version": "1.0.0",
        "supportedInterfaces": [
            {"url": "http://localhost:9001/a2a/data-analyzer", "protocolBinding": "JSONRPC"}
        ],
        "skills": [
            {"id": "analyze", "name": "Data Analysis", "tags": ["analytics"]}
        ]
    },
    "ml-predictor": {
        "protocolVersion": "1.0",
        "name": "ml-predictor",
        "description": "ML predictions",
        "version": "1.0.0",
        "supportedInterfaces": [
            {"url": "http://localhost:9001/a2a/ml-predictor", "protocolBinding": "JSONRPC"}
        ],
        "skills": [
            {"id": "predict", "name": "ML Prediction", "tags": ["ml"]}
        ]
    }
}

# Agent implementations
class DataAnalyzerAgent:
    async def process(self, message: str) -> str:
        return f"Data analysis result for: {message}"

class MLPredictorAgent:
    async def process(self, message: str) -> str:
        return f"ML prediction for: {message}"

AGENTS = {
    "data-analyzer": DataAnalyzerAgent(),
    "ml-predictor": MLPredictorAgent()
}

# Handlers
async def host_index(request: Request) -> JSONResponse:
    """Serve host index at /a2a/index.json"""
    return JSONResponse(HOST_INDEX)

async def agent_card(request: Request) -> JSONResponse:
    """Serve agent card at /a2a/{agent}/.well-known/agent.json"""
    agent_name = request.path_params["agent"]
    card = AGENT_CARDS.get(agent_name)
    if card:
        return JSONResponse(card)
    return JSONResponse({"error": "Agent not found"}, status_code=404)

async def agent_endpoint(request: Request) -> JSONResponse:
    """Handle A2A requests at /a2a/{agent}"""
    agent_name = request.path_params["agent"]
    agent = AGENTS.get(agent_name)
    
    if not agent:
        return JSONResponse({"error": "Agent not found"}, status_code=404)
    
    body = await request.json()
    request_id = body.get("id")
    params = body.get("params", {})
    
    # Extract message
    message = params.get("message", {})
    parts = message.get("parts", [])
    text = " ".join(p.get("text", "") for p in parts if p.get("type") == "text")
    
    # Process
    result = await agent.process(text)
    
    return JSONResponse({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "task": {
                "id": f"task-{request_id}",
                "status": "COMPLETED",
                "result": {
                    "role": "agent",
                    "parts": [{"type": "text", "text": result}]
                }
            }
        }
    })

# App
app = Starlette(routes=[
    Route("/a2a/index.json", host_index),
    Route("/a2a/{agent}/.well-known/agent.json", agent_card),
    Route("/a2a/{agent}", agent_endpoint, methods=["POST"]),
])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001)
```

---

## Step 3: Configure Discovery

```yaml
a2a:
  discovery:
    seeds:
      - "http://localhost:9001"  # Host URL
    host_index_path: "/a2a/index.json"
    well_known_paths:
      - "/.well-known/agent.json"
```

---

# D63: Adding a New MCP Server

## Overview

This guide shows how to create a custom MCP server to expose tools.

---

## Step 1: Create MCP Server

```python
# mcp_server_custom/__main__.py

from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel
from typing import Optional
import asyncio

mcp = FastMCP("Custom Tools Server")

# Simple tool
@mcp.tool()
def hello_world(name: str) -> str:
    """
    Say hello to someone.
    
    Args:
        name: Name to greet
    
    Returns:
        Greeting message
    """
    return f"Hello, {name}!"

# Async tool with progress
@mcp.tool()
async def long_running_task(input_data: str, ctx: Context) -> str:
    """
    A long-running task with progress reporting.
    
    Args:
        input_data: Data to process
    
    Returns:
        Processing result
    """
    total_steps = 5
    
    for i in range(total_steps):
        await ctx.report_progress(progress=i/total_steps, total=1.0)
        await ctx.info(f"Processing step {i+1}/{total_steps}")
        await asyncio.sleep(1)  # Simulate work
    
    return f"Processed: {input_data}"

# Tool with complex input
class AnalysisParams(BaseModel):
    data: str
    depth: int = 1
    include_summary: bool = True

@mcp.tool()
def analyze_data(params: AnalysisParams) -> dict:
    """
    Analyze data with configurable options.
    
    Args:
        params: Analysis parameters
    
    Returns:
        Analysis results
    """
    result = {
        "input_length": len(params.data),
        "depth": params.depth,
    }
    
    if params.include_summary:
        result["summary"] = params.data[:100] + "..."
    
    return result

# Resource (data the agent can read)
@mcp.resource("config://settings")
def get_settings() -> str:
    """Get server configuration."""
    return '{"version": "1.0", "max_depth": 10}'

# Run server
if __name__ == "__main__":
    import sys
    
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)
```

---

## Step 2: Configure in System

```yaml
mcp_servers:
  custom:
    transport: stdio
    command: ["python", "-m", "mcp_server_custom"]
    timeout_seconds: 60

tools:
  hello:
    server: custom
    tool_name: "hello_world"
  
  analyze:
    server: custom
    tool_name: "analyze_data"
  
  long_task:
    server: custom
    tool_name: "long_running_task"
    timeout_seconds: 120  # Override for slow tool
```

---

## Step 3: Test MCP Server

```bash
# Test standalone
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | \
  python -m mcp_server_custom

# Test tool call
echo '{"jsonrpc":"2.0","method":"tools/call","id":2,"params":{"name":"hello_world","arguments":{"name":"World"}}}' | \
  python -m mcp_server_custom
```

---

# D64: Adding a New LLM Provider

## Overview

This guide shows how to add support for a new LLM provider.

---

## Step 1: Create Provider Adapter

```python
# maos/llm/adapters/newprovider.py

from typing import List, Optional, AsyncIterator
from maos.llm.base import LLMAdapter, LLMResponse, LLMChunk
from maos.config.models import LLMConfig
from maos.tools.models import Tool
from maos.graph.state import Message
import os

class NewProviderAdapter(LLMAdapter):
    """Adapter for NewProvider API."""
    
    def __init__(self, config: LLMConfig):
        from newprovider import Client  # Import provider SDK
        
        api_key = os.getenv(config.api_key_env or "NEWPROVIDER_API_KEY")
        if not api_key:
            raise ValueError(f"Missing API key: {config.api_key_env}")
        
        self._client = Client(api_key=api_key)
        self._model = config.model
        self._temperature = config.temperature
        self._max_tokens = config.max_tokens
    
    async def invoke(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None
    ) -> LLMResponse:
        """Invoke LLM and return response."""
        
        # Convert messages to provider format
        provider_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
        
        # Convert tools if provided
        provider_tools = None
        if tools:
            provider_tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema.dict()
                }
                for t in tools
            ]
        
        # Make API call
        response = await self._client.chat.create(
            model=self._model,
            messages=provider_messages,
            tools=provider_tools,
            temperature=self._temperature,
            max_tokens=self._max_tokens
        )
        
        # Convert response
        return LLMResponse(
            content=response.choices[0].message.content,
            tool_calls=self._extract_tool_calls(response),
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens
            }
        )
    
    async def stream(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None
    ) -> AsyncIterator[LLMChunk]:
        """Stream LLM response."""
        
        provider_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
        
        async for chunk in self._client.chat.create_stream(
            model=self._model,
            messages=provider_messages,
            temperature=self._temperature
        ):
            yield LLMChunk(
                content=chunk.delta.content or "",
                done=chunk.finish_reason is not None
            )
    
    def _extract_tool_calls(self, response) -> List[dict]:
        """Extract tool calls from response."""
        tool_calls = []
        message = response.choices[0].message
        
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments
                })
        
        return tool_calls
```

---

## Step 2: Register Adapter

```python
# maos/llm/factory.py

from maos.llm.adapters.newprovider import NewProviderAdapter

PROVIDER_ADAPTERS = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "google": GoogleAdapter,
    "ollama": OllamaAdapter,
    "newprovider": NewProviderAdapter,  # Add here
}
```

---

## Step 3: Update Dependencies

```
# requirements.txt
newprovider-sdk>=1.0.0
```

---

## Step 4: Use in Config

```yaml
llms:
  my_newprovider:
    provider: newprovider
    model: newprovider-large-v2
    api_key_env: NEWPROVIDER_API_KEY
    temperature: 0.7
    max_tokens: 4096

agents:
  my_agent:
    kind: native_worker
    llm: my_newprovider  # Use new provider
    # ...
```

---

# D65: Config-Driven Customization Examples

## Overview

Real-world configuration scenarios demonstrating the system's flexibility.

---

## Scenario 1: Development vs Production

```yaml
# config.dev.yaml - Development configuration
llms:
  default:
    provider: ollama  # Use local LLM
    model: qwen2.5:7b
    base_url: "http://localhost:11434/v1"

graph:
  max_iterations: 20  # More iterations for debugging
  timeouts:
    tool_call_seconds: 120  # Longer for slow dev machines

serving:
  api:
    host: "127.0.0.1"  # Local only
    port: 7777
```

```yaml
# config.prod.yaml - Production configuration
llms:
  default:
    provider: openai
    model: gpt-4o
    temperature: 0.3  # More deterministic

graph:
  max_iterations: 10
  timeouts:
    tool_call_seconds: 30  # Stricter

serving:
  api:
    host: "0.0.0.0"
    port: 7777
    cors_origins:
      - "https://app.company.com"
```

---

## Scenario 2: Team Specialization

```yaml
# Research team configuration
agents:
  supervisor:
    kind: supervisor
    llm: gpt4
    system_prompt: |
      You coordinate a research team. Route to:
      - academic_researcher: For scholarly sources
      - web_researcher: For general web search
      - fact_checker: For verification

  academic_researcher:
    kind: native_worker
    framework: langchain
    llm: claude  # Claude for nuanced analysis
    skillset: academic_research
    system_prompt: "Focus on peer-reviewed sources..."

  web_researcher:
    kind: native_worker
    framework: tinyagent
    llm: gemini_flash  # Fast for web search
    skillset: web_research
    system_prompt: "Search broadly, cite sources..."

  fact_checker:
    kind: native_worker
    framework: openai
    llm: gpt4
    skillset: verification
    system_prompt: "Verify claims, check multiple sources..."
```

---

## Scenario 3: Cost Optimization

```yaml
# Tiered LLM usage for cost control
llms:
  expensive:
    provider: openai
    model: gpt-4o
    temperature: 0.3

  cheap:
    provider: ollama
    model: llama3:8b
    base_url: "http://localhost:11434/v1"

  medium:
    provider: google
    model: gemini-1.5-flash
    temperature: 0.5

agents:
  supervisor:
    kind: supervisor
    llm: medium  # Medium cost for routing

  complex_agent:
    kind: native_worker
    llm: expensive  # GPT-4 for complex tasks
    skillset: complex_analysis

  simple_agent:
    kind: native_worker
    llm: cheap  # Local LLM for simple tasks
    skillset: basic_tasks

  general_agent:
    kind: native_worker
    llm: medium  # Gemini Flash for general use
    skillset: general
```

---

## Scenario 4: Hybrid Internal/External

```yaml
# Mix native workers with external specialists
agents:
  supervisor:
    kind: supervisor
    llm: default
    system_prompt: |
      You have both internal workers and external specialists.
      Use internal for general tasks, external for specialized needs.
      External agents are prefixed with ext::

  # Internal workers
  general_assistant:
    kind: native_worker
    llm: default
    skillset: general

  # External agents discovered from:
a2a:
  discovery:
    seeds:
      - "http://legal-agent.internal:9001"  # Legal specialist
      - "http://finance-agent.internal:9002"  # Finance specialist
  
  import_policy:
    enabled: true
    mode: langgraph_nodes
    include_tags: ["approved", "internal"]
```

---

## Scenario 5: Feature Flags via Config

```yaml
# Enable/disable features through config

# Feature: External agents
a2a:
  import_policy:
    enabled: false  # Disable external agents

# Feature: Specific workers
native_workers:
  ignore_workers:
    - experimental_agent  # Disable experimental worker
    - deprecated_agent    # Disable deprecated worker

# Feature: Streaming
# (Controlled at API level based on client capability)

# Feature: Tool access
skills:
  restricted_ops:
    tools: []  # Empty = disabled skill
```

---

## Scenario 6: Multi-Region Deployment

```yaml
# Region-specific configuration

# US Region
llms:
  default:
    provider: openai
    model: gpt-4o
    # US endpoint (default)

# EU Region (data residency)
llms:
  default:
    provider: azure_openai
    model: gpt-4-eu
    base_url: "https://eu-instance.openai.azure.com"
    api_key_env: AZURE_OPENAI_EU_KEY

# APAC Region (latency optimization)
llms:
  default:
    provider: google
    model: gemini-1.5-pro
    # Google's APAC endpoints
```

---

## Related Documents

- D27: Config Examples Catalog
- D51: Local Development Setup
- D58: Extensibility Guide

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Architecture Team | Initial draft |
