"""
MAOS Configuration Loader.

Handles loading, parsing, and validating configuration from YAML/JSON files.
"""

import json
import os
from pathlib import Path
from typing import Any

import structlog
import yaml
from pydantic import ValidationError as PydanticValidationError

from maos.config.models import Config
from maos.errors import ConfigError, ValidationError

log = structlog.get_logger()


class ConfigLoader:
    """Load and validate configuration files."""

    def __init__(self, env_prefix: str = "MAOS_"):
        """Initialize the config loader.

        Args:
            env_prefix: Prefix for environment variable overrides
        """
        self._env_prefix = env_prefix

    def load(self, config_path: str | Path) -> Config:
        """Load configuration from file.

        Args:
            config_path: Path to YAML or JSON config file

        Returns:
            Validated Config object

        Raises:
            ConfigError: If file not found or invalid
            ValidationError: If schema validation fails
        """
        path = Path(config_path)

        if not path.exists():
            raise ConfigError(f"Configuration file not found: {path}")

        try:
            content = path.read_text()
        except OSError as e:
            raise ConfigError(f"Failed to read configuration file: {e}")

        # Determine format from extension
        suffix = path.suffix.lower()
        if suffix in (".yaml", ".yml"):
            fmt = "yaml"
        elif suffix == ".json":
            fmt = "json"
        else:
            # Try to detect from content
            fmt = "yaml" if content.strip().startswith(("---", "llms:")) else "json"

        log.info("loading_config", path=str(path), format=fmt)
        return self.load_from_string(content, fmt)

    def load_from_string(self, content: str, format: str = "yaml") -> Config:
        """Load configuration from string content.

        Args:
            content: Configuration content as string
            format: Format of content ("yaml" or "json")

        Returns:
            Validated Config object
        """
        try:
            config_dict = yaml.safe_load(content) if format == "yaml" else json.loads(content)
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML syntax: {e}")
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON syntax: {e}")

        if config_dict is None:
            raise ConfigError("Configuration file is empty")

        # Apply environment variable overrides
        config_dict = self._apply_env_overrides(config_dict)

        return self._validate(config_dict)

    def _apply_env_overrides(self, config_dict: dict[str, Any]) -> dict[str, Any]:
        """Apply environment variable overrides to config.

        Environment variables like MAOS_SERVING_API_PORT=8080 will override
        config.serving.api.port.
        """
        for key, value in os.environ.items():
            if not key.startswith(self._env_prefix):
                continue

            # Convert MAOS_SERVING_API_PORT to ["serving", "api", "port"]
            parts = key[len(self._env_prefix):].lower().split("_")

            # Navigate to the right place and set value
            current = config_dict
            for _i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {}
                current = current[part]
                if not isinstance(current, dict):
                    break
            else:
                # Try to convert to appropriate type
                final_key = parts[-1]
                if value.lower() in ("true", "false"):
                    current[final_key] = value.lower() == "true"
                elif value.isdigit():
                    current[final_key] = int(value)
                else:
                    try:
                        current[final_key] = float(value)
                    except ValueError:
                        current[final_key] = value

        return config_dict

    def _validate(self, config_dict: dict[str, Any]) -> Config:
        """Validate config dict against Pydantic models.

        Args:
            config_dict: Configuration as dictionary

        Returns:
            Validated Config object

        Raises:
            ValidationError: If validation fails
        """
        try:
            config = Config.model_validate(config_dict)
            log.info(
                "config_loaded",
                llm_count=len(config.llms),
                agent_count=len(config.agents),
                tool_count=len(config.tools),
            )
            return config
        except PydanticValidationError as e:
            errors = []
            for error in e.errors():
                loc = ".".join(str(x) for x in error["loc"])
                msg = error["msg"]
                errors.append(f"{loc}: {msg}")

            raise ValidationError(
                "Configuration validation failed",
                details={"errors": errors}
            )

    def validate(self, config_dict: dict[str, Any]) -> list[str]:
        """Validate config dict and return list of errors.

        Args:
            config_dict: Configuration as dictionary

        Returns:
            List of validation error messages (empty if valid)
        """
        try:
            self._validate(config_dict)
            return []
        except ValidationError as e:
            return e.details.get("errors", [str(e)])
