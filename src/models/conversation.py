"""
ConversationSession model.

Represents an ongoing or completed conversation between Lukas and a team member.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base, generate_uuid, utc_now


class ConversationSession(Base):
    """
    Represents a conversation session between Lukas and a team member.

    A conversation can occur via DM, in a channel, or within a thread.
    Conversations are marked inactive after 24 hours of no activity.
    """

    __tablename__ = "conversation_sessions"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # Foreign key to team member
    team_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("team_members.id"), nullable=False, index=True
    )

    # Conversation context
    channel_type: Mapped[str] = mapped_column(
        Enum("dm", "channel", "thread", name="channel_type_enum"), nullable=False
    )
    channel_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    thread_ts: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    last_message_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, index=True)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    context_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    team_member: Mapped["TeamMember"] = relationship("TeamMember", back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ConversationSession(id={self.id}, channel_type={self.channel_type}, is_active={self.is_active})>"
