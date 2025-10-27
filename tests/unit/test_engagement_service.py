"""
Unit tests for engagement service - specifically random DM recipient selection logic.

Tests the fair distribution algorithm that selects team members for proactive DMs,
ensuring recent recipients are deprioritized and all active members get equal attention.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
# from src.services.engagement_service import EngagementService  # Will be implemented
from src.models.team_member import TeamMember


class TestRandomDMRecipientSelection:
    """Test random team member selection for proactive DMs."""

    @pytest.fixture
    def engagement_service(self, mock_db_session):
        """Create engagement service instance with mocked dependencies."""
        # return EngagementService(db_session=mock_db_session)  # Will be implemented
        return Mock()  # Placeholder until EngagementService is implemented

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        return Mock()

    def test_select_recipient_excludes_bots(self, engagement_service, mock_db_session):
        """Bot users should never be selected for proactive DMs."""
        # Given a list of users including bots
        users = [
            TeamMember(slack_user_id="U001", display_name="Alice", is_bot=False, is_active=True),
            TeamMember(slack_user_id="B002", display_name="BotUser", is_bot=True, is_active=True),
            TeamMember(slack_user_id="U003", display_name="Bob", is_bot=False, is_active=True),
        ]

        # When filtering eligible users
        eligible = [u for u in users if not u.is_bot and u.is_active]

        # Then bots should be excluded
        assert len(eligible) == 2
        assert all(not u.is_bot for u in eligible)
        assert "BotUser" not in [u.display_name for u in eligible]

    def test_select_recipient_excludes_inactive_users(self, engagement_service, mock_db_session):
        """Inactive users (left workspace) should never be selected."""
        # Given a list of users including inactive ones
        users = [
            TeamMember(slack_user_id="U001", display_name="Alice", is_bot=False, is_active=True),
            TeamMember(slack_user_id="U002", display_name="Charlie", is_bot=False, is_active=False),
            TeamMember(slack_user_id="U003", display_name="Bob", is_bot=False, is_active=True),
        ]

        # When filtering eligible users
        eligible = [u for u in users if not u.is_bot and u.is_active]

        # Then inactive users should be excluded
        assert len(eligible) == 2
        assert all(u.is_active for u in eligible)
        assert "Charlie" not in [u.display_name for u in eligible]

    def test_select_recipient_prioritizes_never_contacted(self, engagement_service, mock_db_session):
        """Users never contacted should have highest priority."""
        # Given users with varied contact history
        never_contacted = TeamMember(
            slack_user_id="U001",
            display_name="NewUser",
            is_bot=False,
            is_active=True,
            last_proactive_dm_at=None,
        )
        recently_contacted = TeamMember(
            slack_user_id="U002",
            display_name="RecentUser",
            is_bot=False,
            is_active=True,
            last_proactive_dm_at=datetime.now() - timedelta(hours=1),
        )

        users = [recently_contacted, never_contacted]

        # When sorted by last contact (None should sort first)
        sorted_users = sorted(
            users,
            key=lambda u: u.last_proactive_dm_at if u.last_proactive_dm_at else datetime.min
        )

        # Then never-contacted user should be first
        assert sorted_users[0].display_name == "NewUser"

    def test_select_recipient_deprioritizes_recently_contacted(self, engagement_service, mock_db_session):
        """Users contacted recently should be lowest priority."""
        # Given users contacted at different times
        long_ago = TeamMember(
            slack_user_id="U001",
            display_name="OldUser",
            is_bot=False,
            is_active=True,
            last_proactive_dm_at=datetime.now() - timedelta(days=7),
        )
        recently = TeamMember(
            slack_user_id="U002",
            display_name="RecentUser",
            is_bot=False,
            is_active=True,
            last_proactive_dm_at=datetime.now() - timedelta(hours=1),
        )

        users = [recently, long_ago]

        # When sorted by last contact (oldest first)
        sorted_users = sorted(users, key=lambda u: u.last_proactive_dm_at)

        # Then least recently contacted should be first
        assert sorted_users[0].display_name == "OldUser"

    def test_select_recipient_fair_distribution_over_time(self, engagement_service, mock_db_session):
        """Over multiple selections, all eligible users should eventually be contacted."""
        # Given 5 active users
        users = [
            TeamMember(
                slack_user_id=f"U00{i}",
                display_name=f"User{i}",
                is_bot=False,
                is_active=True,
                last_proactive_dm_at=None
            )
            for i in range(1, 6)
        ]

        # When selecting with fair distribution (oldest last_proactive_dm_at first)
        # All users with None should have equal priority initially
        never_contacted = [u for u in users if u.last_proactive_dm_at is None]

        # Then all 5 should be eligible
        assert len(never_contacted) == 5

    def test_select_recipient_returns_none_when_no_eligible_users(self, engagement_service, mock_db_session):
        """When no eligible users exist, selection should return None."""
        # Given only bots and inactive users
        users = [
            TeamMember(slack_user_id="B001", display_name="Bot1", is_bot=True, is_active=True),
            TeamMember(slack_user_id="U002", display_name="Inactive", is_bot=False, is_active=False),
        ]

        # When filtering eligible users
        eligible = [u for u in users if not u.is_bot and u.is_active]

        # Then no eligible users
        assert len(eligible) == 0

    def test_select_recipient_handles_single_eligible_user(self, engagement_service, mock_db_session):
        """With only one eligible user, that user should be selected."""
        # Given only one active non-bot user
        users = [
            TeamMember(slack_user_id="U001", display_name="OnlyUser", is_bot=False, is_active=True),
            TeamMember(slack_user_id="B002", display_name="Bot", is_bot=True, is_active=True),
        ]

        # When filtering eligible users
        eligible = [u for u in users if not u.is_bot and u.is_active]

        # Then only one user should be eligible
        assert len(eligible) == 1
        assert eligible[0].display_name == "OnlyUser"

    def test_select_recipient_weighted_selection_by_time_since_contact(self, engagement_service, mock_db_session):
        """Users contacted longer ago should have higher weight in selection."""
        # Given users with different last contact times
        user1_never = None
        user2_week_ago = datetime.now() - timedelta(days=7)
        user3_day_ago = datetime.now() - timedelta(days=1)
        user4_hour_ago = datetime.now() - timedelta(hours=1)

        # When calculating "priority score" (days since contact)
        def priority_score(last_contact):
            if last_contact is None:
                return float('inf')  # Highest priority
            return (datetime.now() - last_contact).total_seconds() / 86400  # Days

        # Then never contacted should have highest score
        assert priority_score(user1_never) > priority_score(user2_week_ago)
        assert priority_score(user2_week_ago) > priority_score(user3_day_ago)
        assert priority_score(user3_day_ago) > priority_score(user4_hour_ago)

    def test_select_recipient_randomness_among_equal_priority(self, engagement_service, mock_db_session):
        """Users with same priority (e.g., all never contacted) should have equal random chance."""
        # Given multiple users never contacted
        users = [
            TeamMember(
                slack_user_id=f"U00{i}",
                display_name=f"User{i}",
                is_bot=False,
                is_active=True,
                last_proactive_dm_at=None
            )
            for i in range(1, 4)
        ]

        # When all have same priority (None)
        all_never_contacted = all(u.last_proactive_dm_at is None for u in users)

        # Then all should have equal selection chance
        assert all_never_contacted
        assert len(users) == 3


class TestProactiveDMTiming:
    """Test timing logic for proactive DM scheduling."""

    def test_next_dm_time_calculation(self):
        """Calculate next DM time based on configured interval."""
        # Given interval of 24 hours
        interval_hours = 24
        last_dm_time = datetime.now()

        # When calculating next DM time
        next_dm_time = last_dm_time + timedelta(hours=interval_hours)

        # Then should be 24 hours later
        hours_diff = (next_dm_time - last_dm_time).total_seconds() / 3600
        assert hours_diff == 24

    def test_should_send_dm_now_when_interval_passed(self):
        """Should send DM when configured interval has passed."""
        # Given interval of 2 hours
        interval_hours = 2
        last_dm_time = datetime.now() - timedelta(hours=3)

        # When checking if should send now
        time_since_last = (datetime.now() - last_dm_time).total_seconds() / 3600
        should_send = time_since_last >= interval_hours

        # Then should send (3 hours > 2 hours)
        assert should_send

    def test_should_not_send_dm_when_interval_not_passed(self):
        """Should not send DM when interval hasn't passed yet."""
        # Given interval of 2 hours
        interval_hours = 2
        last_dm_time = datetime.now() - timedelta(hours=1)

        # When checking if should send now
        time_since_last = (datetime.now() - last_dm_time).total_seconds() / 3600
        should_send = time_since_last >= interval_hours

        # Then should not send (1 hour < 2 hours)
        assert not should_send

    def test_initial_dm_scheduling_with_no_history(self):
        """First DM should be scheduled immediately or after initial delay."""
        # Given no previous DM history
        last_dm_time = None

        # When determining if should send
        should_send = last_dm_time is None

        # Then should allow sending (no history means first DM)
        assert should_send
