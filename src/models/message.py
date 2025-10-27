"""
Message model.

Represents individual messages within a conversation.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base, generate_uuid, utc_now


class Message(Base):
    """
    Represents an individual message within a conversation.

    Messages can be from the user or from the bot (Lukas).
    """

    __tablename__ = "messages"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # Foreign key to conversation
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversation_sessions.id"), nullable=False, index=True
    )

    # Message details
    sender_type: Mapped[str] = mapped_column(
        Enum("user", "bot", name="sender_type_enum"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, index=True)
    slack_ts: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Use 'meta' as attribute name to avoid SQLAlchemy reserved 'metadata' attribute
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    conversation: Mapped["ConversationSession"] = relationship("ConversationSession", back_populates="messages")

    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message(id={self.id}, sender={self.sender_type}, content='{preview}')>"
