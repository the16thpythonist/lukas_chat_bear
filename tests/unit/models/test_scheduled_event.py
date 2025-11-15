"""
Unit tests for ScheduledEvent model
"""

import pytest
from datetime import datetime, timedelta
from src.models.scheduled_event import ScheduledEvent


def test_scheduled_event_creation():
    """Test creating a scheduled event instance."""
    scheduled_time = datetime.utcnow() + timedelta(hours=1)

    event = ScheduledEvent(
        event_type='channel_message',
        scheduled_time=scheduled_time,
        target_channel_id='C123456',
        target_channel_name='#general',
        message='Test message',
        status='pending',
        created_by_user_id='U123456',
        created_by_user_name='Test User'
    )

    assert event.event_type == 'channel_message'
    assert event.scheduled_time == scheduled_time
    assert event.target_channel_id == 'C123456'
    assert event.target_channel_name == '#general'
    assert event.message == 'Test message'
    assert event.status == 'pending'
    assert event.created_by_user_id == 'U123456'
    assert event.created_by_user_name == 'Test User'


def test_scheduled_event_default_values():
    """Test default values for scheduled event."""
    scheduled_time = datetime.utcnow() + timedelta(hours=1)

    event = ScheduledEvent(
        scheduled_time=scheduled_time,
        target_channel_id='C123456',
        message='Test message'
    )

    assert event.event_type == 'channel_message'  # Default value
    assert event.status == 'pending'  # Default value
    assert event.created_at is not None  # Auto-generated


def test_scheduled_event_to_dict():
    """Test converting scheduled event to dictionary."""
    scheduled_time = datetime.utcnow() + timedelta(hours=1)

    event = ScheduledEvent(
        event_type='channel_message',
        scheduled_time=scheduled_time,
        target_channel_id='C123456',
        target_channel_name='#general',
        message='Test message',
        status='pending'
    )
    event.id = 1  # Simulate database ID

    result = event.to_dict()

    assert result['id'] == 1
    assert result['event_type'] == 'channel_message'
    assert result['scheduled_time'] == scheduled_time.isoformat()
    assert result['target_channel_id'] == 'C123456'
    assert result['target_channel_name'] == '#general'
    assert result['message'] == 'Test message'
    assert result['status'] == 'pending'


def test_scheduled_event_status_checks():
    """Test status checking methods."""
    event = ScheduledEvent(
        scheduled_time=datetime.utcnow() + timedelta(hours=1),
        target_channel_id='C123456',
        message='Test',
        status='pending'
    )

    assert event.is_pending() is True
    assert event.is_completed() is False
    assert event.is_cancelled() is False
    assert event.is_failed() is False

    # Test completed status
    event.status = 'completed'
    assert event.is_pending() is False
    assert event.is_completed() is True

    # Test cancelled status
    event.status = 'cancelled'
    assert event.is_cancelled() is True

    # Test failed status
    event.status = 'failed'
    assert event.is_failed() is True


def test_scheduled_event_can_be_edited():
    """Test edit permission check."""
    event = ScheduledEvent(
        scheduled_time=datetime.utcnow() + timedelta(hours=1),
        target_channel_id='C123456',
        message='Test',
        status='pending'
    )

    assert event.can_be_edited() is True

    # Completed events cannot be edited
    event.status = 'completed'
    assert event.can_be_edited() is False

    # Cancelled events cannot be edited
    event.status = 'cancelled'
    assert event.can_be_edited() is False


def test_scheduled_event_can_be_cancelled():
    """Test cancel permission check."""
    event = ScheduledEvent(
        scheduled_time=datetime.utcnow() + timedelta(hours=1),
        target_channel_id='C123456',
        message='Test',
        status='pending'
    )

    assert event.can_be_cancelled() is True

    # Completed events cannot be cancelled
    event.status = 'completed'
    assert event.can_be_cancelled() is False


def test_scheduled_event_repr():
    """Test string representation."""
    scheduled_time = datetime(2025, 10, 31, 15, 0, 0)
    event = ScheduledEvent(
        scheduled_time=scheduled_time,
        target_channel_id='C123456',
        target_channel_name='#general',
        message='Test',
        status='pending'
    )
    event.id = 42

    repr_str = repr(event)
    assert '42' in repr_str
    assert '#general' in repr_str
    assert 'pending' in repr_str
