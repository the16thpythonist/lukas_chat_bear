"""
Configuration loader.

Loads configuration from YAML file and environment variables.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

from src.utils.logger import logger


class ConfigLoader:
    """
    Configuration loader that merges YAML config with environment variables.

    Environment variables can be referenced in YAML using ${VAR_NAME} syntax.
    Supports default values with ${VAR_NAME:-default_value} syntax.
    """

    def __init__(self, config_file: str = "config/config.yml"):
        """
        Initialize config loader.

        Args:
            config_file: Path to YAML configuration file
        """
        self.config_file = config_file
        self.config: Dict[str, Any] = {}
        self._load_dotenv()
        self._load_yaml()
        self._resolve_env_vars()

    def _load_dotenv(self) -> None:
        """Load environment variables from .env file."""
        env_file = Path(".env")
        if env_file.exists():
            load_dotenv(env_file)
            logger.info("Loaded environment variables from .env file")

    def _load_yaml(self) -> None:
        """Load configuration from YAML file."""
        config_path = Path(self.config_file)

        if not config_path.exists():
            logger.warning(f"Config file {self.config_file} not found, using defaults")
            # Try example config
            example_path = Path("config/config.example.yml")
            if example_path.exists():
                logger.info("Using config.example.yml")
                config_path = example_path
            else:
                self.config = {}
                return

        try:
            with open(config_path, "r") as f:
                self.config = yaml.safe_load(f) or {}
            logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            self.config = {}

    def _resolve_env_vars(self) -> None:
        """
        Resolve environment variable references in config.

        Supports:
        - ${VAR_NAME} - Replace with env var value
        - ${VAR_NAME:-default} - Use default if env var not set
        """
        self.config = self._resolve_dict(self.config)

    def _resolve_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively resolve env vars in dictionary."""
        result = {}
        for key, value in d.items():
            if isinstance(value, dict):
                result[key] = self._resolve_dict(value)
            elif isinstance(value, str):
                result[key] = self._resolve_string(value)
            elif isinstance(value, list):
                result[key] = [
                    self._resolve_string(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    def _resolve_string(self, value: str) -> str:
        """
        Resolve environment variable references in a string.

        Args:
            value: String potentially containing ${VAR_NAME} references

        Returns:
            String with env vars resolved
        """
        # Pattern: ${VAR_NAME} or ${VAR_NAME:-default}
        pattern = r"\$\{([^}:]+)(?::-([^}]+))?\}"

        def replacer(match):
            var_name = match.group(1)
            default_value = match.group(2)
            env_value = os.getenv(var_name)

            if env_value is not None:
                return env_value
            elif default_value is not None:
                return default_value
            else:
                logger.warning(f"Environment variable {var_name} not set and no default provided")
                return match.group(0)  # Return original if not found

        return re.sub(pattern, replacer, value)

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated key path.

        Args:
            key_path: Dot-separated path (e.g., "bot.llm.provider")
            default: Default value if key not found

        Returns:
            Configuration value or default

        Example:
            config.get("bot.llm.provider")  # Returns nested value
            config.get("bot.llm.model", "gpt-3.5-turbo")  # With default
        """
        keys = key_path.split(".")
        value = self.config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration as dictionary.

        Returns:
            Complete configuration dictionary
        """
        return self.config


# Global config instance
config = ConfigLoader()
