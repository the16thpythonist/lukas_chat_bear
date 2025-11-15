"""
Unit tests for ScheduledEventRepository
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base
from src.models.scheduled_event import ScheduledEvent
from src.repositories.scheduled_event_repo import ScheduledEventRepository


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def repo(db_session):
    """Create repository instance."""
    return ScheduledEventRepository(db_session)


@pytest.fixture
def sample_event():
    """Create a sample event for testing."""
    return ScheduledEvent(
        scheduled_time=datetime.utcnow() + timedelta(hours=1),
        target_channel_id='C123456',
        target_channel_name='#general',
        message='Test message',
        created_by_user_id='U123456',
        created_by_user_name='Test User'
    )


def test_create_event(repo, sample_event):
    """Test creating a new event."""
    created = repo.create(sample_event)

    assert created.id is not None
    assert created.target_channel_id == 'C123456'
    assert created.message == 'Test message'
    assert created.status == 'pending'


def test_get_by_id(repo, sample_event):
    """Test retrieving event by ID."""
    created = repo.create(sample_event)

    retrieved = repo.get_by_id(created.id)

    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.message == created.message


def test_get_by_id_not_found(repo):
    """Test retrieving non-existent event."""
    result = repo.get_by_id(999)

    assert result is None


def test_get_by_job_id(repo, sample_event):
    """Test retrieving event by job ID."""
    sample_event.job_id = 'job_123'
    created = repo.create(sample_event)

    retrieved = repo.get_by_job_id('job_123')

    assert retrieved is not None
    assert retrieved.id == created.id


def test_get_all(repo):
    """Test retrieving all events."""
    # Create multiple events
    for i in range(3):
        event = ScheduledEvent(
            scheduled_time=datetime.utcnow() + timedelta(hours=i+1),
            target_channel_id=f'C{i}',
            message=f'Message {i}'
        )
        repo.create(event)

    all_events = repo.get_all()

    assert len(all_events) == 3


def test_get_all_with_status_filter(repo):
    """Test retrieving events filtered by status."""
    # Create pending event
    pending = ScheduledEvent(
        scheduled_time=datetime.utcnow() + timedelta(hours=1),
        target_channel_id='C1',
        message='Pending'
    )
    repo.create(pending)

    # Create completed event
    completed = ScheduledEvent(
        scheduled_time=datetime.utcnow() - timedelta(hours=1),
        target_channel_id='C2',
        message='Completed',
        status='completed'
    )
    repo.create(completed)

    pending_events = repo.get_all(status='pending')
    completed_events = repo.get_all(status='completed')

    assert len(pending_events) == 1
    assert len(completed_events) == 1
    assert pending_events[0].status == 'pending'
    assert completed_events[0].status == 'completed'


def test_get_all_with_pagination(repo):
    """Test pagination."""
    # Create 5 events
    for i in range(5):
        event = ScheduledEvent(
            scheduled_time=datetime.utcnow() + timedelta(hours=i+1),
            target_channel_id=f'C{i}',
            message=f'Message {i}'
        )
        repo.create(event)

    # Get first page (2 events)
    page1 = repo.get_all(limit=2, offset=0)
    # Get second page (2 events)
    page2 = repo.get_all(limit=2, offset=2)

    assert len(page1) == 2
    assert len(page2) == 2
    assert page1[0].id != page2[0].id


def test_get_pending(repo):
    """Test getting only pending events."""
    # Create pending event
    pending = ScheduledEvent(
        scheduled_time=datetime.utcnow() + timedelta(hours=1),
        target_channel_id='C1',
        message='Pending'
    )
    repo.create(pending)

    # Create completed event
    completed = ScheduledEvent(
        scheduled_time=datetime.utcnow(),
        target_channel_id='C2',
        message='Completed',
        status='completed'
    )
    repo.create(completed)

    pending_events = repo.get_pending()

    assert len(pending_events) == 1
    assert pending_events[0].status == 'pending'


def test_get_upcoming(repo):
    """Test getting upcoming events."""
    now = datetime.utcnow()

    # Create past event (should not be returned)
    past = ScheduledEvent(
        scheduled_time=now - timedelta(hours=1),
        target_channel_id='C1',
        message='Past'
    )
    repo.create(past)

    # Create future event (should be returned)
    future = ScheduledEvent(
        scheduled_time=now + timedelta(hours=1),
        target_channel_id='C2',
        message='Future'
    )
    repo.create(future)

    upcoming = repo.get_upcoming(limit=10)

    assert len(upcoming) == 1
    assert upcoming[0].message == 'Future'


def test_get_by_creator(repo):
    """Test getting events by creator."""
    # Create events by user1
    for i in range(2):
        event = ScheduledEvent(
            scheduled_time=datetime.utcnow() + timedelta(hours=i+1),
            target_channel_id=f'C{i}',
            message=f'Message {i}',
            created_by_user_id='U111'
        )
        repo.create(event)

    # Create event by user2
    event = ScheduledEvent(
        scheduled_time=datetime.utcnow() + timedelta(hours=3),
        target_channel_id='C3',
        message='Message 3',
        created_by_user_id='U222'
    )
    repo.create(event)

    user1_events = repo.get_by_creator('U111')
    user2_events = repo.get_by_creator('U222')

    assert len(user1_events) == 2
    assert len(user2_events) == 1


def test_update_event(repo, sample_event):
    """Test updating an event."""
    created = repo.create(sample_event)

    # Update message
    created.message = 'Updated message'
    updated = repo.update(created)

    assert updated.message == 'Updated message'
    assert updated.updated_at is not None


def test_mark_completed(repo, sample_event):
    """Test marking event as completed."""
    created = repo.create(sample_event)

    completed = repo.mark_completed(created.id)

    assert completed is not None
    assert completed.status == 'completed'
    assert completed.executed_at is not None


def test_mark_failed(repo, sample_event):
    """Test marking event as failed."""
    created = repo.create(sample_event)

    failed = repo.mark_failed(created.id, 'Test error')

    assert failed is not None
    assert failed.status == 'failed'
    assert failed.error_message == 'Test error'
    assert failed.executed_at is not None


def test_cancel_event(repo, sample_event):
    """Test cancelling a pending event."""
    created = repo.create(sample_event)

    cancelled = repo.cancel(created.id)

    assert cancelled is not None
    assert cancelled.status == 'cancelled'
    assert cancelled.updated_at is not None


def test_cancel_completed_event_fails(repo, sample_event):
    """Test that completed events cannot be cancelled."""
    created = repo.create(sample_event)
    repo.mark_completed(created.id)

    result = repo.cancel(created.id)

    assert result is None  # Cannot cancel completed event


def test_delete_event(repo, sample_event):
    """Test deleting an event."""
    created = repo.create(sample_event)

    deleted = repo.delete(created.id)

    assert deleted is True

    # Verify it's gone
    retrieved = repo.get_by_id(created.id)
    assert retrieved is None


def test_delete_nonexistent_event(repo):
    """Test deleting non-existent event."""
    result = repo.delete(999)

    assert result is False


def test_count_by_status(repo):
    """Test counting events by status."""
    # Create 2 pending, 1 completed
    for i in range(2):
        event = ScheduledEvent(
            scheduled_time=datetime.utcnow() + timedelta(hours=i+1),
            target_channel_id=f'C{i}',
            message=f'Pending {i}'
        )
        repo.create(event)

    completed = ScheduledEvent(
        scheduled_time=datetime.utcnow(),
        target_channel_id='C3',
        message='Completed',
        status='completed'
    )
    repo.create(completed)

    pending_count = repo.count_by_status('pending')
    completed_count = repo.count_by_status('completed')

    assert pending_count == 2
    assert completed_count == 1


def test_count_pending(repo):
    """Test counting pending events."""
    # Create 3 pending events
    for i in range(3):
        event = ScheduledEvent(
            scheduled_time=datetime.utcnow() + timedelta(hours=i+1),
            target_channel_id=f'C{i}',
            message=f'Message {i}'
        )
        repo.create(event)

    count = repo.count_pending()

    assert count == 3
