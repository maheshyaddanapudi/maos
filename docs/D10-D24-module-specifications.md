# D10-D24: Module Specifications (Low-Level Design)

## Config-Driven Multi-Agent Orchestration System

**Document ID:** D10-D24  
**Version:** 1.0  
**Status:** Draft  
**Last Updated:** January 2026

---

## Module Index

| Doc ID | Module | Responsibility |
|--------|--------|----------------|
| D10 | ConfigLoader | YAML/JSON parsing, validation |
| D11 | LLMFactory & Registry | Provider abstraction, client management |
| D12 | MCPRegistry | MCP server connection management |
| D13 | ToolRegistry | Tool materialization from MCP |
| D14 | SkillRegistry | Tool → Skill composition |
| D15 | SkillsetRegistry | Skill → Skillset composition |
| D16 | AgentFactory | Any-Agent instantiation |
| D17 | A2ADiscovery | Agent Card fetching, import policy |
| D18 | GraphFactory | LangGraph construction |
| D19 | SupervisorNode | Routing logic, send_message |
| D20 | NativeWorkerNode | Any-Agent wrapper |
| D21 | ExternalAgentNode | A2A client wrapper |
| D22 | A2AHostServer | Multi-agent host implementation |
| D23 | A2AIndividualServer | Single-agent server implementation |
| D24 | APIServer | FastAPI endpoints, streaming |

---

## D10: ConfigLoader

### Purpose
Load, parse, and validate configuration from YAML/JSON files.

### Interface

```python
class ConfigLoader:
    """Load and validate configuration files."""
    
    def __init__(self, schema_path: Optional[str] = None):
        """Initialize with optional custom schema path."""
    
    def load(self, config_path: str) -> Config:
        """
        Load configuration from file.
        
        Args:
            config_path: Path to YAML or JSON config file
            
        Returns:
            Validated Config object
            
        Raises:
            ConfigError: If file not found or invalid
            ValidationError: If schema validation fails
        """
    
    def load_from_string(self, content: str, format: str = "yaml") -> Config:
        """Load configuration from string content."""
    
    def validate(self, config_dict: dict) -> List[ValidationError]:
        """Validate config dict against schema."""
    
    def merge_with_env(self, config: Config) -> Config:
        """Override config values from environment variables."""
```

### Dependencies
- `pyyaml`: YAML parsing
- `jsonschema`: Schema validation
- `pydantic`: Config models

### Configuration
```yaml
# ConfigLoader behavior
config:
  schema_validation: strict  # strict, warn, none
  env_override_prefix: "MAOS_"  # Prefix for env var overrides
  include_support: true  # Support !include directive
```

### Error Handling
| Error | Cause | Recovery |
|-------|-------|----------|
| `FileNotFoundError` | Config file missing | Fail with clear path |
| `YAMLParseError` | Invalid YAML syntax | Fail with line number |
| `ValidationError` | Schema violation | Fail with field path |

---

## D11: LLMFactory & LLMRegistry

### Purpose
Create and manage LLM provider clients with unified interface.

### Interface

```python
class LLMFactory:
    """Factory for creating LLM clients."""
    
    @staticmethod
    def create(config: LLMConfig) -> LLMClient:
        """
        Create LLM client from configuration.
        
        Args:
            config: LLM configuration with provider, model, etc.
            
        Returns:
            Configured LLM client
        """
    
    @staticmethod
    def get_provider_adapter(provider: str) -> ProviderAdapter:
        """Get adapter for specific provider."""

class LLMRegistry:
    """Registry of configured LLM clients."""
    
    def __init__(self):
        self._clients: Dict[str, LLMClient] = {}
    
    def build(self, llm_configs: Dict[str, LLMConfig]) -> None:
        """Build registry from configuration."""
    
    def get(self, name: str) -> LLMClient:
        """Get LLM client by config name."""
    
    def get_default(self) -> LLMClient:
        """Get default LLM client."""

class LLMClient(Protocol):
    """Unified LLM client interface."""
    
    async def invoke(
        self, 
        messages: List[Message],
        tools: Optional[List[Tool]] = None
    ) -> LLMResponse:
        """Invoke LLM with messages."""
    
    async def stream(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None
    ) -> AsyncIterator[LLMChunk]:
        """Stream LLM response."""
```

