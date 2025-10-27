"""
Engagement service.

Manages proactive team engagement including random DM selection and thread engagement decisions.
Implements probability-based engagement logic with fair distribution and active hours checking.
"""

import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from src.models.team_member import TeamMember
from src.repositories.team_member_repo import TeamMemberRepository
from src.repositories.config_repo import ConfigurationRepository
from src.utils.logger import logger


class EngagementService:
    """
    Service for managing proactive team engagement.

    Handles random DM recipient selection with fair distribution and
    probability-based thread engagement decisions.
    """

    def __init__(
        self,
        db_session: Session,
        team_member_repo: Optional[TeamMemberRepository] = None,
        config_repo: Optional[ConfigurationRepository] = None,
    ):
        """
        Initialize engagement service.

        Args:
            db_session: Database session
            team_member_repo: Optional team member repository (creates if not provided)
            config_repo: Optional configuration repository (creates if not provided)
        """
        self.db = db_session
        self.team_member_repo = team_member_repo or TeamMemberRepository(db_session)
        self.config_repo = config_repo or ConfigurationRepository(db_session)

    def should_engage(self, probability: float, random_value: Optional[float] = None) -> bool:
        """
        Determine if Lukas should engage based on probability.

        Uses simple random comparison: engage if random < probability.

        Args:
            probability: Engagement probability (0.0-1.0)
            random_value: Optional predetermined random value for testing (0.0-1.0)

        Returns:
            True if should engage, False otherwise

        Raises:
            ValueError: If probability is outside 0.0-1.0 range
        """
        if not (0.0 <= probability <= 1.0):
            raise ValueError(f"Probability must be between 0.0 and 1.0, got {probability}")

        if random_value is None:
            random_value = random.random()

        engaged = random_value < probability
        logger.debug(
            f"Engagement decision: probability={probability:.2f}, "
            f"random={random_value:.2f}, engaged={engaged}"
        )
        return engaged

    def is_within_active_hours(
        self,
        check_time: Optional[datetime] = None,
        start_hour: Optional[int] = None,
        end_hour: Optional[int] = None,
        timezone: Optional[str] = None,
    ) -> bool:
        """
        Check if current time is within configured active hours.

        Args:
            check_time: Time to check (defaults to now in UTC)
            start_hour: Start hour (0-23), None means no restriction
            end_hour: End hour (0-23), None means no restriction
            timezone: Timezone string (e.g., 'Europe/Berlin', 'UTC')

        Returns:
            True if within active hours or no restriction configured
        """
        # If no active hours configured, always return True
        if start_hour is None or end_hour is None:
            return True

        if check_time is None:
            from datetime import timezone as dt_timezone
            check_time = datetime.now(dt_timezone.utc)

        # Convert to configured timezone if provided
        if timezone:
            try:
                from zoneinfo import ZoneInfo
                # Handle common timezone name variations
                tz_name = timezone.replace("Germany/", "Europe/")
                tz = ZoneInfo(tz_name)
                check_time = check_time.astimezone(tz)
                logger.debug(f"Converted to timezone {tz_name}: {check_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            except Exception as e:
                logger.warning(f"Invalid timezone '{timezone}': {e}, using server time")

        current_hour = check_time.hour
        within_hours = start_hour <= current_hour < end_hour

        if not within_hours:
            logger.debug(
                f"Outside active hours: current={current_hour}, "
                f"allowed={start_hour}-{end_hour}"
            )

        return within_hours

    def select_dm_recipient(self) -> Optional[TeamMember]:
        """
        Select a team member for proactive DM with fair distribution.

        Selection priority:
        1. Never contacted (last_proactive_dm_at = None) - highest priority
        2. Contacted longest ago - prioritize by oldest last_proactive_dm_at
        3. Exclude bots and inactive users

        Returns:
            Selected TeamMember or None if no eligible users
        """
        # Get eligible users using repository method
        eligible_users = self.team_member_repo.get_active_non_bot_members()

        if not eligible_users:
            logger.warning("No eligible users for proactive DM")
            return None

        # Separate never-contacted from previously-contacted
        never_contacted = [u for u in eligible_users if u.last_proactive_dm_at is None]
        previously_contacted = [u for u in eligible_users if u.last_proactive_dm_at is not None]

        # If there are never-contacted users, randomly select from them
        if never_contacted:
            selected = random.choice(never_contacted)
            logger.info(
                f"Selected never-contacted user for DM: {selected.display_name} "
                f"(slack_id={selected.slack_user_id})"
            )
            return selected

        # Otherwise select user contacted longest ago
        previously_contacted.sort(key=lambda u: u.last_proactive_dm_at)
        selected = previously_contacted[0]

        hours_since = (datetime.now() - selected.last_proactive_dm_at).total_seconds() / 3600
        logger.info(
            f"Selected least recently contacted user for DM: {selected.display_name} "
            f"(last_contact={hours_since:.1f}h ago)"
        )
        return selected

    def update_last_proactive_dm(self, team_member: TeamMember) -> None:
        """
        Update last_proactive_dm_at timestamp for a team member.

        Args:
            team_member: Team member who received proactive DM
        """
        team_member.last_proactive_dm_at = datetime.now()
        self.db.commit()
        logger.info(
            f"Updated last_proactive_dm_at for {team_member.display_name}"
        )

    def get_engagement_probability(self) -> float:
        """
        Get thread engagement probability from configuration.

        Returns:
            Probability as float (0.0-1.0), defaults to 0.20 (20%)
        """
        try:
            # Read from YAML config file instead of database
            from src.utils.config_loader import config
            probability = config.get("bot", {}).get("engagement", {}).get("thread_response_probability", 0.20)
            prob_float = float(probability)
            logger.debug(f"Using engagement probability from config: {prob_float:.0%}")
            return prob_float
        except Exception as e:
            logger.error(f"Error getting engagement probability: {e}, using default 0.20")
            return 0.20

    def get_reaction_probability(self) -> float:
        """
        Get emoji reaction probability from configuration.

        This controls the probability of reacting with an emoji vs text response
        for top-level messages.

        Returns:
            Probability as float (0.0-1.0), defaults to 0.30 (30%)
        """
        try:
            # Read from YAML config file
            from src.utils.config_loader import config
            probability = config.get("bot", {}).get("engagement", {}).get("reaction_probability", 0.30)
            prob_float = float(probability)
            logger.debug(f"Using reaction probability from config: {prob_float:.0%}")
            return prob_float
        except Exception as e:
            logger.error(f"Error getting reaction probability: {e}, using default 0.30")
            return 0.30

    def get_active_hours(self) -> tuple[Optional[int], Optional[int], Optional[str]]:
        """
        Get active hours configuration.

        Returns:
            Tuple of (start_hour, end_hour, timezone) or (None, None, None) if not configured
        """
        try:
            # Read from YAML config file instead of database
            from src.utils.config_loader import config
            active_hours_config = config.get("bot", {}).get("engagement", {}).get("active_hours", {})

            if active_hours_config and isinstance(active_hours_config, dict):
                start_str = active_hours_config.get("start", "")
                end_str = active_hours_config.get("end", "")
                timezone_str = active_hours_config.get("timezone", "UTC")

                # Parse "HH:MM" format to hour integer
                if start_str and end_str:
                    start = int(start_str.split(":")[0])
                    end = int(end_str.split(":")[0])
                    logger.debug(f"Using active hours from config: {start}:00-{end}:00 ({timezone_str})")
                    return (start, end, timezone_str)

            logger.debug("No active hours restriction configured (24/7 mode)")
            return (None, None, None)
        except Exception as e:
            logger.error(f"Error getting active hours: {e}")
            return (None, None, None)

    def is_thread_too_active(
        self,
        message_count: int,
        time_window_minutes: int = 60,
        threshold: Optional[int] = None
    ) -> bool:
        """
        Check if thread has too much activity to engage with.

        Prevents Lukas from overwhelming busy threads.

        Args:
            message_count: Number of messages in time window
            time_window_minutes: Time window to check (default 60 minutes)
            threshold: Max messages before considered "too active" (None = read from config)

        Returns:
            True if thread is too active (should skip), False otherwise
        """
        # Read threshold from config if not provided
        if threshold is None:
            try:
                from src.utils.config_loader import config
                threshold = config.get("bot", {}).get("engagement", {}).get("thread_activity_threshold", 10)
                threshold = int(threshold)
                logger.debug(f"Using thread activity threshold from config: {threshold}")
            except Exception as e:
                logger.error(f"Error getting thread activity threshold: {e}, using default 10")
                threshold = 10

        is_too_active = message_count >= threshold

        if is_too_active:
            logger.debug(
                f"Thread too active: {message_count} messages in {time_window_minutes}min "
                f"(threshold={threshold})"
            )

        return is_too_active

    def get_random_dm_interval_hours(self) -> float:
        """
        Get random DM interval from configuration.

        Returns:
            Interval in hours (supports fractional hours), defaults to 24
        """
        try:
            # Read from YAML config file instead of database
            from src.utils.config_loader import config
            interval = config.get("bot", {}).get("engagement", {}).get("random_dm_interval_hours", 24)
            interval_float = float(interval)
            logger.debug(f"Using random DM interval from config: {interval_float} hours")
            return interval_float
        except Exception as e:
            logger.error(f"Error getting DM interval: {e}, using default 24 hours")
            return 24.0

    def should_send_random_dm_now(self, last_dm_time: Optional[datetime]) -> bool:
        """
        Check if enough time has passed to send another random DM.

        Args:
            last_dm_time: When last random DM was sent (None if never)

        Returns:
            True if should send DM now
        """
        interval_hours = self.get_random_dm_interval_hours()

        # If never sent, allow sending now
        if last_dm_time is None:
            logger.debug("No previous random DM, allowing send now")
            return True

        # Check if interval has passed
        time_since_last = (datetime.now() - last_dm_time).total_seconds() / 3600
        should_send = time_since_last >= interval_hours

        if should_send:
            logger.debug(
                f"Random DM interval passed: {time_since_last:.1f}h >= {interval_hours}h"
            )
        else:
            logger.debug(
                f"Random DM interval not passed: {time_since_last:.1f}h < {interval_hours}h"
            )

        return should_send

    def should_add_reaction(self, random_value: Optional[float] = None) -> bool:
        """
        Decide if should add emoji reaction to a message.

        This is independent of text response decision. Uses reaction_probability
        to determine if an emoji reaction should be added.

        Args:
            random_value: Optional predetermined random value for testing (0.0-1.0)

        Returns:
            True if should add reaction, False otherwise
        """
        reaction_prob = self.get_reaction_probability()
        should_react = self.should_engage(reaction_prob, random_value)
        logger.debug(f"Reaction decision: probability={reaction_prob:.0%}, should_react={should_react}")
        return should_react

    def should_respond_with_text(self, random_value: Optional[float] = None) -> bool:
        """
        Decide if should respond with a text message.

        This is independent of emoji reaction decision. Uses thread_response_probability
        to determine if a text response should be posted.

        Args:
            random_value: Optional predetermined random value for testing (0.0-1.0)

        Returns:
            True if should respond with text, False otherwise
        """
        text_prob = self.get_engagement_probability()
        should_respond = self.should_engage(text_prob, random_value)
        logger.debug(f"Text response decision: probability={text_prob:.0%}, should_respond={should_respond}")
        return should_respond

    def get_available_emojis(self) -> list[str]:
        """
        Get list of available emoji reactions for Lukas.

        Returns:
            List of emoji names suitable for Lukas the Bear
        """
        return [
            'bear',
            'honey_pot',
            'paw_prints',
            'deciduous_tree',  # Forest
            'evergreen_tree',  # Forest
            'hugging_face',
            'thinking_face',
            '+1',  # Thumbs up
            'heart',
            'tada',  # Celebration
            'eyes',  # Watching
            'muscle',  # Strength
            'fire',
            '100',
            'clap',
            'star',
            'sparkles',
            'rocket',
            'zap',
            'rainbow',
        ]
