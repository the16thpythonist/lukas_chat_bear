"""
ScheduledTask model.

Represents time-based tasks (proactive DMs, image posts, maintenance).
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import DateTime, Enum, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base, generate_uuid, utc_now


class TaskType(PyEnum):
    """Enum for scheduled task types."""
    RANDOM_DM = "random_dm"
    IMAGE_POST = "image_post"
    CLEANUP = "cleanup"
    REMINDER = "reminder"


class TargetType(PyEnum):
    """Enum for task target types."""
    USER = "user"
    CHANNEL = "channel"
    SYSTEM = "system"


class TaskStatus(PyEnum):
    """Enum for task execution status."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduledTask(Base):
    """
    Represents a scheduled task to be executed by APScheduler.

    Task types include:
    - random_dm: Proactive DM to a team member
    - image_post: Post AI-generated image to channel
    - cleanup: Database maintenance task
    - reminder: User-requested scheduled message
    """

    __tablename__ = "scheduled_tasks"

    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)

    # APScheduler job ID (unique per execution, not globally unique)
    job_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Job name for grouping recurring tasks (e.g., "random_dm_task")
    job_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Task configuration
    task_type: Mapped[str] = mapped_column(
        Enum("random_dm", "image_post", "cleanup", "reminder", name="task_type_enum"),
        nullable=False,
        index=True
    )
    target_type: Mapped[str] = mapped_column(
        Enum("user", "channel", "system", name="target_type_enum"),
        nullable=False
    )
    target_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Scheduling
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Execution tracking
    status: Mapped[str] = mapped_column(
        Enum("pending", "executing", "completed", "failed", "cancelled", name="task_status_enum"),
        nullable=False,
        default="pending",
        index=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Use 'meta' as attribute name to avoid SQLAlchemy reserved 'metadata' attribute
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    def __repr__(self) -> str:
        return f"<ScheduledTask(id={self.id}, task_type={self.task_type}, status={self.status})>"