### Provider Adapters

| Provider | Adapter Class | Auth Method |
|----------|---------------|-------------|
| OpenAI | `OpenAIAdapter` | Bearer token |
| Anthropic | `AnthropicAdapter` | x-api-key header |
| Google | `GoogleAdapter` | API key |
| Ollama | `OllamaAdapter` | None (local) |
| Azure | `AzureOpenAIAdapter` | Azure AD or key |

### Dependencies
- `openai`: OpenAI client
- `anthropic`: Anthropic client
- `google-generativeai`: Google client
- `langchain-*`: LangChain adapters

---

## D12: MCPRegistry

### Purpose
Manage connections to MCP servers and provide tool handles.

### Interface

```python
class MCPRegistry:
    """Registry of MCP server connections."""
    
    def __init__(self):
        self._connections: Dict[str, MCPConnection] = {}
    
    async def connect_all(self, configs: Dict[str, MCPServerConfig]) -> None:
        """Connect to all configured MCP servers."""
    
    async def connect(self, name: str, config: MCPServerConfig) -> MCPConnection:
        """Connect to a single MCP server."""
    
    def get_connection(self, name: str) -> MCPConnection:
        """Get connection by server name."""
    
    async def get_tools(self, server_name: str) -> List[MCPToolDef]:
        """Get tool definitions from a server."""
    
    async def disconnect_all(self) -> None:
        """Disconnect all servers."""

class MCPConnection:
    """Connection to a single MCP server."""
    
    transport: str  # "stdio" or "http"
    status: ConnectionStatus
    tools: List[MCPToolDef]
    
    async def invoke_tool(
        self, 
        tool_name: str, 
        arguments: Dict[str, Any]
    ) -> Any:
        """Invoke a tool on this server."""
```

### Transport Implementations

```python
class StdioTransport:
    """MCP transport over stdin/stdout."""
    
    async def spawn(self, command: List[str], env: Dict[str, str]) -> None:
        """Spawn subprocess."""
    
    async def send(self, message: dict) -> None:
        """Send JSON-RPC message via stdin."""
    
    async def receive(self) -> dict:
        """Receive JSON-RPC message from stdout."""

class HTTPTransport:
    """MCP transport over HTTP/SSE."""
    
    async def connect(self, url: str) -> None:
        """Connect to HTTP endpoint."""
    
    async def send(self, message: dict) -> dict:
        """Send request and get response."""
```

---

## D13: ToolRegistry

### Purpose
Materialize tools from MCP servers into callable objects.

### Interface

```python
class ToolRegistry:
    """Registry of materialized tools."""
    
    def __init__(self, mcp_registry: MCPRegistry):
        self._mcp_registry = mcp_registry
        self._tools: Dict[str, Tool] = {}
    
    async def materialize(self, tool_configs: Dict[str, ToolConfig]) -> None:
        """
        Materialize tools from configuration.
        
        For each tool config:
        1. Get connection from MCP registry
        2. Fetch tool definition from server
        3. Create Tool object with invocation handle
        """
    
    def get(self, tool_id: str) -> Optional[Tool]:
        """Get tool by ID."""
    
    def list_all(self) -> List[Tool]:
        """List all registered tools."""
    
    def list_by_server(self, server: str) -> List[Tool]:
        """List tools from specific server."""
```

### Tool Materialization Process

1. Read tool config (`server`, `tool_name`)
2. Get MCP connection from registry
3. Verify tool exists on server (`tools/list`)
4. Fetch tool schema
5. Create `Tool` object with:
   - ID from config key
   - Schema from MCP
   - Invoke handle bound to connection

---

## D14: SkillRegistry

### Purpose
Compose tools into named skills.

### Interface

```python
class SkillRegistry:
    """Registry of skills (tool groupings)."""
    
    def __init__(self, tool_registry: ToolRegistry):
        self._tool_registry = tool_registry
        self._skills: Dict[str, Skill] = {}
    
    def build(self, skill_configs: Dict[str, SkillConfig]) -> None:
        """Build skills from configuration."""
    
    def get(self, name: str) -> Optional[Skill]:
        """Get skill by name."""
    
    def get_tools_for_skill(self, name: str) -> List[Tool]:
        """Get resolved tools for a skill."""
    
    def find_skills_with_tool(self, tool_id: str) -> List[Skill]:
        """Find skills containing a specific tool."""
```

