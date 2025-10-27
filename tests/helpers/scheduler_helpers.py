"""
Test helpers for scheduler and random DM testing.

Provides utilities to manually trigger scheduled tasks without waiting for timers.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from unittest.mock import Mock
from sqlalchemy.orm import Session

from src.models.team_member import TeamMember
from src.models.scheduled_task import ScheduledTask, TaskType, TaskStatus
from src.services.engagement_service import EngagementService
from src.repositories.team_member_repo import TeamMemberRepository


async def trigger_random_dm_immediately(
    app: Mock,
    db_session: Session,
    mock_slack_client: Mock,
    engagement_service: Optional[EngagementService] = None
) -> Dict[str, Any]:
    """
    Manually trigger a random DM for testing without waiting for scheduler.

    This function simulates the complete random DM workflow:
    1. Select a recipient using EngagementService
    2. Generate a greeting message
    3. Open a DM conversation via Slack API
    4. Send the message
    5. Update the user's last_proactive_dm_at timestamp
    6. Create a ScheduledTask record

    Args:
        app: Mocked Slack App instance
        db_session: Database session for operations
        mock_slack_client: Mocked Slack WebClient
        engagement_service: Optional EngagementService instance (will create if None)

    Returns:
        dict with keys:
            - success (bool): Whether the operation succeeded
            - user_selected (str): Slack user ID of selected user
            - message_sent (str): The message text that was sent
            - dm_channel_id (str): The DM channel ID
            - timestamp_updated (datetime): When the timestamp was updated
            - task_id (int): ScheduledTask record ID
            - error (str): Error message if failed

    Raises:
        Exception: If Slack API calls fail (unless specifically handled)
    """
    from src.services.proactive_dm_service import send_random_proactive_dm

    result = await send_random_proactive_dm(
        app=app,
        db_session=db_session,
        slack_client=mock_slack_client,
        engagement_service=engagement_service
    )

    return result


def create_scheduled_task_record(
    db_session: Session,
    task_type: TaskType,
    target_id: str,
    status: TaskStatus = TaskStatus.PENDING,
    error_message: Optional[str] = None
) -> ScheduledTask:
    """
    Helper to create a ScheduledTask record for testing.

    Args:
        db_session: Database session
        task_type: Type of task (e.g., TaskType.RANDOM_DM)
        target_id: Target Slack user/channel ID
        status: Task status (default: PENDING)
        error_message: Optional error message for failed tasks

    Returns:
        Created ScheduledTask instance
    """
    task = ScheduledTask(
        task_type=task_type,
        target_id=target_id,
        scheduled_at=datetime.now(),
        status=status,
        error_message=error_message
    )
    db_session.add(task)
    db_session.commit()
    return task


def verify_user_timestamp_updated(
    db_session: Session,
    user_id: str,
    after: datetime
) -> bool:
    """
    Verify that a user's last_proactive_dm_at timestamp was updated after a given time.

    Args:
        db_session: Database session
        user_id: Slack user ID to check
        after: Timestamp to compare against

    Returns:
        True if timestamp exists and is after the given time
    """
    user = db_session.query(TeamMember).filter_by(slack_user_id=user_id).first()
    if not user or not user.last_proactive_dm_at:
        return False
    return user.last_proactive_dm_at > after


def get_never_contacted_users(db_session: Session) -> list[TeamMember]:
    """
    Get all active, non-bot users who have never been sent a proactive DM.

    Args:
        db_session: Database session

    Returns:
        List of TeamMember instances with last_proactive_dm_at = None
    """
    team_member_repo = TeamMemberRepository(db_session)
    return team_member_repo.get_never_contacted_users()


def reset_all_dm_timestamps(db_session: Session) -> None:
    """
    Reset all users' last_proactive_dm_at timestamps to None.

    Useful for testing scenarios starting from a clean state.

    Args:
        db_session: Database session
    """
    db_session.query(TeamMember).update({"last_proactive_dm_at": None})
    db_session.commit()
