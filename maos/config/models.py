"""
MAOS Configuration Pydantic Models.

Defines all configuration structures as Pydantic v2 models.
"""

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai_compatible"
    AZURE_OPENAI = "azure_openai"


class LLMConfig(BaseModel):
    """Configuration for an LLM provider."""

    provider: LLMProvider = Field(..., description="LLM provider identifier")
    model: str = Field(..., description="Model identifier")
    base_url: str | None = Field(None, description="Base URL for OpenAI-compatible providers")
    api_key_env: str | None = Field(None, description="Environment variable name for API key")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int | None = Field(None, ge=1, description="Maximum tokens to generate")
    timeout_seconds: int = Field(default=60, ge=1, description="Request timeout")

    @field_validator("api_key_env", mode="before")
    @classmethod
    def set_default_api_key_env(cls, v: str | None, info) -> str | None:
        if v is not None:
            return v
        # Set default based on provider
        provider = info.data.get("provider")
        if provider == LLMProvider.OPENAI or provider == "openai":
            return "OPENAI_API_KEY"
        elif provider == LLMProvider.ANTHROPIC or provider == "anthropic":
            return "ANTHROPIC_API_KEY"
        elif provider == LLMProvider.GOOGLE or provider == "google":
            return "GOOGLE_API_KEY"
        return None


