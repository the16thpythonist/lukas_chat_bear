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
        # Open DM conversation
        logger.info(f"Opening DM conversation with user {user_id}")
        dm_response = slack_client.conversations_open(users=[user_id])

        if not dm_response.get("ok"):
            error_msg = dm_response.get("error", "unknown_error")
            logger.error(f"Failed to open DM conversation: {error_msg}")
            raise SlackApiError(
                message=f"Failed to open conversation: {error_msg}",
                response=dm_response,
            )

        dm_channel_id = dm_response["channel"]["id"]
        logger.info(f"DM channel opened: {dm_channel_id}")

        # Send message
        logger.info(f"Sending message to channel {dm_channel_id}")
        msg_response = slack_client.chat_postMessage(
            channel=dm_channel_id, text=message
        )

        if not msg_response.get("ok"):
            error_msg = msg_response.get("error", "unknown_error")
            logger.error(f"Failed to send message: {error_msg}")
            raise SlackApiError(
                message=f"Failed to send message: {error_msg}", response=msg_response
            )

        return {
            "channel_id": dm_channel_id,
            "message_ts": msg_response["ts"],
        }

    def _create_task_record(
        self,
        user_id: str,
        status: TaskStatus,
        error_message: Optional[str] = None,
    ) -> ScheduledTask:
        """
        Create a ScheduledTask record to track the DM attempt.

        Args:
            user_id: Slack user ID
            status: Task status
            error_message: Optional error message if failed

        Returns:
            Created ScheduledTask instance
        """
        import uuid
        task = ScheduledTask(
            job_id=f"random_dm_{user_id}_{uuid.uuid4().hex[:8]}",
            task_type=TaskType.RANDOM_DM.value,
            target_type=TargetType.USER.value,
            target_id=user_id,
            scheduled_at=datetime.now(),
            executed_at=datetime.now() if status != TaskStatus.PENDING else None,
            status=status.value,
            error_message=error_message,
            retry_count=0,
        )
        self.db_session.add(task)
        self.db_session.commit()
        return task

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

            except SlackApiError as e:
                logger.error(f"Slack API error sending DM: {e}")
                result["error"] = str(e)
                # Create failed task record
                task = self._create_task_record(
                    user_id, TaskStatus.FAILED, error_message=str(e)
                )
                result["task_id"] = task.id
                raise  # Re-raise to prevent timestamp update

            # Step 4: Update user's last_proactive_dm_at timestamp
            logger.info(f"Updating last_proactive_dm_at for user {user_id}")
            self.engagement_service.update_last_proactive_dm(recipient)
            result["timestamp_updated"] = recipient.last_proactive_dm_at
            logger.info(
                f"Updated timestamp to {result['timestamp_updated']}"
            )

            # Step 5: Create successful task record
            task = self._create_task_record(user_id, TaskStatus.COMPLETED)
            result["task_id"] = task.id

            result["success"] = True
            logger.info(f"Random DM workflow completed successfully for user {user_id}")
            return result

        except SlackApiError:
            # Already logged and task record created above
            return result

        except Exception as e:
            logger.exception(f"Unexpected error in random DM workflow: {e}")
            result["error"] = str(e)
            if result["user_selected"]:
                # Create failed task record if we got far enough to select a user
                task = self._create_task_record(
                    result["user_selected"],
                    TaskStatus.FAILED,
                    error_message=str(e),
                )
                result["task_id"] = task.id
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