### Validation Rules
- All tool IDs in skill must exist in ToolRegistry
- Warn if skill has zero tools
- Allow same tool in multiple skills (tool overlap OK)

---

## D15: SkillsetRegistry

### Purpose
Compose skills into named skillsets for agents.

### Interface

```python
class SkillsetRegistry:
    """Registry of skillsets (skill groupings)."""
    
    def __init__(self, skill_registry: SkillRegistry):
        self._skill_registry = skill_registry
        self._skillsets: Dict[str, Skillset] = {}
    
    def build(self, skillset_configs: Dict[str, SkillsetConfig]) -> None:
        """Build skillsets from configuration."""
    
    def get(self, name: str) -> Optional[Skillset]:
        """Get skillset by name."""
    
    def get_all_tools(self, name: str) -> List[Tool]:
        """Get all tools across all skills in skillset."""
    
    def get_skill_names(self, name: str) -> List[str]:
        """Get skill names for matching external agents."""
```

---

## D16: AgentFactory

### Purpose
Instantiate Any-Agent workers with tools, prompts, and LLM.

### Interface

```python
class AgentFactory:
    """Factory for creating agents via Any-Agent."""
    
    def __init__(
        self,
        llm_registry: LLMRegistry,
        skillset_registry: SkillsetRegistry,
        tool_registry: ToolRegistry
    ):
        self._llm_registry = llm_registry
        self._skillset_registry = skillset_registry
        self._tool_registry = tool_registry
    
    async def create_agent(self, config: AgentConfig) -> Agent:
        """
        Create an agent from configuration.
        
        Steps:
        1. Resolve LLM from registry
        2. Resolve skillset → skills → tools
        3. Convert tools to Any-Agent format
        4. Create AgentConfig
        5. Instantiate via AnyAgent.create_async()
        """
    
    def get_framework(self, config: AgentConfig) -> str:
        """Get framework string for Any-Agent."""
    
    def build_tool_list(self, config: AgentConfig) -> List:
        """Build tool list for Any-Agent (MCP configs + direct tools)."""
```

### Framework Mapping

| Config Framework | Any-Agent Framework | Notes |
|------------------|---------------------|-------|
| `langchain` | `"langchain"` | Default |
| `openai` | `"openai"` | OpenAI Agents SDK |
| `google` | `"google"` | Google ADK |
| `tinyagent` | `"tinyagent"` | Lightweight |

---

## D17: A2ADiscovery

### Purpose
Discover external A2A agents from seed URLs and apply import policy.

### Interface

```python
class A2ADiscovery:
    """Discover and import external A2A agents."""
    
    def __init__(self, http_client: httpx.AsyncClient):
        self._http_client = http_client
    
    async def discover(self, config: A2AConfig) -> List[DiscoveredAgent]:
        """
        Discover agents from seed URLs.
        
        Steps:
        1. For each seed URL:
           a. Try to fetch host index
           b. If not found, try Agent Card directly
        2. Parse all Agent Cards
        3. Apply import policy
        4. Return filtered list
        """
    
    async def fetch_host_index(self, url: str) -> Optional[HostIndex]:
        """Fetch multi-agent host index."""
    
    async def fetch_agent_card(self, url: str) -> Optional[AgentCard]:
        """Fetch individual Agent Card."""
    
    def apply_policy(
        self, 
        agents: List[DiscoveredAgent],
        policy: A2AImportPolicy
    ) -> List[DiscoveredAgent]:
        """Apply import policy filters."""

class DiscoveredAgent:
    """An agent discovered via A2A."""
    card: AgentCard
    source_url: str
    endpoint: str
    import_mode: str  # "node" or "tool"
    assigned_to: Optional[str]  # Worker name for tools_only
```

### Import Policy Logic

```python
def apply_policy(agents, policy):
    filtered = agents
    
    # Filter by tags
    if policy.include_tags:
        filtered = [a for a in filtered 
                    if any(t in a.card.all_tags for t in policy.include_tags)]
    
    if policy.exclude_tags:
        filtered = [a for a in filtered 
                    if not any(t in a.card.all_tags for t in policy.exclude_tags)]
    
    # Filter by names
    if policy.include_names:
        filtered = [a for a in filtered if a.card.name in policy.include_names]
    
    if policy.exclude_names:
        filtered = [a for a in filtered if a.card.name not in policy.exclude_names]
    
    # Apply limit
    return filtered[:policy.max_agents]
```

