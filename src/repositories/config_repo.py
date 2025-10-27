"""
Configuration repository.

Data access layer for Configuration entity.
"""

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.models.config import Configuration
from src.utils.logger import logger


class ConfigurationRepository:
    """Repository for configuration-related database operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_config(self, key: str) -> Optional[Configuration]:
        """
        Get configuration by key.

        Args:
            key: Configuration key

        Returns:
            Configuration object or None
        """
        return self.db.query(Configuration).filter(Configuration.key == key).first()

    def get_value(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with type conversion.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value (typed) or default
        """
        config = self.get_config(key)
        if not config:
            return default

        # Convert based on value_type
        try:
            if config.value_type == "integer":
                return int(config.value)
            elif config.value_type == "float":
                return float(config.value)
            elif config.value_type == "boolean":
                return config.value.lower() in ("true", "1", "yes")
            elif config.value_type == "json":
                return json.loads(config.value)
            else:  # string
                return config.value
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing config value for key {key}: {e}")
            return default

    def set_value(
        self,
        key: str,
        value: Any,
        description: str = "",
        updated_by_user_id: Optional[str] = None,
    ) -> Configuration:
        """
        Set configuration value (create or update).

        Args:
            key: Configuration key
            value: Configuration value
            description: Human-readable description
            updated_by_user_id: ID of user making the change

        Returns:
            Configuration object
        """
        config = self.get_config(key)

        # Determine value_type
        if isinstance(value, bool):
            value_type = "boolean"
            value_str = str(value)
        elif isinstance(value, int):
            value_type = "integer"
            value_str = str(value)
        elif isinstance(value, float):
            value_type = "float"
            value_str = str(value)
        elif isinstance(value, (dict, list)):
            value_type = "json"
            value_str = json.dumps(value)
        else:
            value_type = "string"
            value_str = str(value)

        if config:
            # Update existing
            config.value = value_str
            config.value_type = value_type
            if description:
                config.description = description
            config.updated_by_user_id = updated_by_user_id
        else:
            # Create new
            config = Configuration(
                key=key,
                value=value_str,
                value_type=value_type,
                description=description or f"Configuration for {key}",
                updated_by_user_id=updated_by_user_id,
            )
            self.db.add(config)

        self.db.commit()
        self.db.refresh(config)
        logger.info(f"Set configuration {key} = {value_str} (type: {value_type})")
        return config

    def get_all_configs(self) -> dict[str, Any]:
        """
        Get all configurations as a dictionary.

        Returns:
            Dictionary of key-value pairs
        """
        configs = self.db.query(Configuration).all()
        return {config.key: self.get_value(config.key) for config in configs}

    def seed_default_configs(self) -> None:
        """
        Seed default configuration values.

        Should be called during initial database setup.
        """
        defaults = {
            "random_dm_interval_hours": (24, "Hours between random proactive DMs"),
            "thread_response_probability": (0.20, "Probability of responding to threads (0.0-1.0)"),
            "reaction_probability": (0.15, "Probability of reacting with emoji (0.0-1.0)"),
            "image_post_interval_days": (7, "Days between AI-generated image posts"),
            "conversation_retention_days": (90, "Days to retain conversation history"),
            "max_context_messages": (10, "Maximum message pairs to include in LLM context"),
            "max_tokens_per_request": (4000, "Maximum tokens per LLM request"),
        }

        for key, (value, description) in defaults.items():
            existing = self.get_config(key)
            if not existing:
                self.set_value(key, value, description)
                logger.info(f"Seeded default config: {key} = {value}")
