"""
MAOS LLM Factory.

Creates LLM adapters from configuration.
"""

import os

import structlog

from maos.config.models import LLMConfig, LLMProvider
from maos.errors import ConfigError
from maos.llm.adapters.anthropic import AnthropicAdapter
from maos.llm.adapters.google import GoogleAdapter
from maos.llm.adapters.ollama import OllamaAdapter
from maos.llm.adapters.openai import OpenAIAdapter
from maos.llm.base import LLMAdapter

log = structlog.get_logger()


class LLMFactory:
    """Factory for creating LLM adapters from configuration."""

    def create(self, config: LLMConfig) -> LLMAdapter:
        """Create LLM adapter from configuration.

        Args:
            config: LLM configuration

        Returns:
            Configured LLM adapter

        Raises:
            ConfigError: If provider not supported or configuration invalid
        """
        # Resolve API key from environment
        api_key = self._resolve_api_key(config)

        log.debug(
            "creating_llm_adapter",
            provider=config.provider,
            model=config.model,
        )

        provider = config.provider

        if provider == LLMProvider.OPENAI:
            return OpenAIAdapter(
                model=config.model,
                api_key=api_key,
                base_url=config.base_url,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=float(config.timeout_seconds),
            )

        elif provider == LLMProvider.ANTHROPIC:
            return AnthropicAdapter(
                model=config.model,
                api_key=api_key,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=float(config.timeout_seconds),
            )

        elif provider == LLMProvider.GOOGLE:
            return GoogleAdapter(
                model=config.model,
                api_key=api_key,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            )

        elif provider == LLMProvider.OLLAMA:
            base_url = config.base_url or "http://localhost:11434/v1"
            return OllamaAdapter(
                model=config.model,
                base_url=base_url,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=float(config.timeout_seconds),
            )

        elif provider in (LLMProvider.OPENAI_COMPATIBLE, LLMProvider.AZURE_OPENAI):
            if not config.base_url:
                raise ConfigError(f"base_url is required for {provider}")
            return OpenAIAdapter(
                model=config.model,
                api_key=api_key,
                base_url=config.base_url,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=float(config.timeout_seconds),
            )

        else:
            raise ConfigError(f"Unsupported LLM provider: {provider}")

    # Default environment variable names for each provider
    _DEFAULT_API_KEY_ENVS: dict[LLMProvider, str] = {
        LLMProvider.OPENAI: "OPENAI_API_KEY",
        LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
        LLMProvider.GOOGLE: "GOOGLE_API_KEY",
        LLMProvider.OPENAI_COMPATIBLE: "OPENAI_API_KEY",
        LLMProvider.AZURE_OPENAI: "AZURE_OPENAI_API_KEY",
    }

    def _resolve_api_key(self, config: LLMConfig) -> str | None:
        """Resolve API key from environment variable.

        Args:
            config: LLM configuration

        Returns:
            API key or None if not required/found
        """
        if config.provider == LLMProvider.OLLAMA:
            return None

        # Check explicit api_key_env first
        if config.api_key_env:
            api_key = os.environ.get(config.api_key_env)
            if api_key:
                return api_key
            log.warning(
                "api_key_not_found",
                env_var=config.api_key_env,
                provider=config.provider,
            )

        # Fall back to default environment variable for provider
        default_env = self._DEFAULT_API_KEY_ENVS.get(config.provider)
        if default_env:
            api_key = os.environ.get(default_env)
            if api_key:
                return api_key

        return None