---

## D18: GraphFactory

### Purpose
Construct LangGraph with supervisor, workers, and external nodes.

### Interface

```python
class GraphFactory:
    """Factory for building LangGraph."""
    
    def __init__(
        self,
        agent_registry: AgentRegistry,
        graph_config: GraphConfig
    ):
        self._agent_registry = agent_registry
        self._graph_config = graph_config
    
    def build(self) -> CompiledGraph:
        """
        Build and compile the LangGraph.
        
        Steps:
        1. Create StateGraph with schema
        2. Add supervisor node
        3. Add native worker nodes
        4. Add external agent nodes
        5. Add conditional edges from supervisor
        6. Set entry point
        7. Compile and return
        """
    
    def create_supervisor_node(self) -> Callable:
        """Create supervisor node function."""
    
    def create_worker_node(self, agent: Agent) -> Callable:
        """Create worker node function wrapping Any-Agent."""
    
    def create_external_node(self, agent: DiscoveredAgent) -> Callable:
        """Create external node function with A2A client."""
    
    def build_roster_prompt(self) -> str:
        """Build roster string for supervisor prompt."""
```

### Graph Structure

```python
def build(self) -> CompiledGraph:
    # Create graph
    graph = StateGraph(GraphState)
    
    # Add nodes
    graph.add_node("supervisor", self.create_supervisor_node())
    
    for name, agent in self._agent_registry.get_workers():
        graph.add_node(name, self.create_worker_node(agent))
    
    for name, agent in self._agent_registry.get_externals():
        graph.add_node(name, self.create_external_node(agent))
    
    # Add edges
    graph.add_conditional_edges(
        "supervisor",
        self.route_from_supervisor,
        {name: name for name in all_worker_names} | {"END": END}
    )
    
    for name in all_worker_names:
        graph.add_edge(name, "supervisor")
    
    # Set entry and compile
    graph.set_entry_point("supervisor")
    return graph.compile()
```

---

## D19: SupervisorNode

### Purpose
Implement supervisor routing logic and send_message tool.

### Interface

```python
class SupervisorNode:
    """Supervisor node implementation."""
    
    def __init__(
        self,
        llm: LLMClient,
        roster: List[str],
        system_prompt: str,
        max_iterations: int
    ):
        self._llm = llm
        self._roster = roster
        self._system_prompt = system_prompt
        self._max_iterations = max_iterations
    
    async def run(self, state: GraphState) -> GraphState:
        """
        Execute supervisor logic.
        
        1. Check iteration limit
        2. Build prompt with roster
        3. Invoke LLM for routing decision
        4. Handle send_message if used
        5. Return updated state with next node
        """
    
    def build_prompt(self, state: GraphState) -> str:
        """Build prompt with roster and current state."""
    
    def parse_routing_decision(self, response: str) -> str:
        """Parse LLM response to get next node name."""
    
    async def handle_send_message(self, message: str) -> GraphState:
        """Handle human-in-the-loop request."""
```

### Routing Decision Format

```python
# Expected LLM output format
{
    "reasoning": "The user needs web research...",
    "next": "research_agent",  # or "END" or "AWAIT_INPUT"
    "message": "Optional message to user"
}
```

---

## D20: NativeWorkerNode

### Purpose
Wrap Any-Agent execution as a LangGraph node.

### Interface

```python
class NativeWorkerNode:
    """Native worker node wrapping Any-Agent."""
    
    def __init__(self, agent: Agent, name: str, timeout: int):
        self._agent = agent
        self._name = name
        self._timeout = timeout
    
    async def run(self, state: GraphState) -> GraphState:
        """
        Execute worker agent.
        
        1. Extract task from state
        2. Invoke Any-Agent with task
        3. Capture tool calls and results
        4. Build WorkerResult
        5. Return updated state
        """
    
    async def execute_with_timeout(self, task: str) -> WorkerResult:
        """Execute with timeout handling."""
    
    def build_result(
        self, 
        output: str, 
        tool_calls: List[ToolCallRecord]
    ) -> WorkerResult:
        """Build standardized WorkerResult."""
```

