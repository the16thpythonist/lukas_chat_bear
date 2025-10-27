"""
Command Service - Business logic for bot commands.

Framework-agnostic command execution that can be used by:
- Slack command handlers (via command_handler.py)
- MCP server tools (via mcp_server.py)

Returns structured dictionaries instead of formatted strings for flexibility.
"""

import re
import os
import json
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from slack_sdk import WebClient
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.repositories.team_member_repo import TeamMemberRepository
from src.repositories.config_repo import ConfigurationRepository
from src.models.team_member import TeamMember
from src.models.scheduled_task import ScheduledTask
from src.models.engagement_event import EngagementEvent
from src.models.conversation import ConversationSession
from src.services.scheduler_service import scheduler
from src.utils.logger import logger
from src.utils.database import get_db


class PermissionDeniedError(Exception):
    """Raised when a user lacks permission to execute a command."""

    def __init__(self, command_type: str, user_name: str, message: str = None):
        self.command_type = command_type
        self.user_name = user_name
        if message:
            self.message = message
        else:
            self.message = (
                f"Sorry {user_name}, the '{command_type}' command requires admin privileges. "
                f"Only admins can execute this command."
            )
        super().__init__(self.message)


class CommandService:
    """
    Command business logic service.

    Framework-agnostic implementation that can be used by both
    Slack handlers and MCP tools.
    """

    def __init__(self, db_session: Session, slack_client: Optional[WebClient] = None):
        """
        Initialize command service.

        Args:
            db_session: SQLAlchemy database session
            slack_client: Slack WebClient (optional, required for post/image commands)
        """
        self.db = db_session
        self.slack_client = slack_client
        self.config_repo = ConfigurationRepository(db_session)
        self.team_member_repo = TeamMemberRepository(db_session)

    async def post_message(
        self,
        message: str,
        channel: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Post a message to a Slack channel as Lukas the Bear.

        Args:
            message: Message content to post
            channel: Channel name (with or without #) or channel ID
            user_id: Optional Slack user ID (for logging purposes only, not shown in message)

        Returns:
            {
                "success": bool,
                "channel": str,
                "error": Optional[str],
                "message": str  # Human-readable result
            }
        """
        try:
            # Get user for logging (optional)
            user = None
            if user_id:
                user = self.team_member_repo.get_by_slack_id(user_id)
                if not user:
                    logger.warning(f"User {user_id} not found for logging post_message")

            # Check if Slack client is available
            if not self.slack_client:
                return {
                    "success": False,
                    "channel": channel,
                    "error": "Slack client not available",
                    "message": "Cannot post message: Slack client not initialized"
                }

            # Normalize channel (remove # if present)
            channel_id = channel.lstrip("#")

            # Post message as Lukas the Bear (no attribution - bot posts as himself)
            formatted_message = message

            # Post message to channel (sync call - WebClient is not async)
            response = self.slack_client.chat_postMessage(
                channel=channel_id,
                text=formatted_message,
                unfurl_links=False,
                unfurl_media=False,
            )

            if response.get("ok"):
                requester = user.display_name if user else "Lukas (via command)"
                logger.info(f"Posted message to {channel_id} (requested by: {requester})")
                return {
                    "success": True,
                    "channel": channel_id,
                    "message": f"Posted message to #{channel_id}"
                }
            else:
                error = response.get("error", "Unknown error")
                logger.error(f"Failed to post message: {error}")
                return {
                    "success": False,
                    "channel": channel_id,
                    "error": error,
                    "message": f"Failed to post: {error}"
                }

        except Exception as e:
            logger.error(f"Error posting message to {channel}: {e}")

            # Provide helpful error message
            if "not_in_channel" in str(e) or "channel_not_found" in str(e):
                error_msg = "I'm not a member of that channel."
            elif "invalid_channel" in str(e):
                error_msg = "That channel doesn't exist."
            else:
                error_msg = str(e)

            return {
                "success": False,
                "channel": channel,
                "error": error_msg,
                "message": f"Error posting to #{channel}: {error_msg}"
            }

    async def create_reminder(
        self,
        task: str,
        when: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Create a reminder for a user.

        Supports both duration-based ("30 minutes", "2 hours") and
        time-based ("3pm", "14:30", "tomorrow at 9am") reminders.

        Args:
            task: What to remind the user about
            when: When to send reminder (duration or time string)
            user_id: Slack user ID to remind

        Returns:
            {
                "success": bool,
                "scheduled_at": Optional[datetime],
                "when_description": str,
                "task": str,
                "error": Optional[str],
                "message": str
            }
        """
        try:
            # Get user
            user = self.team_member_repo.get_by_slack_id(user_id)
            if not user:
                return {
                    "success": False,
                    "scheduled_at": None,
                    "when_description": when,
                    "task": task,
                    "error": "User not found",
                    "message": f"User {user_id} not found"
                }

            # Parse when string to determine scheduled time
            scheduled_at, when_description = self._parse_when_string(when)

            if scheduled_at is None:
                return {
                    "success": False,
                    "scheduled_at": None,
                    "when_description": when,
                    "task": task,
                    "error": f"Invalid time format: {when}",
                    "message": f"I couldn't understand the time '{when}'. Try '30 minutes', '2 hours', or '3pm'."
                }

            # Create scheduled task in database
            task_record = ScheduledTask(
                id=str(uuid.uuid4()),
                job_id=f"reminder_{user.id}_{int(datetime.now().timestamp())}",
                task_type="reminder",
                target_type="user",
                target_id=user.slack_user_id,
                scheduled_at=scheduled_at,
                status="pending",
                metadata=json.dumps({
                    "message": task,
                    "requested_by": user.display_name
                }),
            )

            self.db.add(task_record)
            self.db.commit()

            # Schedule the job with APScheduler
            scheduler.add_job(
                func=self._send_reminder,
                trigger="date",
                run_date=scheduled_at,
                args=[user.slack_user_id, task, task_record.id],
                id=task_record.job_id,
                replace_existing=True,
            )

            logger.info(f"Scheduled reminder for {user.display_name} at {scheduled_at}: {task}")

            return {
                "success": True,
                "scheduled_at": scheduled_at,
                "when_description": when_description,
                "task": task,
                "message": f"Reminder set for {when_description}: {task}"
            }

        except Exception as e:
            logger.error(f"Error creating reminder: {e}")
            return {
                "success": False,
                "scheduled_at": None,
                "when_description": when,
                "task": task,
                "error": str(e),
                "message": f"Failed to create reminder: {str(e)}"
            }

    async def get_info(
        self,
        info_type: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get team info, bot status, or engagement statistics.

        Args:
            info_type: Type of info ("team", "status", or "stats")
            user_id: Optional user ID for personalized info

        Returns:
            {
                "success": bool,
                "info_type": str,
                "data": dict,  # Structured data
                "formatted": str,  # Human-readable format
                "error": Optional[str]
            }
        """
        try:
            if info_type == "team":
                data, formatted = self._get_team_info()
            elif info_type == "status":
                data, formatted = self._get_bot_status()
            elif info_type == "stats":
                data, formatted = self._get_engagement_stats()
            else:
                return {
                    "success": False,
                    "info_type": info_type,
                    "data": {},
                    "formatted": "",
                    "error": f"Unknown info type: {info_type}"
                }

            return {
                "success": True,
                "info_type": info_type,
                "data": data,
                "formatted": formatted
            }

        except Exception as e:
            logger.error(f"Error retrieving info ({info_type}): {e}")
            return {
                "success": False,
                "info_type": info_type,
                "data": {},
                "formatted": "",
                "error": str(e)
            }

    async def update_config(
        self,
        setting: str,
        value: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Update bot configuration (admin only).

        Args:
            setting: Setting name ("dm_interval", "thread_probability", "image_interval")
            value: New value for the setting
            user_id: Slack user ID (must be admin)

        Returns:
            {
                "success": bool,
                "setting": str,
                "value": str,
                "error": Optional[str],
                "message": str
            }
        """
        try:
            # Get user and check admin status
            user = self.team_member_repo.get_by_slack_id(user_id)
            if not user:
                return {
                    "success": False,
                    "setting": setting,
                    "value": value,
                    "error": "User not found",
                    "message": f"User {user_id} not found"
                }

            if not user.is_admin:
                raise PermissionDeniedError("config", user.display_name)

            # Validate and parse value based on setting
            config_key = None
            parsed_value = None
            value_type = None

            if setting == "dm_interval":
                # Parse "X hours" format
                hours = self._parse_hours_from_string(value)
                if hours is None:
                    return {
                        "success": False,
                        "setting": setting,
                        "value": value,
                        "error": "Invalid format",
                        "message": "Invalid format. Use '24 hours' or '12 hrs'"
                    }

                config_key = "random_dm_interval_hours"
                parsed_value = str(hours)
                value_type = "integer"

            elif setting == "thread_probability":
                # Parse probability (0.0-1.0)
                try:
                    prob = float(value.strip())
                    if prob < 0.0 or prob > 1.0:
                        return {
                            "success": False,
                            "setting": setting,
                            "value": value,
                            "error": "Value out of range",
                            "message": "Probability must be between 0.0 and 1.0"
                        }

                    config_key = "thread_response_probability"
                    parsed_value = str(prob)
                    value_type = "float"

                except ValueError:
                    return {
                        "success": False,
                        "setting": setting,
                        "value": value,
                        "error": "Invalid number",
                        "message": "Invalid number format"
                    }

            elif setting == "image_interval":
                # Parse "X days" format
                days = self._parse_days_from_string(value)
                if days is None:
                    return {
                        "success": False,
                        "setting": setting,
                        "value": value,
                        "error": "Invalid format",
                        "message": "Invalid format. Use '7 days' or '14 days'"
                    }

                config_key = "image_post_interval_days"
                parsed_value = str(days)
                value_type = "integer"

            else:
                return {
                    "success": False,
                    "setting": setting,
                    "value": value,
                    "error": "Unknown setting",
                    "message": f"Unknown setting: {setting}"
                }

            # Update configuration in database
            self.config_repo.update_config(
                key=config_key,
                value=parsed_value,
                value_type=value_type,
                updated_by_user_id=user.id,
            )

            logger.info(f"Admin {user.display_name} updated {config_key} to {parsed_value}")

            # Apply changes to running services
            self._apply_config_changes(setting, parsed_value)

            return {
                "success": True,
                "setting": setting,
                "value": value,
                "message": f"Updated {setting} to {value}"
            }

        except PermissionDeniedError as e:
            logger.warning(f"Permission denied: {e.message}")
            return {
                "success": False,
                "setting": setting,
                "value": value,
                "error": "Permission denied",
                "message": e.message
            }
        except Exception as e:
            logger.error(f"Error updating config ({setting}): {e}")
            return {
                "success": False,
                "setting": setting,
                "value": value,
                "error": str(e),
                "message": f"Failed to update {setting}: {str(e)}"
            }

    async def generate_image(
        self,
        theme: Optional[str],
        channel: Optional[str],
        user_id: str
    ) -> Dict[str, Any]:
        """
        Generate and post AI image (admin only).

        Args:
            theme: Optional theme/description for image
            channel: Optional channel to post to (defaults to current)
            user_id: Slack user ID (must be admin)

        Returns:
            {
                "success": bool,
                "theme": Optional[str],
                "channel": Optional[str],
                "image_id": Optional[str],
                "error": Optional[str],
                "message": str
            }
        """
        try:
            # Get user and check admin status
            user = self.team_member_repo.get_by_slack_id(user_id)
            if not user:
                return {
                    "success": False,
                    "theme": theme,
                    "channel": channel,
                    "error": "User not found",
                    "message": f"User {user_id} not found"
                }

            if not user.is_admin:
                raise PermissionDeniedError("generate_image", user.display_name)

            # Import image service
            from src.services.image_service import image_service

            if not image_service:
                return {
                    "success": False,
                    "theme": theme,
                    "channel": channel,
                    "error": "Image service not available",
                    "message": "Image service not initialized. Check configuration."
                }

            # Generate and post image
            result = await image_service.generate_and_post(
                channel_id=channel,
                theme=theme,
                occasion=None,
            )

            if result and result.status == "posted":
                logger.info(f"Admin {user_id} generated image: {result.id}")
                return {
                    "success": True,
                    "theme": theme,
                    "channel": channel,
                    "image_id": result.id,
                    "message": f"Generated and posted image{f' with {theme} theme' if theme else ''}"
                }
            elif result and result.status == "failed":
                logger.error(f"Image generation failed: {result.error_message}")
                return {
                    "success": False,
                    "theme": theme,
                    "channel": channel,
                    "error": result.error_message,
                    "message": f"Failed to generate image: {result.error_message}"
                }
            else:
                logger.error("Image generation failed (unknown error)")
                return {
                    "success": False,
                    "theme": theme,
                    "channel": channel,
                    "error": "Unknown error",
                    "message": "Failed to generate or post image"
                }

        except PermissionDeniedError as e:
            logger.warning(f"Permission denied: {e.message}")
            return {
                "success": False,
                "theme": theme,
                "channel": channel,
                "error": "Permission denied",
                "message": e.message
            }
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            return {
                "success": False,
                "theme": theme,
                "channel": channel,
                "error": str(e),
                "message": f"Error generating image: {str(e)}"
            }

    # ===== HELPER METHODS =====

    def _parse_when_string(self, when: str) -> tuple[Optional[datetime], str]:
        """
        Parse 'when' string to datetime and description.

        Handles both duration ("30 minutes", "2 hours") and
        time ("3pm", "14:30") formats.

        Returns:
            (scheduled_datetime, description_string)
        """
        when = when.lower().strip()

        # Try parsing as duration first
        duration_minutes = self._parse_duration_to_minutes(when)
        if duration_minutes is not None:
            scheduled_at = datetime.now() + timedelta(minutes=duration_minutes)
            return scheduled_at, f"in {when}"

        # Try parsing as time
        scheduled_at = self._parse_time_to_datetime(when)
        if scheduled_at is not None:
            return scheduled_at, f"at {when}"

        # Could not parse
        return None, when

    def _parse_duration_to_minutes(self, duration: str) -> Optional[int]:
        """Parse duration string to minutes (e.g., '30 minutes', '2 hours')."""
        duration = duration.lower().strip()

        match = re.match(r"^(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs)$", duration)
        if not match:
            return None

        number = int(match.group(1))
        unit = match.group(2)

        if unit in ["minute", "minutes", "min", "mins"]:
            return number
        elif unit in ["hour", "hours", "hr", "hrs"]:
            return number * 60
        else:
            return None

    def _parse_time_to_datetime(self, time_str: str) -> Optional[datetime]:
        """Parse time string to datetime (today)."""
        time_str = time_str.lower().strip()
        now = datetime.now()

        # Try different formats
        formats = [
            "%I%p",      # 3pm
            "%I:%M%p",   # 2:30pm
            "%H:%M",     # 14:30
        ]

        for fmt in formats:
            try:
                parsed_time = datetime.strptime(time_str, fmt)
                # Combine with today's date
                scheduled = now.replace(
                    hour=parsed_time.hour,
                    minute=parsed_time.minute,
                    second=0,
                    microsecond=0,
                )

                # If time has passed today, schedule for tomorrow
                if scheduled < now:
                    scheduled += timedelta(days=1)

                return scheduled
            except ValueError:
                continue

        return None

    def _parse_hours_from_string(self, value: str) -> Optional[int]:
        """Parse hours from string like '24 hours' or '12 hrs'."""
        value = value.lower().strip()

        match = re.match(r"^(\d+)\s*(?:hour|hours|hr|hrs)$", value)
        if match:
            return int(match.group(1))

        # Try parsing just a number
        try:
            return int(value)
        except ValueError:
            return None

    def _parse_days_from_string(self, value: str) -> Optional[int]:
        """Parse days from string like '7 days' or '14 day'."""
        value = value.lower().strip()

        match = re.match(r"^(\d+)\s*(?:day|days)$", value)
        if match:
            return int(match.group(1))

        # Try parsing just a number
        try:
            return int(value)
        except ValueError:
            return None

    async def _send_reminder(self, user_id: str, message: str, task_id: str):
        """
        Send a reminder message to a user.

        Called by APScheduler when reminder time arrives.
        """
        try:
            # Import bot app to access client
            from src.bot import app

            # Send DM to user
            await app.client.chat_postMessage(
                channel=user_id,
                text=f"⏰ **Reminder:** {message}\n\n🐻 Hope this helps!",
            )

            # Update task status
            with get_db() as db:
                task = db.query(ScheduledTask).filter_by(id=task_id).first()
                if task:
                    task.status = "completed"
                    task.executed_at = datetime.now()
                    db.commit()

            logger.info(f"Sent reminder to {user_id}: {message}")

        except Exception as e:
            logger.error(f"Error sending reminder: {e}")

            # Update task status to failed
            with get_db() as db:
                task = db.query(ScheduledTask).filter_by(id=task_id).first()
                if task:
                    task.status = "failed"
                    task.error_message = str(e)
                    db.commit()

    def _get_team_info(self) -> tuple[dict, str]:
        """
        Get team member information.

        Returns:
            (data_dict, formatted_string)
        """
        # Query active team members
        members = (
            self.db.query(TeamMember)
            .filter_by(is_active=True, is_bot=False)
            .order_by(TeamMember.display_name)
            .all()
        )

        if not members:
            return {}, "🐻 No team members found. That's strange!"

        # Build structured data
        admin_count = sum(1 for m in members if m.is_admin)
        data = {
            "total_members": len(members),
            "admin_count": admin_count,
            "members": [
                {
                    "slack_user_id": m.slack_user_id,
                    "display_name": m.display_name,
                    "is_admin": m.is_admin,
                    "total_messages": m.total_messages_sent
                }
                for m in members
            ]
        }

        # Format for display
        formatted = "🐻 **Team Member Directory**\n\n"
        formatted += f"**Total Members:** {len(members)}\n"
        formatted += f"**Admins:** {admin_count}\n\n"

        for member in members:
            status = "👑" if member.is_admin else "👤"
            formatted += f"{status} <@{member.slack_user_id}> ({member.display_name})\n"

            if member.total_messages_sent > 0:
                formatted += f"   ↳ Messages: {member.total_messages_sent}\n"

        formatted += "\n_Need to update the team list? New members will be added automatically when they interact with me!_ 🐻"

        return data, formatted

    def _get_bot_status(self) -> tuple[dict, str]:
        """
        Get bot status and configuration.

        Returns:
            (data_dict, formatted_string)
        """
        # Get config from database
        configs = self.config_repo.get_all_configs()
        config_dict = {c.key: c.value for c in configs}

        dm_interval = config_dict.get("random_dm_interval_hours", "24")
        thread_prob = config_dict.get("thread_response_probability", "0.20")
        image_interval = config_dict.get("image_post_interval_days", "7")

        # Scheduler status
        job_count = len(scheduler.get_jobs())

        # MCP status
        use_mcp = os.getenv("USE_MCP_AGENT", "true").lower() == "true"
        openai_key = os.getenv("OPENAI_API_KEY")

        # Build structured data
        data = {
            "status": "online",
            "config": {
                "dm_interval_hours": dm_interval,
                "thread_probability": float(thread_prob),
                "image_interval_days": image_interval
            },
            "scheduler": {
                "active_jobs": job_count
            },
            "features": {
                "mcp_agent": use_mcp,
                "image_generation": bool(openai_key)
            }
        }

        # Format for display
        formatted = "🐻 **Lukas the Bear Status**\n\n"
        formatted += "**🟢 Status:** Online and ready!\n\n"

        formatted += "**⚙️ Configuration:**\n"
        formatted += f"• Random DM Interval: {dm_interval} hours\n"
        formatted += f"• Thread Engagement: {float(thread_prob) * 100:.0f}%\n"
        formatted += f"• Image Posting: Every {image_interval} days\n\n"

        formatted += "**📅 Scheduler:**\n"
        formatted += f"• Active Jobs: {job_count}\n\n"

        formatted += "**🔧 Features:**\n"
        formatted += f"• MCP Agent (Web Search): {'✅ Enabled' if use_mcp else '❌ Disabled'}\n"
        formatted += f"• Image Generation: {'✅ Enabled' if openai_key else '❌ Disabled'}\n\n"

        formatted += "_Everything looking good! 🐻_"

        return data, formatted

    def _get_engagement_stats(self) -> tuple[dict, str]:
        """
        Get engagement statistics.

        Returns:
            (data_dict, formatted_string)
        """
        # Query engagement events
        total_events = (
            self.db.query(func.count(EngagementEvent.id)).scalar() or 0
        )

        engaged_events = (
            self.db.query(func.count(EngagementEvent.id))
            .filter_by(engaged=True)
            .scalar()
            or 0
        )

        # Query conversations
        total_conversations = (
            self.db.query(func.count(ConversationSession.id)).scalar() or 0
        )

        active_conversations = (
            self.db.query(func.count(ConversationSession.id))
            .filter_by(is_active=True)
            .scalar()
            or 0
        )

        # Calculate engagement rate
        engagement_rate = (
            (engaged_events / total_events * 100) if total_events > 0 else 0
        )

        # Build structured data
        data = {
            "thread_engagement": {
                "total_events": total_events,
                "engaged_events": engaged_events,
                "engagement_rate": round(engagement_rate, 1)
            },
            "conversations": {
                "total": total_conversations,
                "active": active_conversations
            }
        }

        # Format for display
        formatted = "📊 **Engagement Statistics**\n\n"

        formatted += "**Thread Engagement:**\n"
        formatted += f"• Total Events: {total_events}\n"
        formatted += f"• Engaged: {engaged_events}\n"
        formatted += f"• Engagement Rate: {engagement_rate:.1f}%\n\n"

        formatted += "**Conversations:**\n"
        formatted += f"• Total Conversations: {total_conversations}\n"
        formatted += f"• Active: {active_conversations}\n\n"

        formatted += "_I love chatting with the team! 🐻_"

        return data, formatted

    def _apply_config_changes(self, setting: str, value: str):
        """Apply configuration changes to running services."""
        try:
            if setting == "dm_interval":
                logger.info(f"DM interval updated to {value} hours (restart required for full effect)")
            elif setting == "image_interval":
                logger.info(f"Image interval updated to {value} days (restart required for full effect)")
            elif setting == "thread_probability":
                logger.info(f"Thread probability updated to {value}")
        except Exception as e:
            logger.warning(f"Could not apply config changes dynamically: {e}")
