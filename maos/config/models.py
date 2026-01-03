"""Pydantic models for MAOS configuration."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


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
    provider: LLMProvider
    model: str
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    api_key_env: Optional[str] = None
    base_url: Optional[str] = None
    timeout_seconds: int = Field(default=60, ge=1)


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server connection."""
    transport: Literal["stdio", "http", "sse"] = "stdio"
    command: Optional[List[str]] = None
    url: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    timeout_seconds: int = Field(default=30, ge=1)


class ToolConfig(BaseModel):
    """Configuration mapping a tool ID to an MCP server tool."""
    server: str = Field(..., description="Reference to MCP server name")
    tool_name: str = Field(..., description="Tool name as exposed by MCP server")
    description_override: Optional[str] = None
    timeout_seconds: Optional[int] = Field(default=None, ge=1)


class SkillConfig(BaseModel):
    """A skill groups related tools."""
    tools: List[str] = Field(..., min_length=1)
    description: str = ""


class SkillsetConfig(BaseModel):
    """A skillset groups related skills for an agent."""
    skills: List[str] = Field(..., min_length=1)
    description: Optional[str] = None


class AgentKind(str, Enum):
    """Types of agents."""
    SUPERVISOR = "supervisor"
    NATIVE_WORKER = "native_worker"


class RetryPolicy(BaseModel):
    """Retry configuration for agent/tool failures."""
    max_retries: int = Field(default=1, ge=0, le=5)
    retry_delay_seconds: float = Field(default=1.0, ge=0)
    exponential_backoff: bool = False


class AgentConfig(BaseModel):
    """Configuration for a native agent (supervisor or worker)."""
    kind: AgentKind
    framework: Literal["langchain", "openai", "google", "smolagents", "llamaindex", "agno", "tinyagent"] = "langchain"
    llm: str = "default"
    skillset: Optional[str] = None
    tools: Optional[List[str]] = None
    system_prompt: str
    description: Optional[str] = None
    timeout_seconds: int = Field(default=60, ge=1)
    retry_policy: Optional[RetryPolicy] = None


class NativeWorkersConfig(BaseModel):
    """Configuration options for native workers."""
    ignore_workers: List[str] = Field(default_factory=list)


class A2ADiscoveryConfig(BaseModel):
    """Configuration for discovering external A2A agents."""
    seeds: List[str] = Field(default_factory=list)
    well_known_paths: List[str] = Field(default=["/.well-known/agent.json"])
    host_index_path: str = "/a2a/index.json"
    timeout_seconds: int = Field(default=10, ge=1)
    parallel_discovery: bool = True


class ToolsAssignmentConfig(BaseModel):
    """Configuration for assigning external agents as tools."""
    strategy: Literal["skill_overlap", "explicit", "supervisor"] = "skill_overlap"
    fallback: Literal["supervisor", "skip"] = "supervisor"
    explicit: Dict[str, str] = Field(default_factory=dict)


class A2AImportPolicy(BaseModel):
    """Policy for importing discovered external agents."""
    enabled: bool = True
    mode: Literal["langgraph_nodes", "tools_only"] = "langgraph_nodes"
    tools_assignment: Optional[ToolsAssignmentConfig] = None
    max_agents: int = Field(default=25, ge=1, le=100)
    include_tags: List[str] = Field(default_factory=list)
    exclude_tags: List[str] = Field(default_factory=list)
    include_names: List[str] = Field(default_factory=list)
    exclude_names: List[str] = Field(default_factory=list)


class A2AConfig(BaseModel):
    """A2A external agent discovery and import configuration."""
    discovery: A2ADiscoveryConfig = Field(default_factory=A2ADiscoveryConfig)
    import_policy: A2AImportPolicy = Field(default_factory=A2AImportPolicy)


class TimeoutsConfig(BaseModel):
    """Timeout configuration for graph execution."""
    external_agent_call_seconds: int = Field(default=40, ge=1)
    tool_call_seconds: int = Field(default=30, ge=1)
    total_execution_seconds: int = Field(default=300, ge=1)


class GraphConfig(BaseModel):
    """LangGraph execution configuration."""
    max_iterations: int = Field(default=12, ge=1, le=100)
    timeouts: TimeoutsConfig = Field(default_factory=TimeoutsConfig)
    retry_policy: Optional[RetryPolicy] = None


class APIConfig(BaseModel):
    """API server configuration."""
    host: str = "127.0.0.1"
    port: int = Field(default=7777, ge=1, le=65535)
    cors_origins: List[str] = Field(default=["*"])
    openai_compatible: bool = True


class UIConfig(BaseModel):
    """UI configuration."""
    mode: Literal["none", "chainlit", "openwebui_compatible"] = "none"


class ServingConfig(BaseModel):
    """API and UI serving configuration."""
    api: APIConfig = Field(default_factory=APIConfig)
    ui: UIConfig = Field(default_factory=UIConfig)


class Config(BaseModel):
    """Root configuration model for MAOS."""
    llms: Dict[str, LLMConfig]
    mcp_servers: Dict[str, MCPServerConfig] = Field(default_factory=dict)
    tools: Dict[str, ToolConfig] = Field(default_factory=dict)
    skills: Dict[str, SkillConfig] = Field(default_factory=dict)
    skillsets: Dict[str, SkillsetConfig] = Field(default_factory=dict)
    agents: Dict[str, AgentConfig]
    native_workers: NativeWorkersConfig = Field(default_factory=NativeWorkersConfig)
    a2a: A2AConfig = Field(default_factory=A2AConfig)
    graph: GraphConfig = Field(default_factory=GraphConfig)
    serving: ServingConfig = Field(default_factory=ServingConfig)

    def get_supervisor(self) -> tuple[str, AgentConfig]:
        """Get the supervisor agent configuration."""
        for name, agent in self.agents.items():
            if agent.kind == AgentKind.SUPERVISOR:
                return name, agent
        raise ValueError("No supervisor agent defined in configuration")

    def get_workers(self) -> Dict[str, AgentConfig]:
        """Get all native worker agents."""
        ignore = set(self.native_workers.ignore_workers)
        return {
            name: agent
            for name, agent in self.agents.items()
            if agent.kind == AgentKind.NATIVE_WORKER and name not in ignore
        }

    def validate_references(self) -> List[str]:
        """Validate all cross-references in configuration."""
        errors = []

        # Check tool -> server references
        for tool_name, tool in self.tools.items():
            if tool.server not in self.mcp_servers:
                errors.append(f"Tool '{tool_name}' references unknown server '{tool.server}'")

        # Check skill -> tool references
        for skill_name, skill in self.skills.items():
            for tool_name in skill.tools:
                if tool_name not in self.tools:
                    errors.append(f"Skill '{skill_name}' references unknown tool '{tool_name}'")

        # Check skillset -> skill references
        for skillset_name, skillset in self.skillsets.items():
            for skill_name in skillset.skills:
                if skill_name not in self.skills:
                    errors.append(f"Skillset '{skillset_name}' references unknown skill '{skill_name}'")

        # Check agent -> LLM and skillset references
        for agent_name, agent in self.agents.items():
            if agent.llm not in self.llms:
                errors.append(f"Agent '{agent_name}' references unknown LLM '{agent.llm}'")
            if agent.skillset and agent.skillset not in self.skillsets:
                errors.append(f"Agent '{agent_name}' references unknown skillset '{agent.skillset}'")

        return errors
