"""
MAOS Test Configuration and Fixtures.
"""

import pytest

from maos.agents.factory import AgentFactory
from maos.agents.registry import AgentRegistry
from maos.config.loader import ConfigLoader
from maos.config.models import Config
from maos.llm.registry import LLMRegistry
from maos.mcp.registry import MCPRegistry
from maos.skills.registry import SkillRegistry, SkillsetRegistry
from maos.tools.registry import ToolRegistry

# Sample configuration YAML
SAMPLE_CONFIG_YAML = """
llms:
  default:
    provider: openai
    model: gpt-4o-mini
    temperature: 0.7

agents:
  supervisor:
    kind: supervisor
    llm: default
    system_prompt: "You are a test supervisor."
    description: "Test supervisor"

  worker:
    kind: native_worker
    llm: default
    system_prompt: "You are a test worker."
    description: "Test worker"
"""


MINIMAL_CONFIG_YAML = """
llms:
  default:
    provider: openai
    model: gpt-4o-mini

agents:
  supervisor:
    kind: supervisor
    system_prompt: "You are a supervisor."
"""


@pytest.fixture
def sample_config_yaml() -> str:
    """Sample configuration YAML."""
    return SAMPLE_CONFIG_YAML


@pytest.fixture
def minimal_config_yaml() -> str:
    """Minimal valid configuration YAML."""
    return MINIMAL_CONFIG_YAML


@pytest.fixture
def sample_config() -> Config:
    """Parsed sample configuration."""
    loader = ConfigLoader()
    return loader.load_from_string(SAMPLE_CONFIG_YAML)


@pytest.fixture
def minimal_config() -> Config:
    """Parsed minimal configuration."""
    loader = ConfigLoader()
    return loader.load_from_string(MINIMAL_CONFIG_YAML)


@pytest.fixture
def mock_llm_adapter():
    """Mock LLM adapter for testing."""
    from tests.mocks.llm import MockLLMAdapter
    return MockLLMAdapter(responses=["Test response"])


@pytest.fixture
def mock_llm_registry(mock_llm_adapter):
    """Mock LLM registry with mock adapter."""
    registry = LLMRegistry()
    registry.register_adapter("default", mock_llm_adapter)
    return registry


@pytest.fixture
def empty_mcp_registry():
    """Empty MCP registry."""
    return MCPRegistry()


@pytest.fixture
def empty_tool_registry(empty_mcp_registry):
    """Empty tool registry."""
    return ToolRegistry(empty_mcp_registry)


@pytest.fixture
def empty_skill_registry(empty_tool_registry):
    """Empty skill registry."""
    return SkillRegistry(empty_tool_registry)


@pytest.fixture
def empty_skillset_registry(empty_skill_registry, empty_tool_registry):
    """Empty skillset registry."""
    return SkillsetRegistry(empty_skill_registry, empty_tool_registry)


@pytest.fixture
async def sample_agent_registry(
    sample_config,
    mock_llm_registry,
    empty_skillset_registry,
    empty_skill_registry,
    empty_tool_registry,
):
    """Sample agent registry with agents."""
    factory = AgentFactory(
        llm_registry=mock_llm_registry,
        skillset_registry=empty_skillset_registry,
        skill_registry=empty_skill_registry,
        tool_registry=empty_tool_registry,
    )

    agents = await factory.create_all(sample_config.agents)
    registry = AgentRegistry()
    registry.register_all(agents)
    return registry
