"""
EngagementEvent model.

Audit log of Lukas's proactive channel engagement decisions.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base, generate_uuid, utc_now


class EngagementEvent(Base):
    """
    Audit log of proactive engagement decisions.

    Records whether Lukas decided to engage with a thread or message,
    along with the probability calculation used.
    """

    __tablename__ = "engagement_events"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # Slack context
    channel_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    thread_ts: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Decision details
    event_type: Mapped[str] = mapped_column(
        Enum("thread_response", "reaction", "ignored", name="event_type_enum"),
        nullable=False
    )
    decision_probability: Mapped[float] = mapped_column(Float, nullable=False)
    random_value: Mapped[float] = mapped_column(Float, nullable=False)
    engaged: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)

    # Reference to created message (if engaged)
    message_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("messages.id"), nullable=True
    )

    # Metadata (thread context, activity level, etc.)
    # Use 'meta' as attribute name to avoid SQLAlchemy reserved 'metadata' attribute
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, index=True)

    def __repr__(self) -> str:
        return f"<EngagementEvent(id={self.id}, event_type={self.event_type}, engaged={self.engaged})>"
