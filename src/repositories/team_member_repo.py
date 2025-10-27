"""
Team member repository.

Data access layer for TeamMember entity.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.models.team_member import TeamMember
from src.utils.logger import logger
from src.utils.config_loader import config


class TeamMemberRepository:
    """Repository for team member-related database operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_slack_id(self, slack_user_id: str) -> Optional[TeamMember]:
        """
        Get team member by Slack user ID.

        Args:
            slack_user_id: Slack user ID (e.g., "U123ABC456")

        Returns:
            TeamMember or None
        """
        return (
            self.db.query(TeamMember)
            .filter(TeamMember.slack_user_id == slack_user_id)
            .first()
        )

    def get_or_create(
        self,
        slack_user_id: str,
        display_name: str,
        real_name: Optional[str] = None,
        is_bot: bool = False,
    ) -> TeamMember:
        """
        Get existing team member or create new one.

        Automatically sets admin status based on bot.admin_users config.

        Args:
            slack_user_id: Slack user ID
            display_name: User's display name
            real_name: User's real name
            is_bot: Whether this user is a bot

        Returns:
            TeamMember (existing or new)
        """
        # Load admin user IDs from config
        admin_user_ids = config.get("bot.admin_users", [])
        is_admin = slack_user_id in admin_user_ids

        member = self.get_by_slack_id(slack_user_id)
        if member:
            # Update profile information if changed
            updated = False
            if member.display_name != display_name:
                member.display_name = display_name
                updated = True
            if real_name and member.real_name != real_name:
                member.real_name = real_name
                updated = True

            # Update admin status if it changed (respects config changes)
            if member.is_admin != is_admin:
                member.is_admin = is_admin
                updated = True
                logger.info(f"Updated admin status for {slack_user_id} to {is_admin}")

            if updated:
                member.updated_at = datetime.utcnow()
                self.db.commit()
                self.db.refresh(member)
            return member

        # Create new team member with correct admin status
        member = TeamMember(
            slack_user_id=slack_user_id,
            display_name=display_name,
            real_name=real_name,
            is_bot=is_bot,
            is_admin=is_admin,  # Set from config
        )
        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)
        logger.info(
            f"Created team member {member.id} for Slack user {slack_user_id} "
            f"(admin={is_admin})"
        )
        return member

    def update_last_proactive_dm(self, member_id: str) -> None:
        """
        Update the timestamp of the last proactive DM sent to a member.

        Args:
            member_id: Team member ID
        """
        member = self.db.query(TeamMember).get(member_id)
        if member:
            member.last_proactive_dm_at = datetime.utcnow()
            self.db.commit()
            logger.debug(f"Updated last_proactive_dm_at for member {member_id}")

    def increment_message_count(self, member_id: str) -> None:
        """
        Increment the total message count for a team member.

        Args:
            member_id: Team member ID
        """
        member = self.db.query(TeamMember).get(member_id)
        if member:
            member.total_messages_sent += 1
            self.db.commit()

    def get_active_non_bot_members(self) -> List[TeamMember]:
        """
        Get all active non-bot team members.

        Returns:
            List of TeamMember objects
        """
        return (
            self.db.query(TeamMember)
            .filter(
                and_(
                    TeamMember.is_active == True,
                    TeamMember.is_bot == False,
                )
            )
            .all()
        )

    def get_members_for_random_dm(self, exclude_recent_hours: int = 24) -> List[TeamMember]:
        """
        Get team members eligible for random proactive DM.

        Excludes members who received a DM within the specified hours.

        Args:
            exclude_recent_hours: Hours to exclude recent DM recipients

        Returns:
            List of TeamMember objects
        """
        from datetime import timedelta

        cutoff_time = datetime.utcnow() - timedelta(hours=exclude_recent_hours)

        return (
            self.db.query(TeamMember)
            .filter(
                and_(
                    TeamMember.is_active == True,
                    TeamMember.is_bot == False,
                    (
                        (TeamMember.last_proactive_dm_at == None)
                        | (TeamMember.last_proactive_dm_at < cutoff_time)
                    ),
                )
            )
            .all()
        )

    def get_never_contacted_users(self) -> List[TeamMember]:
        """
        Get all active non-bot users who have never received a proactive DM.

        Returns:
            List of TeamMember objects with last_proactive_dm_at = None
        """
        return (
            self.db.query(TeamMember)
            .filter(
                and_(
                    TeamMember.is_active == True,
                    TeamMember.is_bot == False,
                    TeamMember.last_proactive_dm_at == None,
                )
            )
            .all()
        )

    def is_admin(self, slack_user_id: str) -> bool:
        """
        Check if a user has admin privileges.

        Args:
            slack_user_id: Slack user ID

        Returns:
            True if user is admin, False otherwise
        """
        member = self.get_by_slack_id(slack_user_id)
        return member.is_admin if member else False

    def set_admin_status(self, slack_user_id: str, is_admin: bool) -> None:
        """
        Set admin status for a team member.

        Args:
            slack_user_id: Slack user ID
            is_admin: Admin status to set
        """
        member = self.get_by_slack_id(slack_user_id)
        if member:
            member.is_admin = is_admin
            self.db.commit()
            logger.info(f"Set admin status for {slack_user_id} to {is_admin}")
