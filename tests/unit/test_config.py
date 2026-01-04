"""
Unit tests for configuration module.
"""

import pytest
from pydantic import ValidationError

from maos.config.loader import ConfigLoader
from maos.config.models import (
    AgentConfig,
    AgentKind,
    Config,
    GraphConfig,
    LLMConfig,
    LLMProvider,
    MCPServerConfig,
    MCPTransport,
    SkillConfig,
    SkillsetConfig,
    ToolConfig,
)
from maos.errors import ConfigError
from maos.errors import ValidationError as MAOSValidationError
from tests.fixtures.configs import (
    INVALID_BAD_REFERENCE,
    INVALID_MISSING_LLMS,
    INVALID_WRONG_TYPE,
    VALID_FULL_CONFIG,
    VALID_MINIMAL_CONFIG,
)


class TestLLMConfig:
    """Tests for LLMConfig model."""

    def test_valid_openai_config(self):
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4o-mini",
        )
        assert config.provider == LLMProvider.OPENAI
        assert config.model == "gpt-4o-mini"
        assert config.temperature == 0.7  # default

    def test_valid_anthropic_config(self):
        config = LLMConfig(
            provider=LLMProvider.ANTHROPIC,
            model="claude-3-sonnet-20240229",
            temperature=0.5,
        )
        assert config.provider == LLMProvider.ANTHROPIC

    def test_valid_google_config(self):
        config = LLMConfig(
            provider=LLMProvider.GOOGLE,
            model="gemini-pro",
        )
        assert config.provider == LLMProvider.GOOGLE

    def test_valid_ollama_config(self):
        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="llama3:8b",
        )
        # Ollama doesn't need API key
        assert config.provider == LLMProvider.OLLAMA

    def test_invalid_temperature(self):
        with pytest.raises(ValidationError):
            LLMConfig(
                provider=LLMProvider.OPENAI,
                model="gpt-4",
                temperature=3.0,  # > 2
            )

    def test_custom_api_key_env(self):
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4",
            api_key_env="MY_CUSTOM_KEY",
        )
        assert config.api_key_env == "MY_CUSTOM_KEY"


class TestAgentConfig:
    """Tests for AgentConfig model."""

    def test_supervisor_config(self):
        config = AgentConfig(
            kind=AgentKind.SUPERVISOR,
            system_prompt="You are a supervisor.",
        )
        assert config.kind == AgentKind.SUPERVISOR
        assert config.llm == "default"  # default

    def test_native_worker_config(self):
        config = AgentConfig(
            kind=AgentKind.NATIVE_WORKER,
            llm="claude",
            skillset="researcher",
            system_prompt="Research agent",
        )
        assert config.kind == AgentKind.NATIVE_WORKER
        assert config.skillset == "researcher"


class TestMCPConfig:
    """Tests for MCP-related configs."""

    def test_stdio_server_config(self):
        config = MCPServerConfig(
            transport=MCPTransport.STDIO,
            command=["python", "-m", "server"],
        )
        assert config.transport == MCPTransport.STDIO
        assert config.command == ["python", "-m", "server"]

    def test_http_server_config(self):
        config = MCPServerConfig(
            transport=MCPTransport.HTTP,
            url="http://localhost:8080/mcp",
        )
        assert config.transport == MCPTransport.HTTP
        assert config.url == "http://localhost:8080/mcp"

    def test_tool_config(self):
        config = ToolConfig(
            server="tools",
            tool_name="search.web",
        )
        assert config.server == "tools"
        assert config.tool_name == "search.web"


class TestSkillConfig:
    """Tests for Skill and Skillset configs."""

    def test_skill_config(self):
        config = SkillConfig(
            tools=["search_web", "summarize"],
            description="Web research skill",
        )
        assert len(config.tools) == 2

    def test_skillset_config(self):
        config = SkillsetConfig(
            skills=["research", "writing"],
        )
        assert len(config.skills) == 2


