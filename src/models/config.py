"""
Configuration model.

Stores runtime configuration parameters.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base, generate_uuid, utc_now


class Configuration(Base):
    """
    Stores runtime configuration parameters.

    Configuration can be updated via admin commands without bot restart.
    """

    __tablename__ = "configurations"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # Configuration key-value
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(
        Enum("string", "integer", "float", "boolean", "json", name="value_type_enum"),
        nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Audit tracking
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    updated_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("team_members.id"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Configuration(key={self.key}, value={self.value})>"
