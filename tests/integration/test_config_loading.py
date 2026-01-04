"""
Integration tests for configuration loading.
"""

import json

from maos.config.loader import ConfigLoader


class TestConfigurationIntegration:
    """Integration tests for config loading."""

    def test_load_yaml_with_all_sections(self, tmp_path):
        """Test loading a complete YAML configuration."""
        config_content = """
llms:
  default:
    provider: openai
    model: gpt-4o-mini
    temperature: 0.7

mcp_servers:
  tools:
    transport: stdio
    command: ["python", "-m", "mock_server"]

tools:
  search:
    server: tools
    tool_name: web.search

skills:
  research:
    tools: [search]
    description: Research skill

skillsets:
  researcher:
    skills: [research]

agents:
  supervisor:
    kind: supervisor
    system_prompt: "Route tasks to workers."

  worker:
    kind: native_worker
    skillset: researcher
    system_prompt: "Do research."

graph:
  max_iterations: 15

serving:
  api:
    port: 8080
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        loader = ConfigLoader()
        config = loader.load(config_file)  # Use .load() instead of .load_from_file()

        assert "default" in config.llms
        assert "tools" in config.mcp_servers
        assert "search" in config.tools
        assert "research" in config.skills
        assert "researcher" in config.skillsets
        assert "supervisor" in config.agents
        assert "worker" in config.agents
        assert config.graph.max_iterations == 15
        assert config.serving.api.port == 8080

    def test_json_configuration(self, tmp_path):
        """Test loading JSON configuration."""
        config_data = {
            "llms": {
                "default": {
                    "provider": "anthropic",
                    "model": "claude-3-sonnet-20240229"
                }
            },
            "agents": {
                "supervisor": {
                    "kind": "supervisor",
                    "system_prompt": "Route tasks."
                }
            }
        }

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        loader = ConfigLoader()
        config = loader.load(config_file)  # Use .load() instead of .load_from_file()

        assert config.llms["default"].provider.value == "anthropic"

    def test_minimal_valid_config(self, tmp_path):
        """Test that minimal config is valid."""
        config_content = """
llms:
  default:
    provider: ollama
    model: llama3:8b

agents:
  supervisor:
    kind: supervisor
    system_prompt: "Route."
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        loader = ConfigLoader()
        config = loader.load(config_file)  # Use .load() instead of .load_from_file()

        assert len(config.llms) == 1
        assert len(config.agents) == 1

    def test_a2a_configuration(self, tmp_path):
        """Test A2A configuration section."""
        config_content = """
llms:
  default:
    provider: openai
    model: gpt-4o-mini

agents:
  supervisor:
    kind: supervisor
    system_prompt: "Route."

a2a:
  discovery:
    seeds:
      - "http://example.com/agents"
    timeout_seconds: 15
  import_policy:
    enabled: true
    mode: langgraph_nodes
    prefix: "ext::"
    max_agents: 20
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        loader = ConfigLoader()
        config = loader.load(config_file)  # Use .load() instead of .load_from_file()

        assert len(config.a2a.discovery.seeds) == 1
        assert config.a2a.import_policy.enabled is True
        assert config.a2a.import_policy.max_agents == 20