class TestGraphConfig:
    """Tests for GraphConfig."""

    def test_defaults(self):
        config = GraphConfig()
        # Verify it has default values
        assert config.max_iterations > 0

    def test_custom_values(self):
        config = GraphConfig(
            max_iterations=20,
        )
        assert config.max_iterations == 20


class TestConfigValidation:
    """Tests for cross-reference validation."""

    def test_valid_llm_reference(self):
        """Agent referencing existing LLM should pass."""
        config = Config(
            llms={"default": LLMConfig(provider=LLMProvider.OPENAI, model="gpt-4")},
            agents={
                "supervisor": AgentConfig(
                    kind=AgentKind.SUPERVISOR,
                    llm="default",
                    system_prompt="Test",
                )
            },
        )
        assert config.agents["supervisor"].llm == "default"

    def test_invalid_llm_reference(self):
        """Agent referencing non-existent LLM should fail."""
        with pytest.raises(ValidationError) as exc_info:
            Config(
                llms={"default": LLMConfig(provider=LLMProvider.OPENAI, model="gpt-4")},
                agents={
                    "supervisor": AgentConfig(
                        kind=AgentKind.SUPERVISOR,
                        llm="nonexistent",
                        system_prompt="Test",
                    )
                },
            )
        assert "nonexistent" in str(exc_info.value)

    def test_valid_mcp_server_reference(self):
        """Tool referencing existing MCP server should pass."""
        config = Config(
            llms={"default": LLMConfig(provider=LLMProvider.OPENAI, model="gpt-4")},
            mcp_servers={
                "tools": MCPServerConfig(transport=MCPTransport.STDIO, command=["python"])
            },
            tools={
                "search": ToolConfig(server="tools", tool_name="search")
            },
            agents={
                "supervisor": AgentConfig(
                    kind=AgentKind.SUPERVISOR,
                    system_prompt="Test",
                )
            },
        )
        assert config.tools["search"].server == "tools"

    def test_invalid_mcp_server_reference(self):
        """Tool referencing non-existent MCP server should fail."""
        with pytest.raises(ValidationError) as exc_info:
            Config(
                llms={"default": LLMConfig(provider=LLMProvider.OPENAI, model="gpt-4")},
                mcp_servers={},
                tools={
                    "search": ToolConfig(server="nonexistent", tool_name="search")
                },
                agents={
                    "supervisor": AgentConfig(
                        kind=AgentKind.SUPERVISOR,
                        system_prompt="Test",
                    )
                },
            )
        assert "nonexistent" in str(exc_info.value)


class TestConfigLoader:
    """Tests for ConfigLoader."""

    def test_load_valid_minimal(self):
        loader = ConfigLoader()
        config = loader.load_from_string(VALID_MINIMAL_CONFIG)
        assert "default" in config.llms
        assert "supervisor" in config.agents

    def test_load_valid_full(self):
        loader = ConfigLoader()
        config = loader.load_from_string(VALID_FULL_CONFIG)
        assert "default" in config.llms
        assert "claude" in config.llms
        assert "tools" in config.mcp_servers
        assert "search_web" in config.tools
        assert "web_research" in config.skills
        assert "researcher" in config.skillsets
        assert "supervisor" in config.agents
        assert "research_agent" in config.agents

    def test_load_invalid_yaml(self):
        loader = ConfigLoader()
        with pytest.raises(ConfigError):
            loader.load_from_string("invalid: yaml: content: [")

    def test_load_missing_llms(self):
        loader = ConfigLoader()
        # Should raise either pydantic ValidationError or MAOS ValidationError
        with pytest.raises((ValidationError, MAOSValidationError)):
            loader.load_from_string(INVALID_MISSING_LLMS)

    def test_load_bad_reference(self):
        loader = ConfigLoader()
        with pytest.raises((ValidationError, MAOSValidationError)):
            loader.load_from_string(INVALID_BAD_REFERENCE)

    def test_load_wrong_type(self):
        loader = ConfigLoader()
        with pytest.raises((ValidationError, MAOSValidationError)):
            loader.load_from_string(INVALID_WRONG_TYPE)
