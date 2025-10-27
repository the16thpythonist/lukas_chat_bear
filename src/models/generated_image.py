"""
GeneratedImage model.

Tracks AI-generated images posted by Lukas.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base, generate_uuid, utc_now


class GeneratedImage(Base):
    """
    Tracks AI-generated images created and posted by Lukas.

    Stores prompt, URL, cost, and posting details for audit and debugging.
    """

    __tablename__ = "generated_images"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # Image generation details
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Posting details
    posted_to_channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)

    # Performance metrics
    generation_duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Status tracking
    status: Mapped[str] = mapped_column(
        Enum("generated", "posted", "failed", name="image_status_enum"),
        nullable=False,
        index=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata (theme, occasion, Slack message timestamp, etc.)
    # Use 'meta' as attribute name to avoid SQLAlchemy reserved 'metadata' attribute
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    def __repr__(self) -> str:
        return f"<GeneratedImage(id={self.id}, status={self.status}, created_at={self.created_at})>"
