"""
SQLAlchemy models for Lukas the Bear chatbot.

All database models inherit from the Base declarative base.
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


def generate_uuid() -> str:
    """Generate a UUID string for use as primary key."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.utcnow()


# Import all models
from src.models.conversation import ConversationSession
from src.models.message import Message
from src.models.team_member import TeamMember
from src.models.scheduled_task import ScheduledTask, TaskType, TaskStatus, TargetType
from src.models.config import Configuration
from src.models.engagement_event import EngagementEvent
from src.models.generated_image import GeneratedImage

# Export all models for easy importing
__all__ = [
    "Base",
    "generate_uuid",
    "utc_now",
    "ConversationSession",
    "Message",
    "TeamMember",
    "ScheduledTask",
    "TaskType",
    "TaskStatus",
    "TargetType",
    "Configuration",
    "EngagementEvent",
    "GeneratedImage",
]