---

## D21: ExternalAgentNode

### Purpose
Wrap A2A client call as a LangGraph node.

### Interface

```python
class ExternalAgentNode:
    """External agent node using A2A protocol."""
    
    def __init__(
        self, 
        agent: DiscoveredAgent,
        http_client: httpx.AsyncClient,
        timeout: int
    ):
        self._agent = agent
        self._http_client = http_client
        self._timeout = timeout
    
    async def run(self, state: GraphState) -> GraphState:
        """
        Execute external agent via A2A.
        
        1. Build A2A request from state
        2. Send to external agent endpoint
        3. Handle streaming or sync response
        4. Convert to WorkerResult
        5. Return updated state
        """
    
    async def send_message(self, content: str) -> A2AResponse:
        """Send message/send to external agent."""
    
    async def stream_message(self, content: str) -> AsyncIterator[str]:
        """Stream message from external agent."""
    
    def convert_response(self, response: A2AResponse) -> WorkerResult:
        """Convert A2A response to WorkerResult."""
```

---

## D22: A2AHostServer

### Purpose
Serve multiple agents on a single host endpoint.

### Interface

```python
class A2AHostServer:
    """Multi-agent A2A host server."""
    
    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._agents: Dict[str, A2AAgentHandler] = {}
    
    def register_agent(self, name: str, handler: A2AAgentHandler) -> None:
        """Register an agent at /a2a/{name}/."""
    
    def get_index(self) -> HostIndex:
        """Get host index listing all agents."""
    
    async def start(self) -> None:
        """Start the server."""
    
    async def stop(self) -> None:
        """Stop the server."""

# Routes:
# GET /a2a/index.json -> HostIndex
# GET /a2a/{name}/.well-known/agent.json -> AgentCard
# POST /a2a/{name}/ -> A2A JSON-RPC endpoint
```

---

## D23: A2AIndividualServer

### Purpose
Serve a single agent as standalone A2A server.

### Interface

```python
class A2AIndividualServer:
    """Single-agent A2A server."""
    
    def __init__(
        self, 
        agent: Agent,
        card: AgentCard,
        host: str,
        port: int
    ):
        self._agent = agent
        self._card = card
        self._host = host
        self._port = port
    
    async def start(self) -> None:
        """Start serving the agent."""
    
    async def handle_request(self, request: A2ARequest) -> A2AResponse:
        """Handle incoming A2A request."""

# Routes:
# GET /.well-known/agent.json -> AgentCard
# POST / -> A2A JSON-RPC endpoint
```

---

## D24: APIServer

### Purpose
FastAPI server with chat, agents, and OpenAI-compatible endpoints.

### Interface

```python
class APIServer:
    """FastAPI application server."""
    
    def __init__(
        self,
        graph: CompiledGraph,
        agent_registry: AgentRegistry,
        serving_config: ServingConfig
    ):
        self._graph = graph
        self._agent_registry = agent_registry
        self._config = serving_config
        self._app = FastAPI()
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Configure API routes."""
    
    async def start(self) -> None:
        """Start the server."""
    
    # Endpoints
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """POST /chat - Main chat endpoint."""
    
    async def chat_stream(self, request: ChatRequest) -> StreamingResponse:
        """POST /chat with stream=true."""
    
    async def list_agents(self) -> AgentsResponse:
        """GET /agents - List available agents."""
    
    async def health(self) -> HealthResponse:
        """GET /health - Health check."""
    
    async def openai_chat(self, request: OpenAIChatRequest) -> OpenAIChatResponse:
        """POST /v1/chat/completions - OpenAI-compatible."""
```

### Endpoints Summary

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/chat` | Primary chat interface |
| GET | `/agents` | List workers and externals |
| GET | `/health` | Health check |
| POST | `/v1/chat/completions` | OpenAI-compatible facade |
| WS | `/ws/chat` | WebSocket chat (optional) |

---

## Related Documents

- D06: Component Overview
- D29-D33: API Specifications
- D45-D50: Data Models
- D60-D65: Implementation Guides

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Jan 2026 | Architecture Team | Initial draft |