class MCPTransport(str, Enum):
    """MCP transport types."""
    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server connection."""

    transport: MCPTransport = Field(..., description="Transport mechanism")
    command: list[str] | None = Field(None, description="Command for stdio transport")
    url: str | None = Field(None, description="URL for HTTP/SSE transport")
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables")
    timeout_seconds: int = Field(default=30, ge=1, description="Connection timeout")

    @model_validator(mode="after")
    def validate_transport_requirements(self) -> "MCPServerConfig":
        if self.transport == MCPTransport.STDIO and not self.command:
            raise ValueError("command is required for stdio transport")
        if self.transport in (MCPTransport.HTTP, MCPTransport.SSE) and not self.url:
            raise ValueError("url is required for HTTP/SSE transport")
        return self


class ToolConfig(BaseModel):
    """Configuration mapping a tool ID to an MCP server tool."""

    server: str = Field(..., description="Reference to MCP server name")
    tool_name: str = Field(..., description="Tool name on the MCP server")
    description_override: str | None = Field(None, description="Override tool description")
    timeout_seconds: int | None = Field(None, ge=1, description="Tool execution timeout")


class SkillConfig(BaseModel):
    """A skill groups related tools."""

    tools: list[str] = Field(..., min_length=1, description="List of tool IDs")
    description: str = Field(default="", description="Human-readable description")


class SkillsetConfig(BaseModel):
    """A skillset groups related skills for an agent."""

    skills: list[str] = Field(..., min_length=1, description="List of skill names")
    description: str | None = Field(None, description="Human-readable description")


class AgentKind(str, Enum):
    """Type of agent."""
    SUPERVISOR = "supervisor"
    NATIVE_WORKER = "native_worker"


class AgentFramework(str, Enum):
    """Supported agent frameworks."""
    LANGCHAIN = "langchain"
    OPENAI = "openai"
    GOOGLE = "google"
    SMOLAGENTS = "smolagents"
    LLAMAINDEX = "llamaindex"
    AGNO = "agno"
    TINYAGENT = "tinyagent"


class RetryPolicy(BaseModel):
    """Retry configuration for agent/tool failures."""

    max_retries: int = Field(default=1, ge=0, le=5, description="Maximum retry attempts")
    retry_delay_seconds: float = Field(default=1.0, ge=0, description="Delay between retries")
    exponential_backoff: bool = Field(default=False, description="Use exponential backoff")


class AgentConfig(BaseModel):
    """Configuration for a native agent (supervisor or worker)."""

    kind: AgentKind = Field(..., description="Type of agent")
    framework: AgentFramework = Field(default=AgentFramework.LANGCHAIN, description="Agent framework")
    llm: str = Field(default="default", description="Reference to LLM config name")
    skillset: str | None = Field(None, description="Reference to skillset name")
    tools: list[str] | None = Field(None, description="Direct tool references")
    system_prompt: str = Field(..., description="System prompt for the agent")
    description: str | None = Field(None, description="Human-readable description for routing")
    timeout_seconds: int = Field(default=60, ge=1, description="Agent execution timeout")
    retry_policy: RetryPolicy | None = Field(None, description="Retry configuration")


class NativeWorkersConfig(BaseModel):
    """Configuration options for native workers."""

    ignore_workers: list[str] = Field(default_factory=list, description="Workers to exclude")


class A2ADiscoveryConfig(BaseModel):
    """Configuration for discovering external A2A agents."""

    seeds: list[str] = Field(default_factory=list, description="Seed URLs for discovery")
    well_known_paths: list[str] = Field(
        default=["/.well-known/agent.json"],
        description="Paths to check for Agent Cards"
    )
    host_index_path: str = Field(
        default="/a2a/index.json",
        description="Path for multi-agent host index"
    )
    timeout_seconds: int = Field(default=10, ge=1, description="Discovery timeout")
    parallel_discovery: bool = Field(default=True, description="Fetch cards in parallel")


class AssignmentStrategy(str, Enum):
    """Strategy for assigning external agent tools."""
    SKILL_OVERLAP = "skill_overlap"
    EXPLICIT = "explicit"
    SUPERVISOR = "supervisor"


class ImportMode(str, Enum):
    """How to import external agents."""
    LANGGRAPH_NODES = "langgraph_nodes"
    TOOLS_ONLY = "tools_only"


class ToolsAssignmentConfig(BaseModel):
    """Configuration for tools_only mode assignment."""

    strategy: AssignmentStrategy = Field(default=AssignmentStrategy.SKILL_OVERLAP)
    fallback: str = Field(default="supervisor", description="Fallback when no match")
    explicit: dict[str, str] = Field(default_factory=dict, description="Manual mapping")


class A2AImportPolicy(BaseModel):
    """Policy for importing discovered external agents."""

    enabled: bool = Field(default=True, description="Enable external agent import")
    mode: ImportMode = Field(default=ImportMode.LANGGRAPH_NODES, description="Import mode")
    tools_assignment: ToolsAssignmentConfig | None = Field(None, description="Tools assignment config")
    max_agents: int = Field(default=25, ge=1, le=100, description="Maximum agents to import")
    include_tags: list[str] = Field(default_factory=list, description="Only import these tags")
    exclude_tags: list[str] = Field(default_factory=list, description="Exclude these tags")
    include_names: list[str] = Field(default_factory=list, description="Only import these names")
    exclude_names: list[str] = Field(default_factory=list, description="Exclude these names")


class A2AConfig(BaseModel):
    """A2A external agent discovery and import configuration."""

    discovery: A2ADiscoveryConfig = Field(default_factory=A2ADiscoveryConfig)
    import_policy: A2AImportPolicy = Field(default_factory=A2AImportPolicy)


class TimeoutsConfig(BaseModel):
    """Timeout configuration."""

    worker_seconds: int = Field(default=60, ge=1, description="Worker execution timeout")
    tool_call_seconds: int = Field(default=30, ge=1, description="Tool call timeout")
    external_agent_seconds: int = Field(default=40, ge=1, description="External agent timeout")
    total_execution_seconds: int = Field(default=300, ge=1, description="Total execution timeout")


class GraphConfig(BaseModel):
    """LangGraph execution configuration."""

    max_iterations: int = Field(default=12, ge=1, le=100, description="Max supervisor iterations")
    timeouts: TimeoutsConfig = Field(default_factory=TimeoutsConfig)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)


class APIConfig(BaseModel):
    """API server configuration."""

    host: str = Field(default="127.0.0.1", description="Server host")
    port: int = Field(default=7777, ge=1, le=65535, description="Server port")
    cors_origins: list[str] = Field(default=["*"], description="CORS allowed origins")
    openai_compatible: bool = Field(default=True, description="Enable OpenAI-compatible endpoint")


class UIMode(str, Enum):
    """UI mode options."""
    NONE = "none"
    CHAINLIT = "chainlit"
    OPENWEBUI_COMPATIBLE = "openwebui_compatible"


class UIConfig(BaseModel):
    """UI configuration."""

    mode: UIMode = Field(default=UIMode.NONE, description="UI mode")


class ServingConfig(BaseModel):
    """API and UI serving configuration."""

    api: APIConfig = Field(default_factory=APIConfig)
    ui: UIConfig = Field(default_factory=UIConfig)


class Config(BaseModel):
    """Root configuration model."""

    llms: dict[str, LLMConfig] = Field(..., min_length=1, description="LLM configurations")
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict, description="MCP servers")
    tools: dict[str, ToolConfig] = Field(default_factory=dict, description="Tool definitions")
    skills: dict[str, SkillConfig] = Field(default_factory=dict, description="Skill definitions")
    skillsets: dict[str, SkillsetConfig] = Field(default_factory=dict, description="Skillset definitions")
    agents: dict[str, AgentConfig] = Field(..., min_length=1, description="Agent definitions")
    native_workers: NativeWorkersConfig = Field(default_factory=NativeWorkersConfig)
    a2a: A2AConfig = Field(default_factory=A2AConfig)
    graph: GraphConfig = Field(default_factory=GraphConfig)
    serving: ServingConfig = Field(default_factory=ServingConfig)

    @model_validator(mode="after")
    def validate_references(self) -> "Config":
        """Validate cross-references between config sections."""
        errors: list[str] = []

        # Validate tool -> server references
        for tool_id, tool in self.tools.items():
            if tool.server not in self.mcp_servers:
                errors.append(f"Tool '{tool_id}' references unknown server '{tool.server}'")

        # Validate skill -> tool references
        for skill_name, skill in self.skills.items():
            for tool_id in skill.tools:
                if tool_id not in self.tools:
                    errors.append(f"Skill '{skill_name}' references unknown tool '{tool_id}'")

        # Validate skillset -> skill references
        for skillset_name, skillset in self.skillsets.items():
            for skill_name in skillset.skills:
                if skill_name not in self.skills:
                    errors.append(f"Skillset '{skillset_name}' references unknown skill '{skill_name}'")

        # Validate agent -> skillset references
        for agent_name, agent in self.agents.items():
            if agent.skillset and agent.skillset not in self.skillsets:
                errors.append(f"Agent '{agent_name}' references unknown skillset '{agent.skillset}'")
            if agent.llm not in self.llms:
                errors.append(f"Agent '{agent_name}' references unknown LLM '{agent.llm}'")

        if errors:
            raise ValueError("Configuration validation errors:\n" + "\n".join(f"  - {e}" for e in errors))

        return self

    def get_supervisor(self) -> tuple[str, AgentConfig] | None:
        """Get the supervisor agent configuration."""
        for name, agent in self.agents.items():
            if agent.kind == AgentKind.SUPERVISOR:
                return name, agent
        return None

    def get_workers(self) -> dict[str, AgentConfig]:
        """Get all native worker agent configurations."""
        ignored = set(self.native_workers.ignore_workers)
        return {
            name: agent
            for name, agent in self.agents.items()
            if agent.kind == AgentKind.NATIVE_WORKER and name not in ignored
        }
