"""Factory for creating LLM adapters."""

from typing import Dict, Type

from maos.config.models import LLMConfig, LLMProvider
from maos.llm.base import LLMAdapter
from maos.llm.adapters.openai import OpenAIAdapter
from maos.llm.adapters.anthropic import AnthropicAdapter
from maos.llm.adapters.google import GoogleAdapter
from maos.llm.adapters.ollama import OllamaAdapter


class LLMFactory:
    """Factory for creating LLM adapters from configuration."""

    # Map of providers to adapter classes
    _adapters: Dict[LLMProvider, Type[LLMAdapter]] = {
        LLMProvider.OPENAI: OpenAIAdapter,
        LLMProvider.ANTHROPIC: AnthropicAdapter,
        LLMProvider.GOOGLE: GoogleAdapter,
        LLMProvider.OLLAMA: OllamaAdapter,
        LLMProvider.OPENAI_COMPATIBLE: OpenAIAdapter,
        LLMProvider.AZURE_OPENAI: OpenAIAdapter,  # Uses OpenAI adapter with different config
    }

    def create(self, config: LLMConfig) -> LLMAdapter:
        """
        Create an LLM adapter from configuration.

        Args:
            config: LLM configuration.

        Returns:
            Configured LLM adapter.

        Raises:
            ValueError: If provider is not supported.
        """
        adapter_class = self._adapters.get(config.provider)
        if adapter_class is None:
            raise ValueError(f"Unsupported LLM provider: {config.provider}")

        return adapter_class(config)

    @classmethod
    def register_adapter(cls, provider: LLMProvider, adapter_class: Type[LLMAdapter]) -> None:
        """
        Register a custom adapter for a provider.

        Args:
            provider: The provider identifier.
            adapter_class: The adapter class to use.
        """
        cls._adapters[provider] = adapter_class

    @classmethod
    def supported_providers(cls) -> list[LLMProvider]:
        """Get list of supported providers."""
        return list(cls._adapters.keys())
