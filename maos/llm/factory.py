"""Factory for creating LLM adapters.

This module provides two approaches:
1. LangChain-based adapters (recommended) - uses official langchain-* packages
2. Raw SDK adapters (fallback) - direct SDK wrappers

The LangChain approach is preferred because:
- Unified interface across providers
- Native integration with LangGraph
- Battle-tested implementations
- Automatic tool binding support
"""

from typing import Dict, Type, Union

from langchain_core.language_models import BaseChatModel

from maos.config.models import LLMConfig, LLMProvider
from maos.llm.base import LLMAdapter


class LLMFactory:
    """Factory for creating LLM adapters from configuration.

    By default, creates LangChain-based adapters which integrate
    natively with LangGraph. Can optionally create raw SDK adapters
    if needed for specific use cases.
    """

    def __init__(self, use_langchain: bool = True):
        """
        Initialize the factory.

        Args:
            use_langchain: If True (default), use LangChain adapters.
                          If False, use raw SDK adapters.
        """
        self._use_langchain = use_langchain

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
        if self._use_langchain:
            return self._create_langchain_adapter(config)
        else:
            return self._create_raw_adapter(config)

    def create_chat_model(self, config: LLMConfig) -> BaseChatModel:
        """
        Create a LangChain chat model directly (for LangGraph native use).

        This returns the raw LangChain chat model without our adapter wrapper,
        which is ideal for direct use with LangGraph's create_react_agent
        and other prebuilt components.

        Args:
            config: LLM configuration.

        Returns:
            A LangChain BaseChatModel instance.
        """
        from maos.llm.adapters.langchain_adapter import create_langchain_model
        return create_langchain_model(config)

    def _create_langchain_adapter(self, config: LLMConfig) -> LLMAdapter:
        """Create adapter using LangChain."""
        from maos.llm.adapters.langchain_adapter import create_adapter_from_config
        return create_adapter_from_config(config)

    def _create_raw_adapter(self, config: LLMConfig) -> LLMAdapter:
        """Create adapter using raw SDK (fallback)."""
        # Import here to avoid circular imports and only load if needed
        from maos.llm.adapters.openai import OpenAIAdapter
        from maos.llm.adapters.anthropic import AnthropicAdapter
        from maos.llm.adapters.google import GoogleAdapter
        from maos.llm.adapters.ollama import OllamaAdapter

        adapters: Dict[LLMProvider, Type[LLMAdapter]] = {
            LLMProvider.OPENAI: OpenAIAdapter,
            LLMProvider.ANTHROPIC: AnthropicAdapter,
            LLMProvider.GOOGLE: GoogleAdapter,
            LLMProvider.OLLAMA: OllamaAdapter,
            LLMProvider.OPENAI_COMPATIBLE: OpenAIAdapter,
            LLMProvider.AZURE_OPENAI: OpenAIAdapter,
        }

        adapter_class = adapters.get(config.provider)
        if adapter_class is None:
            raise ValueError(f"Unsupported LLM provider: {config.provider}")

        return adapter_class(config)

    @classmethod
    def supported_providers(cls) -> list[LLMProvider]:
        """Get list of supported providers."""
        return [
            LLMProvider.OPENAI,
            LLMProvider.ANTHROPIC,
            LLMProvider.GOOGLE,
            LLMProvider.OLLAMA,
            LLMProvider.OPENAI_COMPATIBLE,
            LLMProvider.AZURE_OPENAI,
        ]
