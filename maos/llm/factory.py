"""Factory for creating LLM adapters using LangChain.

This module creates LLM adapters using official LangChain packages:
- langchain-openai for OpenAI
- langchain-anthropic for Anthropic
- langchain-google-genai for Google
- langchain-community for Ollama

The LangChain approach provides:
- Unified interface across providers
- Native integration with LangGraph
- Battle-tested implementations
- Automatic tool binding support
"""

from langchain_core.language_models import BaseChatModel

from maos.config.models import LLMConfig, LLMProvider
from maos.llm.base import LLMAdapter


class LLMFactory:
    """Factory for creating LLM adapters from configuration.

    Creates LangChain-based adapters which integrate natively with LangGraph.
    """

    def create(self, config: LLMConfig) -> LLMAdapter:
        """
        Create an LLM adapter from configuration.

        Args:
            config: LLM configuration.

        Returns:
            Configured LLM adapter using LangChain.

        Raises:
            ValueError: If provider is not supported.
        """
        from maos.llm.adapters.langchain_adapter import create_adapter_from_config

        return create_adapter_from_config(config)

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
