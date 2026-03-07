"""Registry for LLM adapters."""

from maos.config.models import LLMConfig
from maos.llm.base import LLMAdapter
from maos.llm.factory import LLMFactory


class LLMRegistry:
    """Registry for LLM adapters."""

    def __init__(self, factory: LLMFactory | None = None):
        """
        Initialize the LLM registry.

        Args:
            factory: LLM factory to use. Creates default if not provided.
        """
        self._adapters: dict[str, LLMAdapter] = {}
        self._factory = factory or LLMFactory()

    def build(self, llm_configs: dict[str, LLMConfig]) -> None:
        """
        Build the registry from configuration.

        Args:
            llm_configs: Dictionary of LLM configurations keyed by name.
        """
        for name, config in llm_configs.items():
            self.register(name, config)

    def register(self, name: str, config: LLMConfig) -> None:
        """
        Register an LLM adapter from configuration.

        Args:
            name: Name to register the adapter under.
            config: LLM configuration.
        """
        adapter = self._factory.create(config)
        self._adapters[name] = adapter

    def register_adapter(self, name: str, adapter: LLMAdapter) -> None:
        """
        Register a pre-created LLM adapter.

        Args:
            name: Name to register the adapter under.
            adapter: Pre-created LLM adapter.
        """
        self._adapters[name] = adapter

    def get(self, name: str) -> LLMAdapter | None:
        """
        Get an LLM adapter by name.

        Args:
            name: The adapter name.

        Returns:
            The adapter if found, None otherwise.
        """
        return self._adapters.get(name)

    def get_or_raise(self, name: str) -> LLMAdapter:
        """
        Get an LLM adapter by name, raising if not found.

        Args:
            name: The adapter name.

        Returns:
            The adapter.

        Raises:
            KeyError: If adapter not found.
        """
        adapter = self._adapters.get(name)
        if adapter is None:
            raise KeyError(f"LLM adapter not found: {name}")
        return adapter

    def get_default(self) -> LLMAdapter:
        """
        Get the default LLM adapter.

        Returns:
            The adapter registered as "default".

        Raises:
            KeyError: If no default adapter is registered.
        """
        return self.get_or_raise("default")

    def get_or_default(self, name: str | None = None) -> LLMAdapter:
        """
        Get an adapter by name, falling back to default.

        Args:
            name: The adapter name (optional).

        Returns:
            The named adapter if found, otherwise the default.

        Raises:
            KeyError: If neither named nor default adapter is found.
        """
        if name and name in self._adapters:
            return self._adapters[name]
        if "default" in self._adapters:
            return self._adapters["default"]
        raise KeyError(f"LLM adapter '{name}' not found and no default configured")

    def list(self) -> list[str]:
        """
        List all registered adapter names.

        Returns:
            List of adapter names.
        """
        return list(self._adapters.keys())

    def __contains__(self, name: str) -> bool:
        """Check if an adapter is registered."""
        return name in self._adapters

    def __len__(self) -> int:
        """Get the number of registered adapters."""
        return len(self._adapters)
