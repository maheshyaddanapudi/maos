"""
Integration tests for LLM registry.
"""

from unittest.mock import patch

from maos.config.models import LLMConfig, LLMProvider
from maos.llm.registry import LLMRegistry


class TestLLMRegistryIntegration:
    """Integration tests for LLM registry building."""

    def test_build_multiple_providers(self):
        """Test building registry with multiple providers."""
        configs = {
            "ollama": LLMConfig(
                provider=LLMProvider.OLLAMA,
                model="llama3:8b",
            ),
        }

        registry = LLMRegistry()
        registry.build(configs)

        assert registry.get("ollama") is not None

    def test_build_with_custom_base_url(self):
        """Test building with custom base URL."""
        configs = {
            "custom": LLMConfig(
                provider=LLMProvider.OPENAI,
                model="local-model",
                base_url="http://localhost:8000/v1",
            ),
        }

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            registry = LLMRegistry()
            registry.build(configs)

        adapter = registry.get("custom")
        assert adapter is not None

    def test_default_adapter_fallback(self):
        """Test default adapter fallback."""
        configs = {
            "default": LLMConfig(
                provider=LLMProvider.OLLAMA,
                model="llama3",
            ),
            "other": LLMConfig(
                provider=LLMProvider.OLLAMA,
                model="mistral",
            ),
        }

        registry = LLMRegistry()
        registry.build(configs)

        # Get by name
        assert registry.get_or_default("other") is registry.get("other")

        # Fallback to default
        assert registry.get_or_default("nonexistent") is registry.get("default")
        assert registry.get_or_default(None) is registry.get("default")

    def test_list_all_adapters(self):
        """Test listing all registered adapters."""
        configs = {
            "a": LLMConfig(provider=LLMProvider.OLLAMA, model="a"),
            "b": LLMConfig(provider=LLMProvider.OLLAMA, model="b"),
            "c": LLMConfig(provider=LLMProvider.OLLAMA, model="c"),
        }

        registry = LLMRegistry()
        registry.build(configs)

        names = registry.list_names()
        assert len(names) == 3
        assert "a" in names
        assert "b" in names
        assert "c" in names
