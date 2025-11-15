"""
Persona service.

Manages Lukas the Bear's personality and system prompt generation.
"""

import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pytz
import yaml

from src.utils.config_loader import config
from src.utils.logger import logger


class PersonaService:
    """
    Service for managing Lukas the Bear's persona and prompts.

    Loads personality configuration from persona_prompts.yml and generates
    context-appropriate system prompts.
    """

    def __init__(self, persona_file: str = "config/persona_prompts.yml"):
        """
        Initialize persona service.

        Args:
            persona_file: Path to persona prompts YAML file
        """
        self.persona_file = persona_file
        self.config: Dict = {}
        self._load_persona_config()

    def _load_persona_config(self) -> None:
        """Load persona configuration from YAML file."""
        persona_path = Path(self.persona_file)

        if not persona_path.exists():
            logger.warning(f"Persona file {self.persona_file} not found, using defaults")
            self.config = self._get_default_config()
            return

        try:
            with open(persona_path, "r") as f:
                self.config = yaml.safe_load(f) or {}
            logger.info(f"Loaded persona configuration from {persona_path}")
        except Exception as e:
            logger.error(f"Error loading persona file: {e}")
            self.config = self._get_default_config()

    def _get_default_config(self) -> Dict:
        """Get default persona configuration."""
        return {
            "system_prompt": "You are Lukas the Bear, a friendly chatbot mascot.",
            "fallback_responses": [
                "I'm having trouble thinking right now. Can you try again?"
            ],
            "greeting_templates": ["Hi there!"],
        }

    def get_system_prompt(self, context: Optional[Dict] = None) -> str:
        """
        Generate system prompt for Lukas.

        Args:
            context: Optional context for prompt customization

        Returns:
            System prompt string with current date/time prepended
        """
        base_prompt = self.config.get("system_prompt", "You are Lukas the Bear.")

        # Get timezone from config (with fallback to Germany/Berlin)
        timezone_str = config.get("bot.engagement.active_hours.timezone", "Germany/Berlin")

        # Handle common timezone name variations (Germany/Berlin -> Europe/Berlin)
        timezone_str = timezone_str.replace("Germany/", "Europe/")

        try:
            tz = pytz.timezone(timezone_str)
            current_time = datetime.now(tz)

            # Format: "October 29, 2025 at 14:30 CEST"
            formatted_date = current_time.strftime("%B %d, %Y at %H:%M %Z")

            # Prepend date/time to system prompt
            datetime_header = f"Current date and time: {formatted_date}\n\n"
            return datetime_header + base_prompt

        except Exception as e:
            logger.warning(f"Failed to add date/time to system prompt: {e}. Using base prompt only.")
            return base_prompt

    def get_fallback_response(self) -> str:
        """
        Get a random fallback response for when LLM fails.

        Returns:
            Fallback response string
        """
        fallbacks = self.config.get("fallback_responses", [
            "I'm having trouble thinking right now. Can you try again?"
        ])
        return random.choice(fallbacks)

    def get_greeting_template(self) -> str:
        """
        Get a random greeting template for proactive DMs.

        Returns:
            Greeting template string
        """
        greetings = self.config.get("greeting_templates", ["Hi there!"])
        greeting = random.choice(greetings)

        # Replace time_of_day placeholder
        hour = datetime.now().hour
        if 5 <= hour < 12:
            time_of_day = "morning"
        elif 12 <= hour < 17:
            time_of_day = "afternoon"
        elif 17 <= hour < 22:
            time_of_day = "evening"
        else:
            time_of_day = "night"

        return greeting.replace("{time_of_day}", time_of_day)

    def get_image_caption(self) -> str:
        """
        Get a random image caption for AI-generated bear images.

        Returns:
            Image caption string
        """
        captions = self.config.get("image_captions", [
            "Here's a little bear art to brighten your day! 🐻✨"
        ])
        return random.choice(captions)

    def get_image_prompt(self, occasion: Optional[str] = None) -> str:
        """
        Get an image generation prompt based on occasion/season.

        Args:
            occasion: Optional occasion/season (spring, summer, fall, winter, etc.)

        Returns:
            Image generation prompt
        """
        prompts_config = self.config.get("image_prompts", {})

        if occasion:
            # Try seasonal or special occasion prompts
            seasonal_prompts = prompts_config.get("seasonal", {})
            occasion_prompts = prompts_config.get("special_occasions", {})

            if occasion in seasonal_prompts:
                prompts = seasonal_prompts[occasion]
                return random.choice(prompts)
            elif occasion in occasion_prompts:
                prompts = occasion_prompts[occasion]
                return random.choice(prompts)

        # Default prompts
        default_prompts = prompts_config.get("default", [
            "A friendly cartoon bear mascot, digital art, warm colors"
        ])
        return random.choice(default_prompts)

    def get_emoji_reactions(self, category: str = "positive") -> List[str]:
        """
        Get emoji reactions for a specific category.

        Args:
            category: Emoji category (positive, thinking, bear_themed, encouragement)

        Returns:
            List of emoji names (without colons)
        """
        reactions_config = self.config.get("emoji_reactions", {})
        return reactions_config.get(category, ["thumbsup"])


# Global persona service instance
persona_service = PersonaService()
