"""LLM provider adapters using LangChain.

This module uses official LangChain packages for LLM integration:
- langchain-openai for OpenAI models
- langchain-anthropic for Anthropic models
- langchain-google-genai for Google models
- langchain-community for Ollama and other providers

Benefits:
- Unified interface across all providers
- Native integration with LangGraph
- Battle-tested implementations
- Automatic tool binding support
"""

from maos.llm.adapters.langchain_adapter import (
    LangChainAdapter,
    create_adapter_from_config,
    create_langchain_model,
)

__all__ = [
    "LangChainAdapter",
    "create_langchain_model",
    "create_adapter_from_config",
]
