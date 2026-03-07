"""Configuration loader for MAOS."""

import json
import os
from pathlib import Path
from typing import Any

import structlog
import yaml
from pydantic import ValidationError

from maos.config.models import Config

logger = structlog.get_logger()

_SECURITY_PATHS = {
    "auth",
    "security",
    "api_keys",
    "keys",
    "cors",
    "a2a",
    "mcp_servers",
    "command",
}


class ConfigError(Exception):
    """Configuration-related errors."""

    pass


class ConfigLoader:
    """Load and validate configuration files."""

    def __init__(self, env_prefix: str = "MAOS_"):
        """
        Initialize the config loader.

        Args:
            env_prefix: Prefix for environment variable overrides.
        """
        self._env_prefix = env_prefix

    def load(self, config_path: str) -> Config:
        """
        Load configuration from a file.

        Args:
            config_path: Path to YAML or JSON config file.

        Returns:
            Validated Config object.

        Raises:
            ConfigError: If file not found or invalid.
        """
        path = Path(config_path)
        if not path.exists():
            raise ConfigError(f"Configuration file not found: {config_path}")

        try:
            content = path.read_text()
        except Exception as e:
            raise ConfigError(f"Failed to read configuration file: {e}")

        # Detect format from extension
        if path.suffix in (".yaml", ".yml"):
            config_dict = self._parse_yaml(content)
        elif path.suffix == ".json":
            config_dict = self._parse_json(content)
        else:
            # Try YAML first, then JSON
            try:
                config_dict = self._parse_yaml(content)
            except Exception:
                config_dict = self._parse_json(content)

        return self._build_config(config_dict)

    def load_from_string(self, content: str, format: str = "yaml") -> Config:
        """
        Load configuration from a string.

        Args:
            content: Configuration content as string.
            format: Format of the content ("yaml" or "json").

        Returns:
            Validated Config object.
        """
        if format == "yaml":
            config_dict = self._parse_yaml(content)
        else:
            config_dict = self._parse_json(content)

        return self._build_config(config_dict)

    def load_from_dict(self, config_dict: dict[str, Any]) -> Config:
        """
        Load configuration from a dictionary.

        Args:
            config_dict: Configuration dictionary.

        Returns:
            Validated Config object.
        """
        return self._build_config(config_dict)

    def _parse_yaml(self, content: str) -> dict[str, Any]:
        """Parse YAML content."""
        try:
            return yaml.safe_load(content) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML: {e}")

    def _parse_json(self, content: str) -> dict[str, Any]:
        """Parse JSON content."""
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON: {e}")

    def _build_config(self, config_dict: dict[str, Any]) -> Config:
        """
        Build and validate configuration from dictionary.

        Args:
            config_dict: Raw configuration dictionary.

        Returns:
            Validated Config object.

        Raises:
            ConfigError: If validation fails.
        """
        # Apply environment variable overrides
        config_dict = self._apply_env_overrides(config_dict)

        try:
            config = Config.model_validate(config_dict)
        except ValidationError as e:
            errors = []
            for err in e.errors():
                loc = ".".join(str(x) for x in err["loc"])
                errors.append(f"  {loc}: {err['msg']}")
            raise ConfigError("Configuration validation failed:\n" + "\n".join(errors))

        # Validate cross-references
        ref_errors = config.validate_references()
        if ref_errors:
            raise ConfigError(
                "Configuration reference errors:\n" + "\n".join(f"  - {e}" for e in ref_errors)
            )

        return config

    def _apply_env_overrides(self, config_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Apply environment variable overrides to configuration.

        Environment variables are named like:
        - MAOS_SERVING_API_HOST -> serving.api.host
        - MAOS_GRAPH_MAX_ITERATIONS -> graph.max_iterations

        Args:
            config_dict: Original configuration dictionary.

        Returns:
            Configuration with env overrides applied.
        """
        result = config_dict.copy()

        for key, value in os.environ.items():
            if not key.startswith(self._env_prefix):
                continue

            # Convert env var name to config path
            # MAOS_SERVING_API_HOST -> serving.api.host
            path_parts = key[len(self._env_prefix) :].lower().split("_")

            # Navigate/create nested dicts
            current = result
            for part in path_parts[:-1]:
                if part not in current:
                    current[part] = {}
                elif not isinstance(current[part], dict):
                    break
                current = current[part]
            else:
                # Block security-related overrides via env vars
                # Check individual parts and consecutive pairs (for multi-word keys
                # like "mcp_servers" which split into ["mcp", "servers"])
                pairs = [f"{path_parts[i]}_{path_parts[i + 1]}" for i in range(len(path_parts) - 1)]
                if any(part in _SECURITY_PATHS for part in (*path_parts, *pairs)):
                    logger.warning(
                        "security_config_env_override_blocked",
                        env_var=key,
                        message="Security-related config override via env var blocked",
                    )
                    continue

                # Try to parse as JSON for complex values, otherwise use string
                final_key = path_parts[-1]
                try:
                    current[final_key] = json.loads(value)
                except json.JSONDecodeError:
                    current[final_key] = value

        return result

    def validate(self, config_dict: dict[str, Any]) -> list[str]:
        """
        Validate configuration dictionary without creating Config object.

        Args:
            config_dict: Configuration dictionary to validate.

        Returns:
            List of validation error messages (empty if valid).
        """
        errors = []
        try:
            config = Config.model_validate(config_dict)
            errors.extend(config.validate_references())
        except ValidationError as e:
            for err in e.errors():
                loc = ".".join(str(x) for x in err["loc"])
                errors.append(f"{loc}: {err['msg']}")
        return errors


def load_config(config_path: str | None = None) -> Config:
    """
    Convenience function to load configuration.

    Args:
        config_path: Path to config file. If None, looks for:
            1. MAOS_CONFIG environment variable
            2. config.yaml in current directory
            3. config.json in current directory

    Returns:
        Validated Config object.
    """
    loader = ConfigLoader()

    if config_path:
        return loader.load(config_path)

    # Check environment variable
    env_path = os.environ.get("MAOS_CONFIG")
    if env_path:
        return loader.load(env_path)

    # Check current directory
    for filename in ["config.yaml", "config.yml", "config.json"]:
        if Path(filename).exists():
            return loader.load(filename)

    raise ConfigError(
        "No configuration file found. Please specify a config path or "
        "create config.yaml in the current directory."
    )
