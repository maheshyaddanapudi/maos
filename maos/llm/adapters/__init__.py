"""LLM provider adapters.

This module provides two types of adapters:

1. LangChain Adapters (Recommended):
   - LangChainAdapter: Wraps LangChain chat models
   - create_langchain_model: Creates raw LangChain models for LangGraph

2. Raw SDK Adapters (Legacy/Fallback):
   - OpenAIAdapter, AnthropicAdapter, etc.: Direct SDK wrappers

The LangChain approach is preferred for LangGraph integration.
"""

# LangChain-based adapter (recommended)
from maos.llm.adapters.langchain_adapter import (
    LangChainAdapter,
    create_langchain_model,
    create_adapter_from_config,
)

# Raw SDK adapters (fallback)
from maos.llm.adapters.openai import OpenAIAdapter
from maos.llm.adapters.anthropic import AnthropicAdapter
from maos.llm.adapters.google import GoogleAdapter
from maos.llm.adapters.ollama import OllamaAdapter

__all__ = [
    # LangChain (recommended)
    "LangChainAdapter",
    "create_langchain_model",
    "create_adapter_from_config",
    # Raw SDK (fallback)
    "OpenAIAdapter",
    "AnthropicAdapter",
    "GoogleAdapter",
    "OllamaAdapter",
]
