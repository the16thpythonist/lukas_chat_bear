"""
Command handler for admin commands and triggers.

Handles special commands like on-demand image generation.
"""

import re
from typing import Optional, Tuple

from src.repositories.team_member_repo import TeamMemberRepository
from src.utils.database import get_db
from src.utils.logger import logger


async def handle_generate_image_command(event: dict, say, client):
    """
    Handle on-demand image generation command from admins.

    Command format: "generate image [theme] [to #channel]"
    Examples:
      - "generate image" (seasonal, current channel)
      - "generate image halloween" (specific theme, current channel)
      - "generate image to #random" (seasonal, specified channel)
      - "generate image halloween to #random" (theme + channel)

    Args:
        event: Slack event data
        say: Slack say function for responding
        client: Slack client
    """
    try:
        user_id = event.get("user")
        text = event.get("text", "").strip()
        channel = event.get("channel")

        # Check if user is admin
        with get_db() as db:
            team_member_repo = TeamMemberRepository(db)
            team_member = team_member_repo.get_by_slack_user_id(user_id)

            if not team_member or not team_member.is_admin:
                await say("Sorry, only admins can trigger image generation!")
                logger.warning(f"Non-admin user {user_id} tried to generate image")
                return

        # Parse command
        theme, target_channel = parse_generate_image_command(text)

        # Use current channel if not specified
        if not target_channel:
            target_channel = channel

        # Acknowledge command
        await say(f"Generating a bear image{f' with {theme} theme' if theme else ''}... :bear:")

        # Import image service (avoid circular imports)
        from src.services.image_service import image_service

        if not image_service:
            await say("Image service not available. Please check configuration.")
            logger.error("Image service not initialized")
            return

        # Generate and post image
        result = await image_service.generate_and_post(
            channel_id=target_channel,
            theme=theme,
            occasion=None,
        )

        if result and result.status == "posted":
            if target_channel != channel:
                await say(f"Image posted to <#{target_channel}>!")
            logger.info(f"Admin {user_id} triggered image generation: {result.id}")
        elif result and result.status == "failed":
            await say(f"Failed to generate image: {result.error_message}")
            logger.error(f"Image generation failed: {result.error_message}")
        else:
            await say("Failed to generate or post image. Please check logs.")
            logger.error("Image generation failed (unknown error)")

    except Exception as e:
        logger.error(f"Error handling generate image command: {e}")
        await say("An error occurred while generating the image.")


def parse_generate_image_command(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse generate image command to extract theme and channel.

    Args:
        text: Command text (e.g., "generate image halloween to #random")

    Returns:
        Tuple of (theme, channel_id)
    """
    # Normalize text
    text = text.lower().strip()

    # Remove "generate image" prefix
    if text.startswith("generate image"):
        text = text[len("generate image"):].strip()
    elif text.startswith("gen image"):
        text = text[len("gen image"):].strip()

    # Extract channel (format: "to #channel" or "to C123456")
    channel_id = None
    channel_match = re.search(r"to\s+[#<]?([a-zA-Z0-9_-]+)[>]?", text)
    if channel_match:
        channel_id = channel_match.group(1)
        # Remove channel part from text
        text = text[:channel_match.start()] + text[channel_match.end():]
        text = text.strip()

    # Remaining text is theme (if any)
    theme = text.strip() if text.strip() else None

    # Validate theme (must be reasonable)
    if theme and len(theme) > 50:
        theme = None  # Too long, ignore

    return theme, channel_id


async def handle_app_mention(event: dict, say, client):
    """
    Handle @mentions of the bot for commands.

    Args:
        event: Slack event data
        say: Slack say function
        client: Slack client
    """
    try:
        user_id = event.get("user")
        text = event.get("text", "").strip()
        channel = event.get("channel")

        # Ignore bot messages
        if event.get("bot_id"):
            return

        logger.info(f"Received mention from {user_id}: {text}")

        # Remove bot mention from text
        # Format: <@U123ABC> text here
        text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

        # Check for image generation command
        if text.lower().startswith(("generate image", "gen image", "post image")):
            await handle_generate_image_command(event, say, client)
            return

        # Default: treat as conversational message
        # (This will be expanded in Phase 6 with more commands)
        from src.handlers.message_handler import handle_direct_message

        # Treat mention as DM for now
        await handle_direct_message(event, say, client)

    except Exception as e:
        logger.error(f"Error handling app mention: {e}")
        await say("Sorry, I had trouble understanding that command.")


def register_command_handlers(app):
    """
    Register command handlers with Slack app.

    Args:
        app: Slack Bolt app instance
    """
    @app.event("app_mention")
    async def handle_mention_event(event, say, client):
        await handle_app_mention(event, say, client)

    logger.info("Command handlers registered")
