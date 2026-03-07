"""Unit tests for config module."""

import pytest

from maos.config.loader import ConfigLoader
from maos.config.models import (
    AgentConfig,
    AgentKind,
    Config,
    GraphConfig,
    LLMConfig,
    LLMProvider,
    SkillConfig,
)


@pytest.mark.unit
class TestLLMConfig:
    """Tests for LLMConfig model."""

    def test_openai_config(self):
        """Test OpenAI LLM configuration."""
        config = LLMConfig(provider=LLMProvider.OPENAI, model="gpt-4o-mini")
        assert config.provider == LLMProvider.OPENAI
        assert config.model == "gpt-4o-mini"
        assert config.temperature == 0.7  # default

    def test_anthropic_config(self):
        """Test Anthropic LLM configuration."""
        config = LLMConfig(
            provider=LLMProvider.ANTHROPIC, model="claude-3-5-sonnet-20241022", temperature=0.5
        )
        assert config.provider == LLMProvider.ANTHROPIC
        assert config.temperature == 0.5

    def test_temperature_validation(self):
        """Test temperature bounds validation."""
        # Valid temperatures
        LLMConfig(provider=LLMProvider.OPENAI, model="test", temperature=0)
        LLMConfig(provider=LLMProvider.OPENAI, model="test", temperature=2)

        # Invalid temperatures
        with pytest.raises(ValueError):
            LLMConfig(provider=LLMProvider.OPENAI, model="test", temperature=-0.1)

        with pytest.raises(ValueError):
            LLMConfig(provider=LLMProvider.OPENAI, model="test", temperature=2.1)


@pytest.mark.unit
class TestAgentConfig:
    """Tests for AgentConfig model."""

    def test_supervisor_config(self):
        """Test supervisor agent configuration."""
        config = AgentConfig(
            kind=AgentKind.SUPERVISOR, llm="default", system_prompt="You are a supervisor."
        )
        assert config.kind == AgentKind.SUPERVISOR
        assert config.timeout_seconds == 60  # default

    def test_worker_config(self):
        """Test worker agent configuration."""
        config = AgentConfig(
            kind=AgentKind.NATIVE_WORKER,
            llm="fast",
            system_prompt="You are a worker.",
            description="A helpful worker",
            tools=["tool1", "tool2"],
        )
        assert config.kind == AgentKind.NATIVE_WORKER
        assert len(config.tools) == 2


@pytest.mark.unit
class TestGraphConfig:
    """Tests for GraphConfig model."""

    def test_default_config(self):
        """Test default graph configuration."""
        config = GraphConfig()
        assert config.max_iterations == 12  # Default is 12
        assert config.timeouts.tool_call_seconds == 30

    def test_custom_iterations(self):
        """Test custom max iterations."""
        config = GraphConfig(max_iterations=20)
        assert config.max_iterations == 20


@pytest.mark.unit
class TestConfig:
    """Tests for root Config model."""

    def test_minimal_config(self, minimal_config):
        """Test minimal valid configuration."""
        assert "default" in minimal_config.llms
        assert "supervisor" in minimal_config.agents

    def test_full_config(self, full_config):
        """Test full configuration with all features."""
        assert len(full_config.llms) == 2
        assert len(full_config.agents) == 3
        assert len(full_config.skills) == 1
        assert full_config.graph.max_iterations == 5


@pytest.mark.unit
class TestConfigLoader:
    """Tests for ConfigLoader."""

    def test_load_from_string(self, config_yaml_content):
        """Test loading config from YAML string."""
        loader = ConfigLoader()
        config = loader.load_from_string(config_yaml_content)

        assert "default" in config.llms
        assert config.llms["default"].provider == LLMProvider.OPENAI

    def test_load_from_file(self, tmp_config_file):
        """Test loading config from file."""
        loader = ConfigLoader()
        config = loader.load(tmp_config_file)

        assert "supervisor" in config.agents
        assert config.agents["supervisor"].kind == AgentKind.SUPERVISOR

    def test_invalid_yaml(self):
        """Test handling of invalid YAML."""
        loader = ConfigLoader()
        with pytest.raises(Exception):
            loader.load_from_string("invalid: yaml: content: [")

    def test_missing_required_fields(self):
        """Test handling of missing required fields."""
        loader = ConfigLoader()
        yaml_content = """
llms:
  default:
    provider: openai
    model: test
# Missing agents
"""
        with pytest.raises(Exception):
            loader.load_from_string(yaml_content)


@pytest.mark.unit
class TestConfigValidation:
    """Tests for configuration validation."""

    def test_validate_references(self, full_config):
        """Test that cross-references are validated."""
        # This should not raise
        full_config.validate_references()

    def test_invalid_tool_reference(self):
        """Test detection of invalid tool reference in skill."""
        config = Config(
            llms={"default": LLMConfig(provider=LLMProvider.OPENAI, model="test")},
            agents={
                "supervisor": AgentConfig(
                    kind=AgentKind.SUPERVISOR, llm="default", system_prompt="test"
                )
            },
            skills={
                "test_skill": SkillConfig(
                    tools=["nonexistent_tool"],  # Invalid reference
                    description="Test skill",
                )
            },
        )

        errors = config.validate_references()
        assert len(errors) > 0
        assert any("nonexistent_tool" in error for error in errors)
