"""
Proactive DM Service

Handles sending random proactive DMs to team members to maintain engagement.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from unittest.mock import Mock

from slack_sdk.errors import SlackApiError
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.models.scheduled_task import ScheduledTask, TaskType, TaskStatus, TargetType
from src.models.team_member import TeamMember
from src.services.engagement_service import EngagementService
from src.services.persona_service import PersonaService
from src.repositories.team_member_repo import TeamMemberRepository
from src.repositories.conversation_repo import ConversationRepository
from src.services.scheduler_service import update_task_after_execution
from src.utils.config_loader import config

logger = logging.getLogger(__name__)


class ProactiveDMService:
    """Service for sending proactive DMs to team members."""

    def __init__(
        self,
        db_session: Session,
        engagement_service: Optional[EngagementService] = None,
        persona_service: Optional[PersonaService] = None,
    ):
        """
        Initialize the ProactiveDMService.

        Args:
            db_session: Database session for operations
            engagement_service: Optional EngagementService instance
            persona_service: Optional PersonaService instance
        """
        self.db_session = db_session
        self.engagement_service = engagement_service or EngagementService(db_session)
        self.persona_service = persona_service or PersonaService()
        self.team_member_repo = TeamMemberRepository(db_session)
        self.conversation_repo = ConversationRepository(db_session)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(SlackApiError),
        reraise=True,
    )
    async def _send_slack_dm(
        self, slack_client: Mock, user_id: str, message: str
    ) -> Dict[str, Any]:
        """
        Send a DM via Slack API with retry logic.

        Args:
            slack_client: Slack WebClient instance
            user_id: Slack user ID to send DM to
            message: Message text to send

        Returns:
            dict with 'channel_id' and 'message_ts'

        Raises:
            SlackApiError: If Slack API call fails after retries
        """
        # Open DM conversation (reuses existing if one exists)
        logger.info(f"Opening DM conversation with user {user_id}")
        dm_response = await slack_client.conversations_open(users=[user_id])

        if not dm_response.get("ok"):
            error_msg = dm_response.get("error", "unknown_error")
            logger.error(f"Failed to open DM conversation: {error_msg}")
            raise SlackApiError(
                message=f"Failed to open conversation: {error_msg}",
                response=dm_response,
            )

        dm_channel_id = dm_response["channel"]["id"]
        # Check if this is a new or existing conversation
        channel_info = dm_response.get("channel", {})
        is_new = channel_info.get("is_im", False) and not channel_info.get("created", 0)

        if "created" in channel_info:
            logger.info(
                f"DM channel opened: {dm_channel_id} "
                f"(conversation created: {datetime.fromtimestamp(channel_info['created'])})"
            )
        else:
            logger.info(f"DM channel opened: {dm_channel_id} (reusing existing conversation)")

        # Send message
        logger.info(f"Sending proactive DM to channel {dm_channel_id}")
        logger.info(f"Message preview: {message[:100]}{'...' if len(message) > 100 else ''}")
        msg_response = await slack_client.chat_postMessage(
            channel=dm_channel_id, text=message
        )

        if not msg_response.get("ok"):
            error_msg = msg_response.get("error", "unknown_error")
            logger.error(f"Failed to send message: {error_msg}")
            raise SlackApiError(
                message=f"Failed to send message: {error_msg}", response=msg_response
            )

        logger.info(
            f"✓ Message sent successfully to {dm_channel_id} "
            f"(timestamp: {msg_response['ts']})"
        )

        return {
            "channel_id": dm_channel_id,
            "message_ts": msg_response["ts"],
        }


    async def send_random_dm(
        self,
        app: Mock,
        slack_client: Mock,
    ) -> Dict[str, Any]:
        """
        Send a random proactive DM to an eligible team member.

        This is the main entry point for the random DM feature. It:
        1. Selects an eligible recipient using fair distribution
        2. Generates a personalized greeting message
        3. Sends the DM via Slack API
        4. Updates the user's last_proactive_dm_at timestamp
        5. Creates a ScheduledTask record for tracking

        Args:
            app: Slack App instance (can be mocked for testing)
            slack_client: Slack WebClient instance

        Returns:
            dict with keys:
                - success (bool): Whether the operation succeeded
                - user_selected (str|None): Slack user ID of selected user
                - message_sent (str|None): The message text that was sent
                - dm_channel_id (str|None): The DM channel ID
                - timestamp_updated (datetime|None): When timestamp was updated
                - task_id (int|None): ScheduledTask record ID
                - error (str|None): Error message if failed
                - reason (str|None): Reason for failure (e.g., 'no_eligible_users')
        """
        result = {
            "success": False,
            "user_selected": None,
            "message_sent": None,
            "dm_channel_id": None,
            "timestamp_updated": None,
            "task_id": None,
            "error": None,
            "reason": None,
        }

        try:
            # Step 1: Select recipient
            logger.info("Selecting random DM recipient")
            recipient = self.engagement_service.select_dm_recipient()

            if not recipient:
                logger.warning("No eligible users for random DM")
                result["reason"] = "no_eligible_users"
                return result

            user_id = recipient.slack_user_id
            result["user_selected"] = user_id
            logger.info(f"Selected user {user_id} for random DM")

            # Step 2: Generate greeting message
            logger.info("Generating greeting message")
            greeting = self.persona_service.get_greeting_template()
            result["message_sent"] = greeting
            logger.debug(f"Generated greeting: {greeting}")

            # Step 3: Send DM via Slack API
            try:
                slack_result = await self._send_slack_dm(
                    slack_client, user_id, greeting
                )
                result["dm_channel_id"] = slack_result["channel_id"]
                logger.info(
                    f"Successfully sent DM to {user_id} in channel {slack_result['channel_id']}"
                )

                # Save message to database for Activity Log
                try:
                    # Get or create conversation for this DM
                    conversation = self.conversation_repo.get_or_create_conversation(
                        team_member_id=recipient.id,
                        channel_type="dm",
                        channel_id=slack_result["channel_id"],
                        thread_ts=None
                    )

                    # Save bot message to database
                    self.conversation_repo.add_message(
                        conversation_id=conversation.id,
                        sender_type="bot",
                        content=greeting,
                        slack_ts=slack_result["message_ts"],
                        token_count=len(greeting.split()),  # Rough estimate
                        metadata={
                            "sent_via": "proactive_dm",
                            "proactive_type": "random_dm",
                            "recipient_id": user_id,
                            "recipient_name": recipient.display_name if recipient.display_name else user_id
                        }
                    )
                    logger.info(f"Saved proactive DM to database (conversation {conversation.id})")
                except Exception as db_error:
                    # Log error but don't fail the operation - DM was sent successfully
                    logger.error(f"Failed to save proactive DM to database: {db_error}")
                    # Continue with the rest of the flow

            except SlackApiError as e:
                logger.error(f"Slack API error sending DM: {e}")
                result["error"] = str(e)
                # Update task record to failed
                interval_hours = config.get("bot.engagement.random_dm_interval_hours", 24)
                update_task_after_execution(
                    job_id="random_dm_task",
                    status=TaskStatus.FAILED,
                    error_message=str(e),
                    next_run_interval_hours=interval_hours,
                    metadata_update={
                        "recipient": user_id,
                        "recipient_name": recipient.display_name if recipient.display_name else user_id,
                        "attempted_message": greeting[:200]
                    }
                )
                raise  # Re-raise to prevent timestamp update

            # Step 4: Update user's last_proactive_dm_at timestamp
            logger.info(f"Updating last_proactive_dm_at for user {user_id}")
            self.engagement_service.update_last_proactive_dm(recipient)
            result["timestamp_updated"] = recipient.last_proactive_dm_at
            logger.info(
                f"Updated timestamp to {result['timestamp_updated']}"
            )

            # Step 5: Update task record to completed
            interval_hours = config.get("bot.engagement.random_dm_interval_hours", 24)
            update_task_after_execution(
                job_id="random_dm_task",
                status=TaskStatus.COMPLETED,
                next_run_interval_hours=interval_hours,
                metadata_update={
                    "recipient": user_id,
                    "recipient_name": recipient.display_name if recipient.display_name else user_id,
                    "message": greeting[:200]  # Truncate to keep metadata reasonable
                }
            )

            result["success"] = True
            logger.info(f"Random DM workflow completed successfully for user {user_id}")
            return result

        except SlackApiError:
            # Already logged and task record updated above
            return result

        except Exception as e:
            logger.exception(f"Unexpected error in random DM workflow: {e}")
            result["error"] = str(e)
            # Update task record to failed
            interval_hours = config.get("bot.engagement.random_dm_interval_hours", 24)
            update_task_after_execution(
                job_id="random_dm_task",
                status=TaskStatus.FAILED,
                error_message=str(e),
                next_run_interval_hours=interval_hours
            )
            return result


# Module-level function for easy scheduler integration
async def send_random_proactive_dm(
    app: Mock,
    db_session: Session,
    slack_client: Mock,
    engagement_service: Optional[EngagementService] = None,
) -> Dict[str, Any]:
    """
    Send a random proactive DM to an eligible team member.

    This is a convenience function that creates a ProactiveDMService instance
    and calls send_random_dm(). Suitable for use with APScheduler.

    Args:
        app: Slack App instance
        db_session: Database session
        slack_client: Slack WebClient instance
        engagement_service: Optional EngagementService instance

    Returns:
        dict with result details (see ProactiveDMService.send_random_dm)
    """
    service = ProactiveDMService(
        db_session=db_session, engagement_service=engagement_service
    )
    return await service.send_random_dm(app, slack_client)
