"""
Scheduled Event Model

Represents a one-time scheduled message to be posted to a Slack channel at a future time.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Index

from src.models import Base


class ScheduledEvent(Base):
    """
    Model for scheduled channel messages.

    A scheduled event represents a one-time message that will be posted to a Slack channel
    at a specified future time. Events can be created via natural language commands (admin only)
    or through the dashboard UI.

    Attributes:
        id: Unique identifier
        event_type: Type of event (default: 'channel_message')
        scheduled_time: When to execute the event (UTC datetime)
        target_channel_id: Slack channel ID (e.g., 'C123456')
        target_channel_name: Channel name for display (e.g., '#general')
        message: Message content to post
        status: Event status (pending, completed, cancelled, failed)
        job_id: APScheduler job ID for cancellation
        created_by_user_id: Slack user ID who created the event
        created_by_user_name: Display name of creator
        created_at: When event was created
        updated_at: Last modification time
        executed_at: When event was actually executed
        error_message: Error details if execution failed
    """

    __tablename__ = 'scheduled_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False, default='channel_message', server_default='channel_message')
    scheduled_time = Column(DateTime, nullable=False)
    target_channel_id = Column(String(255), nullable=False)
    target_channel_name = Column(String(255), nullable=True)
    message = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default='pending', server_default='pending')
    job_id = Column(String(255), nullable=True, unique=True)
    created_by_user_id = Column(String(255), nullable=True)
    created_by_user_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # Indexes defined in migration, but documented here
    __table_args__ = (
        Index('idx_scheduled_events_status', 'status'),
        Index('idx_scheduled_events_scheduled_time', 'scheduled_time'),
        Index('idx_scheduled_events_created_by', 'created_by_user_id'),
    )

    def __init__(self, **kwargs):
        """
        Initialize a ScheduledEvent with Python-level defaults.

        This ensures defaults are set even when creating instances without database insertion.
        """
        # Set defaults if not provided
        if 'event_type' not in kwargs:
            kwargs['event_type'] = 'channel_message'
        if 'status' not in kwargs:
            kwargs['status'] = 'pending'
        if 'created_at' not in kwargs:
            kwargs['created_at'] = datetime.utcnow()

        super().__init__(**kwargs)

    def __repr__(self):
        return (
            f"<ScheduledEvent(id={self.id}, scheduled_time='{self.scheduled_time}', "
            f"channel='{self.target_channel_name}', status='{self.status}')>"
        )

    def to_dict(self):
        """Convert model to dictionary for API responses."""
        return {
            'id': self.id,
            'event_type': self.event_type,
            'scheduled_time': self.scheduled_time.isoformat() if self.scheduled_time else None,
            'target_channel_id': self.target_channel_id,
            'target_channel_name': self.target_channel_name,
            'message': self.message,
            'status': self.status,
            'job_id': self.job_id,
            'created_by_user_id': self.created_by_user_id,
            'created_by_user_name': self.created_by_user_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'error_message': self.error_message
        }

    def is_pending(self):
        """Check if event is pending execution."""
        return self.status == 'pending'

    def is_completed(self):
        """Check if event has been executed successfully."""
        return self.status == 'completed'

    def is_cancelled(self):
        """Check if event has been cancelled."""
        return self.status == 'cancelled'

    def is_failed(self):
        """Check if event execution failed."""
        return self.status == 'failed'

    def can_be_edited(self):
        """Check if event can be edited (only pending events can be edited)."""
        return self.is_pending()

    def can_be_cancelled(self):
        """Check if event can be cancelled (only pending events can be cancelled)."""
        return self.is_pending()
