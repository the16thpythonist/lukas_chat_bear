"""
TeamMember model.

Represents a Slack workspace user.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base, generate_uuid, utc_now


class TeamMember(Base):
    """
    Represents a Slack workspace user.

    Tracks user profile information, admin status, and engagement metrics.
    """

    __tablename__ = "team_members"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # Slack user information
    slack_user_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    real_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    # User attributes
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # Engagement tracking
    last_proactive_dm_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    total_messages_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    # Relationships
    conversations: Mapped[list["ConversationSession"]] = relationship("ConversationSession", back_populates="team_member")

    def __repr__(self) -> str:
        return f"<TeamMember(id={self.id}, slack_user_id={self.slack_user_id}, display_name={self.display_name})>"
