"""
Command handler - Simplified for MCP-based architecture.

All commands are now handled via LLM agent with MCP tools.
This file maintains backwards compatibility and helper functions.
"""

import re
from src.repositories.team_member_repo import TeamMemberRepository
from src.utils.database import get_db
from src.utils.logger import logger


# ===== HELPER FUNCTIONS =====


def get_user_from_slack_id(slack_user_id: str, db_session):
    """
    Get TeamMember from Slack user ID.

    Args:
        slack_user_id: Slack user ID (e.g., U123ABC)
        db_session: Database session

    Returns:
        TeamMember or None if not found
    """
    repo = TeamMemberRepository(db_session)
    return repo.get_by_slack_id(slack_user_id)


# ===== CONFIRMATION MESSAGE FORMATTER =====
# Kept for backwards compatibility with other parts of the codebase


class ConfirmationFormatter:
    """Format confirmation messages with Lukas's persona."""

    @staticmethod
    def post_success(channel_name: str) -> str:
        """Format success message for post command."""
        return f"✅ Done! I posted your message to #{channel_name}. 🐻"

    @staticmethod
    def post_failure(channel_name: str, reason: str) -> str:
        """Format failure message for post command."""
        return (
            f"❌ Oops! I couldn't post to #{channel_name}. {reason}\n\n"
            f"Make sure I'm invited to that channel! 🐻"
        )

    @staticmethod
    def reminder_success(when: str, task: str) -> str:
        """Format success message for reminder command."""
        return (
            f"⏰ Got it! I'll remind you {when} to: {task}\n\n"
            f"I won't forget! 🐻"
        )

    @staticmethod
    def reminder_failure(reason: str) -> str:
        """Format failure message for reminder command."""
        return (
            f"❌ I couldn't set that reminder. {reason}\n\n"
            f"Try asking me like: 'remind me in 30 minutes to check the build' 🐻"
        )

    @staticmethod
    def config_success(setting: str, value: str) -> str:
        """Format success message for config command."""
        setting_names = {
            "dm_interval": "random DM interval",
            "thread_probability": "thread engagement probability",
            "image_interval": "image posting interval",
        }
        friendly_name = setting_names.get(setting, setting)
        return (
            f"⚙️ Configuration updated! Set {friendly_name} to: {value}\n\n"
            f"The changes are now active. 🐻"
        )

    @staticmethod
    def config_failure(setting: str, reason: str) -> str:
        """Format failure message for config command."""
        return (
            f"❌ Couldn't update {setting}. {reason}\n\n"
            f"Please check the value and try again! 🐻"
        )

    @staticmethod
    def permission_denied(command_type: str) -> str:
        """Format permission denied message."""
        return (
            f"🚫 Sorry, that action requires admin privileges.\n\n"
            f"Contact an admin if you need help! 🐻"
        )

    @staticmethod
    def unknown_command(text: str) -> str:
        """Format unknown command message."""
        return (
            f"🤔 Hmm, I'm not sure I understand that.\n\n"
            f"Just ask me naturally - I can help with posting messages, setting reminders, "
            f"getting team info, and more! 🐻"
        )

    @staticmethod
    def error_message(error_details: str) -> str:
        """Format general error message."""
        return (
            f"😅 Oops! Something went wrong: {error_details}\n\n"
            f"Let me know if you need help troubleshooting! 🐻"
        )


# ===== APP MENTION HANDLER =====


async def handle_app_mention(event: dict, say, client):
    """
    Handle @mentions of the bot.

    All mentions are now processed through the LLM agent with MCP tools.
    The LLM will automatically decide whether to use command tools or respond conversationally.

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

        # Get user from database
        with get_db() as db:
            user = get_user_from_slack_id(user_id, db)

            if not user:
                await say("I don't recognize you yet! Send me a DM first so I can get to know you. 🐻")
                return

        # Pass to message handler (which uses LLM agent with MCP tools)
        from src.handlers.message_handler import handle_direct_message

        # The LLM agent will automatically use MCP tools for commands
        # like "remind me...", "post to #channel...", "team info", etc.
        await handle_direct_message(event, say, client)

    except Exception as e:
        logger.error(f"Error handling app mention: {e}", exc_info=True)
        await say("Sorry, I had trouble processing that request. 🐻")


# ===== HANDLER REGISTRATION =====


def register_command_handlers(app):
    """
    Register command handlers with Slack app.

    Args:
        app: Slack Bolt app instance
    """
    @app.event("app_mention")
    async def handle_mention_event(event, say, client):
        await handle_app_mention(event, say, client)

    logger.info("Command handlers registered (using LLM+MCP architecture)")
