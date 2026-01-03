"""
MAOS LLM Registry.

Manages LLM adapter instances by name.
"""

import structlog

from maos.config.models import LLMConfig
from maos.errors import ConfigError
from maos.llm.base import LLMAdapter
from maos.llm.factory import LLMFactory

log = structlog.get_logger()


class LLMRegistry:
    """Registry of configured LLM adapters."""

    def __init__(self):
        self._adapters: dict[str, LLMAdapter] = {}
        self._factory = LLMFactory()

    def build(self, llm_configs: dict[str, LLMConfig]) -> None:
        """Build registry from configuration.

        Args:
            llm_configs: Dictionary of LLM configurations keyed by name
        """
        for name, config in llm_configs.items():
            try:
                adapter = self._factory.create(config)
                self._adapters[name] = adapter
                log.info(
                    "llm_registered",
                    name=name,
                    provider=config.provider,
                    model=config.model,
                )
            except Exception as e:
                log.error(
                    "llm_registration_failed",
                    name=name,
                    error=str(e),
                )
                raise ConfigError(f"Failed to create LLM adapter '{name}': {e}")

    def register(self, name: str, config: LLMConfig) -> None:
        """Register a single LLM adapter.

        Args:
            name: Name for the adapter
            config: LLM configuration
        """
        adapter = self._factory.create(config)
        self._adapters[name] = adapter
        log.info("llm_registered", name=name)

    def register_adapter(self, name: str, adapter: LLMAdapter) -> None:
        """Register a pre-created adapter.

        Args:
            name: Name for the adapter
            adapter: LLM adapter instance
        """
        self._adapters[name] = adapter
        log.info("llm_adapter_registered", name=name)

    def get(self, name: str) -> LLMAdapter | None:
        """Get LLM adapter by name.

        Args:
            name: Adapter name

        Returns:
            LLM adapter or None if not found
        """
        return self._adapters.get(name)

    def get_or_raise(self, name: str) -> LLMAdapter:
        """Get LLM adapter by name or raise error.

        Args:
            name: Adapter name

        Returns:
            LLM adapter

        Raises:
            ConfigError: If adapter not found
        """
        adapter = self.get(name)
        if adapter is None:
            raise ConfigError(f"LLM adapter not found: {name}")
        return adapter

    def get_default(self) -> LLMAdapter:
        """Get the default LLM adapter.

        Returns:
            Default LLM adapter

        Raises:
            ConfigError: If no default adapter configured
        """
        if "default" in self._adapters:
            return self._adapters["default"]

        # Return first adapter if no default
        if self._adapters:
            first_name = next(iter(self._adapters))
            log.warning(
                "no_default_llm",
                using=first_name,
            )
            return self._adapters[first_name]

        raise ConfigError("No LLM adapters configured")

    def get_or_default(self, name: str | None) -> LLMAdapter:
        """Get adapter by name or fall back to default.

        Args:
            name: Adapter name or None

        Returns:
            LLM adapter
        """
        if name and name in self._adapters:
            return self._adapters[name]
        return self.get_default()

    def list_names(self) -> list[str]:
        """List all registered adapter names.

        Returns:
            List of adapter names
        """
        return list(self._adapters.keys())

    def __len__(self) -> int:
        return len(self._adapters)

    def __contains__(self, name: str) -> bool:
        return name in self._adapters
