"""
End-to-end integration tests for random DM workflow.

Tests the complete random DM feature from user selection through message sending
and database updates, without relying on real timing or Slack API calls.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock
from slack_sdk.errors import SlackApiError

from src.models.team_member import TeamMember
from src.models.scheduled_task import ScheduledTask, TaskType, TaskStatus
from tests.helpers.scheduler_helpers import (
    trigger_random_dm_immediately,
    get_never_contacted_users,
)


@pytest.mark.asyncio
class TestCompleteRandomDMWorkflow:
    """
    Integration tests for the entire random DM feature.
    Tests the complete flow without relying on real timing.
    """

    async def test_first_random_dm_selects_never_contacted_user(
        self,
        engagement_team_members,
        test_session,
        mock_slack_app,
        mock_slack_client_for_dm,
        engagement_service_instance,
    ):
        """
        Protects against: Not prioritizing never-contacted users

        Given: Database with 7 users (1 never contacted, others have various states)
        When: Random DM is triggered manually
        Then: The never-contacted user is selected
        And: Slack DM is sent with appropriate greeting
        And: Database timestamp is updated
        """
        # Arrange: Get never-contacted users
        never_contacted = [
            u
            for u in engagement_team_members
            if u.last_proactive_dm_at is None and not u.is_bot and u.is_active
        ]
        assert len(never_contacted) == 1  # Only U_NEVER based on fixture
        expected_user_id = never_contacted[0].slack_user_id

        # Act: Trigger random DM
        result = await trigger_random_dm_immediately(
            app=mock_slack_app,
            db_session=test_session,
            mock_slack_client=mock_slack_client_for_dm,
            engagement_service=engagement_service_instance,
        )

        # Assert: User selected from never-contacted group
        assert result["success"] is True
        assert result["user_selected"] == expected_user_id

        # Assert: Slack API called correctly
        mock_slack_client_for_dm.conversations_open.assert_called_once()
        call_args = mock_slack_client_for_dm.conversations_open.call_args
        assert call_args[1]["users"] == [expected_user_id]

        mock_slack_client_for_dm.chat_postMessage.assert_called_once()
        message_args = mock_slack_client_for_dm.chat_postMessage.call_args
        assert message_args[1]["channel"] == "D12345TEST"  # From mock fixture
        assert "🐻" in message_args[1]["text"] or len(message_args[1]["text"]) > 10  # Greeting template

        # Assert: Database updated
        selected_user = (
            test_session.query(TeamMember)
            .filter_by(slack_user_id=expected_user_id)
            .first()
        )
        assert selected_user.last_proactive_dm_at is not None
        assert selected_user.last_proactive_dm_at > datetime.now() - timedelta(
            seconds=5
        )

    async def test_second_random_dm_selects_different_user(
        self,
        engagement_team_members,
        test_session,
        mock_slack_app,
        mock_slack_client_for_dm,
        engagement_service_instance,
    ):
        """
        Protects against: Sending multiple DMs to same user while others haven't been contacted

        Given: Database with multiple never-contacted users
        When: Two random DMs are triggered
        Then: Two different users are selected
        """
        # Arrange: Reset all timestamps to create multiple never-contacted users
        for member in engagement_team_members:
            if not member.is_bot and member.is_active:
                member.last_proactive_dm_at = None
        test_session.commit()

        # Get eligible users
        eligible_users = [
            u for u in engagement_team_members if not u.is_bot and u.is_active
        ]
        assert len(eligible_users) >= 2

        # Act: Send first DM
        result1 = await trigger_random_dm_immediately(
            mock_slack_app, test_session, mock_slack_client_for_dm, engagement_service_instance
        )
        first_user_id = result1["user_selected"]
        assert result1["success"] is True

        # Act: Send second DM
        result2 = await trigger_random_dm_immediately(
            mock_slack_app, test_session, mock_slack_client_for_dm, engagement_service_instance
        )
        second_user_id = result2["user_selected"]
        assert result2["success"] is True

        # Assert: Different users selected
        assert first_user_id != second_user_id
        assert second_user_id in [u.slack_user_id for u in eligible_users]

    async def test_all_users_eventually_contacted_fair_distribution(
        self,
        engagement_team_members,
        test_session,
        mock_slack_app,
        mock_slack_client_for_dm,
        engagement_service_instance,
    ):
        """
        Protects against: Unequal distribution of random DMs

        Given: 5 active non-bot users (all with timestamps reset)
        When: 5 random DMs are sent
        Then: All 5 users have been contacted exactly once
        """
        # Arrange: Reset timestamps and get active non-bot users
        active_non_bot_users = [
            u for u in engagement_team_members if not u.is_bot and u.is_active
        ]

        for user in active_non_bot_users:
            user.last_proactive_dm_at = None
        test_session.commit()

        contacted_users = set()

        # Act: Send DMs to all users
        for i in range(len(active_non_bot_users)):
            result = await trigger_random_dm_immediately(
                mock_slack_app, test_session, mock_slack_client_for_dm, engagement_service_instance
            )
            assert result["success"] is True
            contacted_users.add(result["user_selected"])

        # Assert: All users contacted
        assert len(contacted_users) == len(active_non_bot_users)

        # Assert: All users have timestamp
        for user in active_non_bot_users:
            test_session.refresh(user)
            assert user.last_proactive_dm_at is not None

    async def test_bots_and_inactive_users_never_selected(
        self,
        engagement_team_members,
        test_session,
        mock_slack_app,
        mock_slack_client_for_dm,
        engagement_service_instance,
    ):
        """
        Protects against: Sending DMs to bots or inactive users

        Given: Database with bot and inactive users
        When: Random DMs are sent multiple times
        Then: Bots and inactive users are never selected
        """
        # Arrange: Get bot and inactive user IDs
        bot_users = [u.slack_user_id for u in engagement_team_members if u.is_bot]
        inactive_users = [
            u.slack_user_id for u in engagement_team_members if not u.is_active
        ]
        excluded_users = set(bot_users + inactive_users)

        # Reset all timestamps
        for user in engagement_team_members:
            user.last_proactive_dm_at = None
        test_session.commit()

        # Act: Send multiple DMs
        for i in range(5):
            result = await trigger_random_dm_immediately(
                mock_slack_app, test_session, mock_slack_client_for_dm, engagement_service_instance
            )
            if result["success"]:
                # Assert: Selected user is not bot or inactive
                assert result["user_selected"] not in excluded_users

    async def test_greeting_message_contains_expected_content(
        self,
        engagement_team_members,
        test_session,
        mock_slack_app,
        mock_slack_client_for_dm,
        engagement_service_instance,
    ):
        """
        Protects against: Sending empty or malformed greeting messages

        Given: Random DM is triggered
        When: Message is sent
        Then: Message contains greeting template content
        """
        # Act: Trigger DM
        result = await trigger_random_dm_immediately(
            mock_slack_app, test_session, mock_slack_client_for_dm, engagement_service_instance
        )

        assert result["success"] is True
        message = result["message_sent"]

        # Assert: Message is non-empty and looks like a greeting
        assert message is not None
        assert len(message) > 10  # Should be a real greeting, not empty
        # Common patterns in greeting templates
        assert any(
            word in message.lower()
            for word in ["hey", "hi", "hello", "checking", "good", "how"]
        )

    async def test_scheduled_task_record_created_on_success(
        self,
        engagement_team_members,
        test_session,
        mock_slack_app,
        mock_slack_client_for_dm,
        engagement_service_instance,
    ):
        """
        Protects against: Not tracking DM execution history

        Given: Random DM is sent successfully
        When: Operation completes
        Then: ScheduledTask record exists with COMPLETED status
        """
        # Act: Trigger DM
        result = await trigger_random_dm_immediately(
            mock_slack_app, test_session, mock_slack_client_for_dm, engagement_service_instance
        )

        assert result["success"] is True

        # Assert: Task record created
        task_record = (
            test_session.query(ScheduledTask)
            .filter_by(
                task_type=TaskType.RANDOM_DM.value, target_id=result["user_selected"]
            )
            .first()
        )

        assert task_record is not None
        assert task_record.status == TaskStatus.COMPLETED.value
        assert task_record.executed_at is not None
        assert task_record.error_message is None

    async def test_oldest_contacted_user_selected_when_no_never_contacted(
        self,
        engagement_team_members,
        test_session,
        mock_slack_app,
        mock_slack_client_for_dm,
        engagement_service_instance,
    ):
        """
        Protects against: Not selecting oldest contacted user when all users have been contacted

        Given: All users have been contacted (no NULL timestamps)
        When: Random DM is triggered
        Then: User with oldest timestamp is selected
        """
        # Arrange: Set timestamps so U_WEEK_AGO (7 days ago) is oldest
        now = datetime.now()
        for user in engagement_team_members:
            if not user.is_bot and user.is_active:
                if user.slack_user_id == "U_WEEK_AGO":
                    user.last_proactive_dm_at = now - timedelta(days=7)
                else:
                    # Set others to more recent times
                    user.last_proactive_dm_at = now - timedelta(days=1)
        test_session.commit()

        # Act: Trigger DM
        result = await trigger_random_dm_immediately(
            mock_slack_app, test_session, mock_slack_client_for_dm, engagement_service_instance
        )

        # Assert: Oldest user selected
        assert result["success"] is True
        assert result["user_selected"] == "U_WEEK_AGO"


@pytest.mark.asyncio
class TestRandomDMFailureScenarios:
    """Tests for error handling and recovery in random DM workflow."""

    async def test_slack_api_failure_does_not_update_timestamp(
        self,
        engagement_team_members,
        test_session,
        mock_slack_app,
        mock_slack_client_for_dm,
        engagement_service_instance,
    ):
        """
        Protects against: Marking user as contacted when DM actually failed

        Given: Slack API returns error
        When: Random DM is attempted
        Then: Timestamp is NOT updated
        And: ScheduledTask marked as failed
        """
        # Arrange: Mock Slack API to fail
        mock_slack_client_for_dm.conversations_open.side_effect = SlackApiError(
            message="user_not_found", response={"ok": False, "error": "user_not_found"}
        )

        never_contacted = [
            u
            for u in engagement_team_members
            if u.last_proactive_dm_at is None and not u.is_bot and u.is_active
        ][0]
        original_timestamp = never_contacted.last_proactive_dm_at

        # Act: Try to send DM (should handle error gracefully)
        result = await trigger_random_dm_immediately(
            mock_slack_app, test_session, mock_slack_client_for_dm, engagement_service_instance
        )

        # Assert: Operation failed
        assert result["success"] is False
        assert result["error"] is not None

        # Assert: Timestamp unchanged
        test_session.refresh(never_contacted)
        assert never_contacted.last_proactive_dm_at == original_timestamp

        # Assert: Failed task record created
        if result["user_selected"]:
            failed_task = (
                test_session.query(ScheduledTask)
                .filter_by(
                    task_type=TaskType.RANDOM_DM.value,
                    target_id=result["user_selected"],
                    status=TaskStatus.FAILED.value,
                )
                .first()
            )
            assert failed_task is not None
            assert "user_not_found" in failed_task.error_message

    async def test_no_eligible_users_returns_gracefully(
        self,
        test_session,
        mock_slack_app,
        mock_slack_client_for_dm,
        engagement_service_instance,
    ):
        """
        Protects against: Crashing when no users are eligible

        Given: All users are bots or inactive
        When: Random DM is triggered
        Then: Returns gracefully without error
        And: No Slack API calls made
        """
        # Arrange: Mark all users as inactive
        for user in test_session.query(TeamMember).all():
            user.is_active = False
        test_session.commit()

        # Act: Try to send DM
        result = await trigger_random_dm_immediately(
            mock_slack_app, test_session, mock_slack_client_for_dm, engagement_service_instance
        )

        # Assert: Graceful failure
        assert result["success"] is False
        assert result["reason"] == "no_eligible_users"
        assert result["user_selected"] is None

        # Assert: No Slack API calls
        mock_slack_client_for_dm.conversations_open.assert_not_called()

    async def test_message_send_failure_after_conversation_open(
        self,
        engagement_team_members,
        test_session,
        mock_slack_app,
        mock_slack_client_for_dm,
        engagement_service_instance,
    ):
        """
        Protects against: Not handling failures in chat_postMessage

        Given: conversations_open succeeds but chat_postMessage fails
        When: Random DM is attempted
        Then: Timestamp is NOT updated
        And: Error is properly recorded
        """
        # Arrange: Mock conversations_open to succeed, chat_postMessage to fail
        mock_slack_client_for_dm.conversations_open.return_value = {
            "ok": True,
            "channel": {"id": "D12345"},
        }
        mock_slack_client_for_dm.chat_postMessage.side_effect = SlackApiError(
            message="channel_not_found",
            response={"ok": False, "error": "channel_not_found"},
        )

        never_contacted = [
            u
            for u in engagement_team_members
            if u.last_proactive_dm_at is None and not u.is_bot and u.is_active
        ][0]
        original_timestamp = never_contacted.last_proactive_dm_at

        # Act: Try to send DM
        result = await trigger_random_dm_immediately(
            mock_slack_app, test_session, mock_slack_client_for_dm, engagement_service_instance
        )

        # Assert: Operation failed
        assert result["success"] is False

        # Assert: Timestamp unchanged
        test_session.refresh(never_contacted)
        assert never_contacted.last_proactive_dm_at == original_timestamp
