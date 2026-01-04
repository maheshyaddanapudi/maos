"""
MAOS Ollama LLM Adapter.

Uses LangChain's ChatOpenAI with Ollama's OpenAI-compatible endpoint.
"""

from maos.llm.adapters.openai import OpenAIAdapter


class OllamaAdapter(OpenAIAdapter):
    """Ollama adapter using OpenAI-compatible API via LangChain."""

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434/v1",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        timeout: float = 120.0,  # Ollama may need more time
    ):
        # Ollama doesn't require an API key but LangChain needs something
        super().__init__(
            model=model,
            api_key="ollama",  # Placeholder for Ollama
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
