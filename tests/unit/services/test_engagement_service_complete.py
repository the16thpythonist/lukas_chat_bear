"""
Complete unit tests for EngagementService with real database integration.

Tests the actual EngagementService class methods with mocked external
dependencies and real database operations.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
from freezegun import freeze_time

from src.services.engagement_service import EngagementService
from src.models.team_member import TeamMember


class TestEngagementServiceDatabaseIntegration:
    """Test EngagementService methods with real database operations."""

    def test_select_dm_recipient_with_real_db(
        self, engagement_service_instance, engagement_team_members
    ):
        """Test selecting DM recipient from real database with varied users."""
        # Given engagement_team_members fixture (7 users in DB)
        # When selecting recipient
        selected = engagement_service_instance.select_dm_recipient()

        # Then should return a TeamMember
        assert selected is not None
        assert isinstance(selected, TeamMember)

        # Should be either never-contacted or oldest-contacted user
        assert selected.slack_user_id in ["U_NEVER", "U_WEEK_AGO"]

        # Should NOT be bot or inactive
        assert not selected.is_bot
        assert selected.is_active

    def test_select_dm_recipient_excludes_bots_from_db(
        self, engagement_service_instance, engagement_team_members
    ):
        """Bot users should never be selected from database."""
        # Given DB has bot user (B_BOT)
        # When selecting 10 times
        selections = [
            engagement_service_instance.select_dm_recipient()
            for _ in range(10)
        ]

        # Then no selection should be the bot
        bot_ids = [s.slack_user_id for s in selections if s]
        assert "B_BOT" not in bot_ids

    def test_select_dm_recipient_excludes_inactive_from_db(
        self, engagement_service_instance, engagement_team_members
    ):
        """Inactive users should never be selected from database."""
        # Given DB has inactive user (U_INACTIVE)
        # When selecting 10 times
        selections = [
            engagement_service_instance.select_dm_recipient()
            for _ in range(10)
        ]

        # Then no selection should be the inactive user
        inactive_ids = [s.slack_user_id for s in selections if s]
        assert "U_INACTIVE" not in inactive_ids

    def test_select_dm_recipient_returns_none_when_no_eligible(
        self, engagement_service_instance, test_session
    ):
        """Should return None when no eligible users exist."""
        # Given DB with only bots and inactive users
        test_session.query(TeamMember).delete()  # Clear existing
        test_session.add_all([
            TeamMember(
                slack_user_id="B001",
                display_name="Bot",
                is_bot=True,
                is_active=True
            ),
            TeamMember(
                slack_user_id="U002",
                display_name="Inactive",
                is_bot=False,
                is_active=False
            ),
        ])
        test_session.commit()

        # When selecting recipient
        selected = engagement_service_instance.select_dm_recipient()

        # Then should return None
        assert selected is None

    def test_update_last_proactive_dm_commits_to_db(
        self, engagement_service_instance, engagement_team_members, test_session
    ):
        """Updating last_proactive_dm_at should persist to database."""
        # Given a team member who was never contacted
        never_contacted = test_session.query(TeamMember).filter_by(
            slack_user_id="U_NEVER"
        ).first()
        assert never_contacted.last_proactive_dm_at is None

        # When updating last proactive DM timestamp
        engagement_service_instance.update_last_proactive_dm(never_contacted)

        # Then timestamp should be persisted
        test_session.refresh(never_contacted)
        assert never_contacted.last_proactive_dm_at is not None
        assert isinstance(never_contacted.last_proactive_dm_at, datetime)

        # Should be very recent (within last minute)
        time_diff = datetime.now() - never_contacted.last_proactive_dm_at
        assert time_diff.total_seconds() < 60

    def test_get_engagement_probability_from_config(
        self, engagement_service_instance, engagement_config
    ):
        """Should retrieve engagement probability from database config."""
        # Given engagement_config fixture (0.20 configured)
        # When getting engagement probability
        probability = engagement_service_instance.get_engagement_probability()

        # Then should return configured value
        assert probability == 0.20
        assert isinstance(probability, float)

    def test_get_active_hours_from_config(
        self, engagement_service_instance, engagement_config
    ):
        """Should retrieve active hours from database config."""
        # Given engagement_config fixture (8-18 configured)
        # When getting active hours
        start_hour, end_hour = engagement_service_instance.get_active_hours()

        # Then should return configured values
        assert start_hour == 8
        assert end_hour == 18

    def test_get_random_dm_interval_from_config(
        self, engagement_service_instance, engagement_config
    ):
        """Should retrieve random DM interval from database config."""
        # Given engagement_config fixture (24 hours configured)
        # When getting interval
        interval = engagement_service_instance.get_random_dm_interval_hours()

        # Then should return configured value
        assert interval == 24
        assert isinstance(interval, int)


class TestEngagementServiceBusinessLogic:
    """Test EngagementService business logic with various inputs."""

    @pytest.mark.parametrize("probability,random_val,expected", [
        (0.20, 0.10, True),   # random < probability → engage
        (0.20, 0.30, False),  # random >= probability → don't engage
        (0.50, 0.25, True),   # random < probability → engage
        (0.50, 0.75, False),  # random >= probability → don't engage
        (0.00, 0.00, False),  # 0% probability → never engage
        (1.00, 0.99, True),   # 100% probability → always engage
    ])
    def test_should_engage_with_various_probabilities(
        self, engagement_service_instance, probability, random_val, expected
    ):
        """Test engagement decision with various probability/random combinations."""
        # When making engagement decision with predetermined random value
        result = engagement_service_instance.should_engage(probability, random_val)

        # Then should match expected outcome
        assert result == expected

    def test_should_engage_raises_on_invalid_probability(
        self, engagement_service_instance
    ):
        """Should raise ValueError for probabilities outside 0.0-1.0 range."""
        # Given invalid probabilities
        invalid_probabilities = [-0.1, 1.5, 2.0, -1.0]

        # When/Then should raise ValueError
        for prob in invalid_probabilities:
            with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
                engagement_service_instance.should_engage(prob)

    @freeze_time("2025-01-15 10:00:00")  # Wednesday 10am
    @pytest.mark.parametrize("start,end,expected", [
        (8, 18, True),    # 10am within 8am-6pm → active
        (9, 17, True),    # 10am within 9am-5pm → active
        (11, 18, False),  # 10am before 11am start → inactive
        (8, 10, False),   # 10am at exact end boundary → inactive
        (None, None, True),  # No restriction → always active
    ])
    def test_is_within_active_hours_various_times(
        self, engagement_service_instance, start, end, expected
    ):
        """Test active hours check with various configurations."""
        # When checking if within active hours (frozen at 10am)
        result = engagement_service_instance.is_within_active_hours(
            start_hour=start,
            end_hour=end
        )

        # Then should match expected
        assert result == expected

    @pytest.mark.parametrize("message_count,threshold,expected", [
        (5, 10, False),   # 5 < 10 → not too active
        (15, 10, True),   # 15 >= 10 → too active
        (10, 10, True),   # 10 >= 10 → too active (boundary)
        (0, 10, False),   # 0 < 10 → not too active
    ])
    def test_is_thread_too_active_various_counts(
        self, engagement_service_instance, message_count, threshold, expected
    ):
        """Test thread activity check with various message counts."""
        # When checking if thread too active
        result = engagement_service_instance.is_thread_too_active(
            message_count=message_count,
            threshold=threshold
        )

        # Then should match expected
        assert result == expected

    def test_should_send_random_dm_now_first_time(
        self, engagement_service_instance
    ):
        """Should allow sending when no previous DM exists."""
        # When checking if should send (never sent before)
        result = engagement_service_instance.should_send_random_dm_now(last_dm_time=None)

        # Then should allow sending
        assert result is True

    def test_should_send_random_dm_now_after_interval(
        self, engagement_service_instance, engagement_config
    ):
        """Should allow sending when interval has passed."""
        # Given last DM was 25 hours ago (interval is 24h)
        last_dm = datetime.now() - timedelta(hours=25)

        # When checking if should send
        result = engagement_service_instance.should_send_random_dm_now(last_dm)

        # Then should allow sending
        assert result is True

    def test_should_send_random_dm_now_before_interval(
        self, engagement_service_instance, engagement_config
    ):
        """Should not allow sending when interval hasn't passed."""
        # Given last DM was 1 hour ago (interval is 24h)
        last_dm = datetime.now() - timedelta(hours=1)

        # When checking if should send
        result = engagement_service_instance.should_send_random_dm_now(last_dm)

        # Then should not allow sending
        assert result is False

    def test_select_engagement_type_distribution(
        self, engagement_service_instance
    ):
        """Engagement type should be ~70% text, ~30% reaction over many selections."""
        # When selecting engagement type 1000 times
        selections = [
            engagement_service_instance.select_engagement_type()
            for _ in range(1000)
        ]

        # Then distribution should be approximately 70/30
        text_count = selections.count('text')
        reaction_count = selections.count('reaction')

        text_percentage = text_count / 1000
        reaction_percentage = reaction_count / 1000

        # Allow 10% variance (60-80% text, 20-40% reaction)
        assert 0.60 <= text_percentage <= 0.80
        assert 0.20 <= reaction_percentage <= 0.40

    def test_select_emoji_reaction_returns_valid_emoji(
        self, engagement_service_instance
    ):
        """Selected emoji should be from bear-appropriate list."""
        # Given valid bear emojis
        valid_emojis = [
            'bear', 'honey_pot', 'paw_prints', 'deciduous_tree',
            'evergreen_tree', 'hugging_face', 'thinking_face',
            '+1', 'heart', 'tada', 'eyes', 'muscle'
        ]

        # When selecting emoji 20 times
        selections = [
            engagement_service_instance.select_emoji_reaction()
            for _ in range(20)
        ]

        # Then all selections should be valid
        for emoji in selections:
            assert emoji in valid_emojis

    def test_select_dm_recipient_fair_distribution_over_time(
        self, engagement_service_instance, engagement_team_members, test_session
    ):
        """Over multiple selections, should fairly distribute across users."""
        # Given 5 eligible users in DB
        # When selecting recipient 5 times and updating timestamps
        selected_ids = []
        for _ in range(5):
            recipient = engagement_service_instance.select_dm_recipient()
            if recipient:
                selected_ids.append(recipient.slack_user_id)
                # Update timestamp to simulate actual DM send
                engagement_service_instance.update_last_proactive_dm(recipient)
                test_session.refresh(recipient)

        # Then should have selected different users (fair distribution)
        unique_selections = len(set(selected_ids))
        assert unique_selections >= 3  # At least 3 different users

        # Never-contacted user should be selected first
        assert selected_ids[0] == "U_NEVER"

    def test_error_handling_when_config_missing(
        self, engagement_service_instance, test_session
    ):
        """Should use defaults when configuration is missing."""
        # Given DB with no configuration entries
        from src.models.config import Configuration
        test_session.query(Configuration).delete()
        test_session.commit()

        # When getting configuration values
        probability = engagement_service_instance.get_engagement_probability()
        interval = engagement_service_instance.get_random_dm_interval_hours()
        start, end = engagement_service_instance.get_active_hours()

        # Then should return sensible defaults
        assert probability == 0.20  # Default 20%
        assert interval == 24  # Default 24 hours
        assert start is None and end is None  # No restriction
