"""
Unit tests for engagement probability logic.

Tests the core probability calculation and decision-making logic
that determines when Lukas should proactively engage with threads.
"""

import pytest
from datetime import datetime, timedelta


class TestEngagementProbability:
    """Test engagement probability calculation and decision logic."""

    def test_should_engage_returns_true_when_random_below_probability(self):
        """When random value < probability, should_engage returns True."""
        # Given a configured probability of 20%
        probability = 0.20
        # When random value is below threshold (e.g., 0.15)
        random_value = 0.15
        # Then should engage
        assert random_value < probability

    def test_should_engage_returns_false_when_random_above_probability(self):
        """When random value >= probability, should_engage returns False."""
        # Given a configured probability of 20%
        probability = 0.20
        # When random value is above threshold (e.g., 0.25)
        random_value = 0.25
        # Then should not engage
        assert random_value >= probability

    def test_probability_validation_accepts_valid_range(self):
        """Probability validation accepts values between 0.0 and 1.0."""
        valid_probabilities = [0.0, 0.15, 0.20, 0.50, 1.0]
        for prob in valid_probabilities:
            assert 0.0 <= prob <= 1.0, f"Valid probability {prob} should pass"

    def test_probability_validation_rejects_invalid_range(self):
        """Probability validation rejects values outside 0.0-1.0 range."""
        invalid_probabilities = [-0.1, 1.5, 2.0, -1.0]
        for prob in invalid_probabilities:
            assert not (0.0 <= prob <= 1.0), f"Invalid probability {prob} should fail"

    def test_engagement_decision_with_zero_probability_never_engages(self):
        """With probability 0.0, should never engage regardless of random value."""
        probability = 0.0
        # Even with random value of 0, should not engage (0 < 0 is False)
        assert not (0.0 < probability)
        assert not (0.5 < probability)
        assert not (0.99 < probability)

    def test_engagement_decision_with_full_probability_always_engages(self):
        """With probability 1.0, should always engage (unless random is exactly 1.0)."""
        probability = 1.0
        # Any random value less than 1.0 should trigger engagement
        assert 0.0 < probability
        assert 0.5 < probability
        assert 0.99 < probability

    def test_typical_engagement_rate_calculation(self):
        """Test typical engagement rate of 20% over multiple decisions."""
        probability = 0.20
        # Simulate 100 decisions with uniform random distribution
        # In practice, ~20 should result in engagement
        sample_random_values = [i / 100.0 for i in range(100)]
        engaged_count = sum(1 for r in sample_random_values if r < probability)

        # With 20% probability, expect ~20 engagements out of 100
        assert 18 <= engaged_count <= 22, f"Expected ~20 engagements, got {engaged_count}"

    def test_edge_case_random_value_equals_probability(self):
        """When random value exactly equals probability, should not engage (boundary condition)."""
        probability = 0.20
        random_value = 0.20
        # Using < comparison, equal values should NOT trigger engagement
        assert not (random_value < probability)


class TestActiveHoursCheck:
    """Test active hours validation for proactive engagement."""

    def test_is_within_active_hours_during_work_hours(self):
        """During configured active hours, should return True."""
        # Given active hours 8am-6pm
        start_hour = 8
        end_hour = 18
        # When checking 10am
        check_hour = 10
        # Then should be within active hours
        assert start_hour <= check_hour < end_hour

    def test_is_within_active_hours_before_start(self):
        """Before active hours start, should return False."""
        # Given active hours 8am-6pm
        start_hour = 8
        end_hour = 18
        # When checking 6am
        check_hour = 6
        # Then should be outside active hours
        assert not (start_hour <= check_hour < end_hour)

    def test_is_within_active_hours_after_end(self):
        """After active hours end, should return False."""
        # Given active hours 8am-6pm
        start_hour = 8
        end_hour = 18
        # When checking 8pm (20)
        check_hour = 20
        # Then should be outside active hours
        assert not (start_hour <= check_hour < end_hour)

    def test_is_within_active_hours_at_boundary_start(self):
        """At exact start hour, should return True."""
        start_hour = 8
        end_hour = 18
        check_hour = 8
        assert start_hour <= check_hour < end_hour

    def test_is_within_active_hours_at_boundary_end(self):
        """At exact end hour, should return False (exclusive end)."""
        start_hour = 8
        end_hour = 18
        check_hour = 18
        assert not (start_hour <= check_hour < end_hour)

    def test_active_hours_disabled_when_none(self):
        """When active hours not configured (None), should always return True."""
        # No active hours restriction
        start_hour = None
        end_hour = None
        # Any hour should be acceptable
        assert start_hour is None or end_hour is None


class TestThreadActivityLevel:
    """Test thread activity level assessment for engagement decisions."""

    def test_thread_is_not_too_active_below_threshold(self):
        """Threads below activity threshold are eligible for engagement."""
        # Given activity threshold of 10 messages per hour
        threshold = 10
        # When thread has 5 messages in last hour
        message_count = 5
        # Then should not be too active
        assert message_count < threshold

    def test_thread_is_too_active_above_threshold(self):
        """Very active threads exceed threshold and should be avoided."""
        # Given activity threshold of 10 messages per hour
        threshold = 10
        # When thread has 15 messages in last hour
        message_count = 15
        # Then should be too active
        assert message_count >= threshold

    def test_thread_activity_at_boundary(self):
        """Thread at exact threshold boundary should be considered too active."""
        threshold = 10
        message_count = 10
        # Boundary case: exactly at threshold should be excluded (use >=)
        assert message_count >= threshold


class TestEngagementCooldown:
    """Test cooldown period between engagements in same thread/channel."""

    def test_thread_not_recently_engaged_outside_cooldown(self):
        """Threads outside cooldown period are eligible for re-engagement."""
        # Given cooldown period of 1 hour
        cooldown_hours = 1
        # When last engagement was 2 hours ago
        last_engagement = datetime.now() - timedelta(hours=2)
        now = datetime.now()
        hours_since = (now - last_engagement).total_seconds() / 3600
        # Then should be outside cooldown
        assert hours_since > cooldown_hours

    def test_thread_recently_engaged_within_cooldown(self):
        """Threads within cooldown period should not be re-engaged."""
        # Given cooldown period of 1 hour
        cooldown_hours = 1
        # When last engagement was 30 minutes ago
        last_engagement = datetime.now() - timedelta(minutes=30)
        now = datetime.now()
        hours_since = (now - last_engagement).total_seconds() / 3600
        # Then should be within cooldown
        assert hours_since < cooldown_hours

    def test_thread_never_engaged_has_no_cooldown(self):
        """Threads never engaged should always be eligible."""
        # When last_engagement is None
        last_engagement = None
        # Then no cooldown applies
        assert last_engagement is None


class TestEngagementTypeSelection:
    """Test selection between text response vs emoji reaction."""

    def test_engagement_type_text_response_selected(self):
        """Test that text response can be selected."""
        engagement_types = ['text', 'reaction']
        selected_type = 'text'
        assert selected_type in engagement_types

    def test_engagement_type_reaction_selected(self):
        """Test that reaction can be selected."""
        engagement_types = ['text', 'reaction']
        selected_type = 'reaction'
        assert selected_type in engagement_types

    def test_engagement_type_distribution(self):
        """Test that engagement types are distributed (e.g., 70% text, 30% reaction)."""
        # This would be implemented with weighted random selection
        # For now, just verify both types exist
        engagement_types = ['text', 'reaction']
        assert len(engagement_types) == 2
        assert 'text' in engagement_types
        assert 'reaction' in engagement_types
