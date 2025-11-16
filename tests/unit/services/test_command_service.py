"""
Unit tests for CommandService.

Tests the business logic layer independent of Slack/MCP protocols.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from src.services.command_service import CommandService, PermissionDeniedError


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    return Mock()


@pytest.fixture
def mock_slack_client():
    """Mock Slack WebClient (synchronous client)."""
    client = Mock()
    client.chat_postMessage = Mock()
    return client


@pytest.fixture
def mock_admin_user():
    """Mock admin user."""
    user = Mock()
    user.id = "admin_id"
    user.slack_user_id = "U_ADMIN"
    user.display_name = "Admin User"
    user.is_admin = True
    user.total_messages_sent = 10
    return user


@pytest.fixture
def mock_regular_user():
    """Mock regular (non-admin) user."""
    user = Mock()
    user.id = "user_id"
    user.slack_user_id = "U_USER"
    user.display_name = "Regular User"
    user.is_admin = False
    user.total_messages_sent = 5
    return user


@pytest.fixture
def command_service(mock_db_session, mock_slack_client):
    """Create CommandService instance with mocked dependencies."""
    with patch('src.services.command_service.ConfigurationRepository'):
        with patch('src.services.command_service.TeamMemberRepository'):
            service = CommandService(mock_db_session, mock_slack_client)
            return service


class TestPostMessage:
    """Tests for post_message method."""

    @pytest.mark.asyncio
    async def test_post_message_success(self, command_service, mock_regular_user, mock_slack_client):
        """Test successful message posting."""
        # Setup
        command_service.team_member_repo.get_by_slack_user_id = Mock(return_value=mock_regular_user)
        mock_slack_client.chat_postMessage.return_value = {"ok": True}

        # Execute
        result = await command_service.post_message(
            message="Test message",
            channel="general",
            user_id="U_USER"
        )

        # Assert
        assert result["success"] is True
        assert result["channel"] == "general"
        mock_slack_client.chat_postMessage.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_message_as_lukas_without_user_id(self, command_service, mock_slack_client):
        """Test posting as Lukas the Bear (bot) without user attribution."""
        # Setup
        mock_slack_client.chat_postMessage.return_value = {"ok": True}

        # Execute - no user_id provided
        result = await command_service.post_message(
            message="Test announcement from Lukas",
            channel="general"
        )

        # Assert
        assert result["success"] is True
        assert result["channel"] == "general"

        # Verify message was posted without attribution
        call_args = mock_slack_client.chat_postMessage.call_args
        assert call_args[1]["channel"] == "general"
        # Message should be posted as-is, without attribution
        assert call_args[1]["text"] == "Test announcement from Lukas"
        assert "Posted by" not in call_args[1]["text"]
        mock_slack_client.chat_postMessage.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_message_user_not_found(self, command_service, mock_slack_client):
        """Test posting with non-existent user (logs warning but still posts)."""
        # Setup
        command_service.team_member_repo.get_by_slack_user_id = Mock(return_value=None)
        mock_slack_client.chat_postMessage.return_value = {"ok": True}

        # Execute - should still succeed even if user not found
        result = await command_service.post_message(
            message="Test",
            channel="general",
            user_id="U_UNKNOWN"
        )

        # Assert - should succeed (user_id is only for logging now)
        assert result["success"] is True
        assert "general" == result["channel"]


class TestCreateReminder:
    """Tests for create_reminder method."""

    @pytest.mark.asyncio
    async def test_create_reminder_duration_based(self, command_service, mock_regular_user, mock_db_session):
        """Test creating a reminder with duration (e.g., '30 minutes')."""
        # Setup
        command_service.team_member_repo.get_by_slack_id = Mock(return_value=mock_regular_user)

        with patch('src.services.command_service.scheduler') as mock_scheduler:
            # Mock add_job to return a job object and avoid serialization
            mock_job = Mock()
            mock_job.id = "job_123"
            mock_scheduler.add_job.return_value = mock_job

            # Execute
            result = await command_service.create_reminder(
                task="check the build",
                when="30 minutes",
                user_id="U_USER"
            )

            # Assert
            assert result["success"] is True
            assert result["task"] == "check the build"
            assert "30 minutes" in result["when_description"]
            assert result["scheduled_at"] is not None
            mock_scheduler.add_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_reminder_time_based(self, command_service, mock_regular_user, mock_db_session):
        """Test creating a reminder with specific time (e.g., '3pm')."""
        # Setup
        command_service.team_member_repo.get_by_slack_id = Mock(return_value=mock_regular_user)

        with patch('src.services.command_service.scheduler') as mock_scheduler:
            # Mock add_job to return a job object and avoid serialization
            mock_job = Mock()
            mock_job.id = "job_456"
            mock_scheduler.add_job.return_value = mock_job

            # Execute
            result = await command_service.create_reminder(
                task="review PRs",
                when="3pm",
                user_id="U_USER"
            )

            # Assert
            assert result["success"] is True
            assert result["task"] == "review PRs"
            assert "3pm" in result["when_description"]
            mock_scheduler.add_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_reminder_invalid_format(self, command_service, mock_regular_user):
        """Test creating a reminder with invalid time format."""
        # Setup
        command_service.team_member_repo.get_by_slack_id = Mock(return_value=mock_regular_user)

        # Execute
        result = await command_service.create_reminder(
            task="check build",
            when="invalid time format",
            user_id="U_USER"
        )

        # Assert
        assert result["success"] is False
        assert "Invalid time format" in result["error"]


class TestGetInfo:
    """Tests for get_info method."""

    @pytest.mark.asyncio
    async def test_get_team_info(self, command_service, mock_admin_user, mock_regular_user, mock_db_session):
        """Test getting team member information."""
        # Setup
        mock_db_session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [
            mock_admin_user,
            mock_regular_user
        ]

        # Execute
        result = await command_service.get_info(info_type="team")

        # Assert
        assert result["success"] is True
        assert result["info_type"] == "team"
        assert result["data"]["total_members"] == 2
        assert result["data"]["admin_count"] == 1
        assert "Team Member Directory" in result["formatted"]

    @pytest.mark.asyncio
    async def test_get_bot_status(self, command_service):
        """Test getting bot status information."""
        # Setup
        command_service.config_repo.get_all_configs = Mock(return_value=[
            Mock(key="random_dm_interval_hours", value="24"),
            Mock(key="thread_response_probability", value="0.20"),
            Mock(key="image_post_interval_days", value="7"),
        ])

        with patch('src.services.command_service.scheduler') as mock_scheduler:
            mock_scheduler.get_jobs.return_value = []

            # Execute
            result = await command_service.get_info(info_type="status")

            # Assert
            assert result["success"] is True
            assert result["info_type"] == "status"
            assert "status" in result["data"]
            assert "Lukas the Bear Status" in result["formatted"]

    @pytest.mark.asyncio
    async def test_get_engagement_stats(self, command_service, mock_db_session):
        """Test getting engagement statistics."""
        # Setup
        mock_db_session.query.return_value.scalar.return_value = 100  # total events
        mock_db_session.query.return_value.filter_by.return_value.scalar.return_value = 50  # engaged events

        # Execute
        result = await command_service.get_info(info_type="stats")

        # Assert
        assert result["success"] is True
        assert result["info_type"] == "stats"
        assert "thread_engagement" in result["data"]
        assert "Engagement Statistics" in result["formatted"]


class TestUpdateConfig:
    """Tests for update_config method (admin only)."""

    @pytest.mark.asyncio
    async def test_update_config_as_admin(self, command_service, mock_admin_user, mock_db_session):
        """Test updating configuration as admin."""
        # Setup
        command_service.team_member_repo.get_by_slack_user_id = Mock(return_value=mock_admin_user)
        command_service.config_repo.update_config = Mock()

        # Execute
        result = await command_service.update_config(
            setting="dm_interval",
            value="48 hours",
            user_id="U_ADMIN"
        )

        # Assert
        assert result["success"] is True
        assert result["setting"] == "dm_interval"
        command_service.config_repo.update_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_config_as_non_admin(self, command_service, mock_regular_user):
        """Test updating configuration as non-admin (should fail)."""
        # Setup
        command_service.team_member_repo.get_by_slack_id = Mock(return_value=mock_regular_user)

        # Execute
        result = await command_service.update_config(
            setting="dm_interval",
            value="48 hours",
            user_id="U_USER"
        )

        # Assert - should return error instead of raising exception
        assert result["success"] is False
        assert result["error"] == "Permission denied"
        assert "admin privileges" in result["message"]

    @pytest.mark.asyncio
    async def test_update_config_invalid_value(self, command_service, mock_admin_user):
        """Test updating configuration with invalid value."""
        # Setup
        command_service.team_member_repo.get_by_slack_user_id = Mock(return_value=mock_admin_user)

        # Execute
        result = await command_service.update_config(
            setting="thread_probability",
            value="1.5",  # Invalid: must be between 0.0 and 1.0
            user_id="U_ADMIN"
        )

        # Assert
        assert result["success"] is False
        assert ("out of range" in result["message"] or "between 0.0 and 1.0" in result["message"])


class TestGenerateImage:
    """Tests for generate_image method (admin only)."""

    @pytest.mark.asyncio
    async def test_generate_image_as_admin(self, command_service, mock_admin_user):
        """Test generating image as admin."""
        # Setup
        command_service.team_member_repo.get_by_slack_user_id = Mock(return_value=mock_admin_user)

        mock_image_result = Mock()
        mock_image_result.status = "posted"
        mock_image_result.id = "img_123"

        # Mock the image_service module that gets imported inside the method
        mock_img_service = Mock()
        mock_img_service.generate_and_post = AsyncMock(return_value=mock_image_result)

        with patch('src.services.image_service.image_service', mock_img_service):
            # Execute
            result = await command_service.generate_image(
                theme="halloween",
                channel="general",
                user_id="U_ADMIN"
            )

            # Assert
            assert result["success"] is True
            assert result["image_id"] == "img_123"

    @pytest.mark.asyncio
    async def test_generate_image_as_non_admin(self, command_service, mock_regular_user):
        """Test generating image as non-admin (should fail)."""
        # Setup
        command_service.team_member_repo.get_by_slack_id = Mock(return_value=mock_regular_user)

        # Execute
        result = await command_service.generate_image(
            theme="halloween",
            channel="general",
            user_id="U_USER"
        )

        # Assert - should return error instead of raising exception
        assert result["success"] is False
        assert result["error"] == "Permission denied"
        assert "admin privileges" in result["message"]


class TestHelperMethods:
    """Tests for helper/parsing methods."""

    def test_parse_duration_to_minutes(self, command_service):
        """Test parsing duration strings to minutes."""
        assert command_service._parse_duration_to_minutes("30 minutes") == 30
        assert command_service._parse_duration_to_minutes("2 hours") == 120
        assert command_service._parse_duration_to_minutes("1 hr") == 60
        assert command_service._parse_duration_to_minutes("invalid") is None

    def test_parse_hours_from_string(self, command_service):
        """Test parsing hours from configuration strings."""
        assert command_service._parse_hours_from_string("24 hours") == 24
        assert command_service._parse_hours_from_string("12 hrs") == 12
        assert command_service._parse_hours_from_string("48") == 48
        assert command_service._parse_hours_from_string("invalid") is None

    def test_parse_days_from_string(self, command_service):
        """Test parsing days from configuration strings."""
        assert command_service._parse_days_from_string("7 days") == 7
        assert command_service._parse_days_from_string("14 day") == 14
        assert command_service._parse_days_from_string("30") == 30
        assert command_service._parse_days_from_string("invalid") is None
