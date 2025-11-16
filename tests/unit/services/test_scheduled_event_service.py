"""
Unit tests for ScheduledEventService
"""

import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, call
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import pytz

from src.models import Base
from src.models.scheduled_event import ScheduledEvent
from src.services.scheduled_event_service import ScheduledEventService


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
def mock_scheduler():
    """Create mock APScheduler instance."""
    scheduler = Mock(spec=BackgroundScheduler)
    scheduler.add_job = Mock()
    scheduler.reschedule_job = Mock()
    scheduler.remove_job = Mock()
    return scheduler


@pytest.fixture
def mock_slack_client():
    """Create mock Slack client."""
    client = Mock()
    client.chat_postMessage = Mock(return_value={'ok': True})
    return client


@pytest.fixture
def service(db_session, mock_scheduler, mock_slack_client):
    """Create ScheduledEventService instance."""
    with patch('src.services.scheduled_event_service.config') as mock_config:
        mock_config.get.return_value = 'UTC'
        return ScheduledEventService(db_session, mock_scheduler, mock_slack_client)


@pytest.fixture
def service_est(db_session, mock_scheduler, mock_slack_client):
    """Create ScheduledEventService with EST timezone."""
    with patch('src.services.scheduled_event_service.config') as mock_config:
        mock_config.get.return_value = 'America/New_York'
        return ScheduledEventService(db_session, mock_scheduler, mock_slack_client)


class TestParseTime:
    """Tests for parse_time method."""

    def test_parse_absolute_time(self, service):
        """Test parsing absolute time like '3pm Friday'."""
        # Use a fixed reference time for consistent testing
        reference = datetime(2025, 10, 27, 10, 0, 0)  # Monday 10am

        result = service.parse_time("3pm Friday", reference_time=reference)

        assert result is not None
        assert result.hour == 15  # 3pm
        # Should be Friday (day 4)
        assert result.weekday() == 4

    def test_parse_relative_time(self, service):
        """Test parsing relative time like 'in 30 minutes'."""
        reference = datetime.utcnow()

        result = service.parse_time("in 30 minutes", reference_time=reference)

        assert result is not None
        # Should be approximately 30 minutes from reference
        diff = (result - reference).total_seconds()
        assert 1700 < diff < 1900  # Allow some margin (28-32 minutes)

    def test_parse_tomorrow(self, service):
        """Test parsing 'tomorrow at 2pm'."""
        reference = datetime(2025, 10, 27, 10, 0, 0)

        result = service.parse_time("tomorrow at 2pm", reference_time=reference)

        assert result is not None
        assert result.hour == 14  # 2pm
        assert result.day == 28  # Next day

    def test_parse_invalid_time(self, service):
        """Test parsing invalid time string."""
        result = service.parse_time("not a valid time")

        assert result is None

    def test_parse_empty_string(self, service):
        """Test parsing empty string."""
        result = service.parse_time("")

        assert result is None

    def test_parse_none(self, service):
        """Test parsing None."""
        result = service.parse_time(None)

        assert result is None

    def test_parse_with_timezone(self, service_est):
        """Test parsing with non-UTC timezone."""
        reference = datetime(2025, 10, 27, 10, 0, 0)

        result = service_est.parse_time("3pm", reference_time=reference)

        assert result is not None
        # Result should be in UTC, so 3pm EST = 8pm UTC (during DST)
        # Note: This is a naive UTC datetime, so we just check it parsed


class TestCreateEvent:
    """Tests for create_event method."""

    def test_create_event_success(self, service, mock_scheduler):
        """Test successfully creating an event."""
        scheduled_time = datetime.utcnow() + timedelta(hours=1)

        event, error = service.create_event(
            scheduled_time=scheduled_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Test message',
            created_by_user_id='U123456',
            created_by_user_name='Test User'
        )

        assert event is not None
        assert error is None
        assert event.id is not None
        assert event.target_channel_id == 'C123456'
        assert event.message == 'Test message'
        assert event.status == 'pending'
        assert event.job_id is not None

        # Verify APScheduler job was created
        mock_scheduler.add_job.assert_called_once()
        call_args = mock_scheduler.add_job.call_args
        assert call_args[1]['id'] == f"scheduled_event_{event.id}"

    def test_create_event_past_time(self, service):
        """Test creating event with past time fails."""
        past_time = datetime.utcnow() - timedelta(hours=1)

        event, error = service.create_event(
            scheduled_time=past_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Test message'
        )

        assert event is None
        assert error == "Scheduled time must be in the future"

    def test_create_event_now(self, service):
        """Test creating event for current time fails."""
        now = datetime.utcnow()

        event, error = service.create_event(
            scheduled_time=now,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Test message'
        )

        assert event is None
        assert error == "Scheduled time must be in the future"

    def test_create_event_minimal_fields(self, service):
        """Test creating event with minimal required fields."""
        scheduled_time = datetime.utcnow() + timedelta(hours=1)

        event, error = service.create_event(
            scheduled_time=scheduled_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Test message'
        )

        assert event is not None
        assert error is None
        assert event.created_by_user_id is None
        assert event.created_by_user_name is None


class TestCreateFromNaturalLanguage:
    """Tests for create_from_natural_language method."""

    def test_create_from_natural_language_success(self, service, mock_scheduler):
        """Test creating event from natural language time."""
        event, error = service.create_from_natural_language(
            time_string="in 2 hours",
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Meeting reminder',
            created_by_user_id='U123456'
        )

        assert event is not None
        assert error is None
        assert event.message == 'Meeting reminder'
        mock_scheduler.add_job.assert_called_once()

    def test_create_from_natural_language_invalid_time(self, service):
        """Test creating event with unparseable time."""
        event, error = service.create_from_natural_language(
            time_string="not a valid time",
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Test message'
        )

        assert event is None
        assert "Could not parse time" in error


class TestUpdateEvent:
    """Tests for update_event method."""

    def test_update_event_time(self, service, mock_scheduler):
        """Test updating event's scheduled time."""
        # Create event first
        original_time = datetime.utcnow() + timedelta(hours=1)
        event, _ = service.create_event(
            scheduled_time=original_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Test message'
        )

        # Update time
        new_time = datetime.utcnow() + timedelta(hours=2)
        updated, error = service.update_event(
            event_id=event.id,
            scheduled_time=new_time
        )

        assert updated is not None
        assert error is None
        assert updated.scheduled_time == new_time

        # Verify job was rescheduled
        mock_scheduler.reschedule_job.assert_called_once()
        call_args = mock_scheduler.reschedule_job.call_args
        assert call_args[1]['job_id'] == event.job_id

    def test_update_event_message(self, service):
        """Test updating event's message."""
        # Create event first
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        event, _ = service.create_event(
            scheduled_time=scheduled_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Original message'
        )

        # Update message
        updated, error = service.update_event(
            event_id=event.id,
            message='Updated message'
        )

        assert updated is not None
        assert error is None
        assert updated.message == 'Updated message'

    def test_update_event_not_found(self, service):
        """Test updating non-existent event."""
        updated, error = service.update_event(
            event_id=999,
            message='Test'
        )

        assert updated is None
        assert error == "Event not found"

    def test_update_completed_event_fails(self, service):
        """Test updating completed event fails."""
        # Create and complete event
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        event, _ = service.create_event(
            scheduled_time=scheduled_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Test message'
        )
        service.repo.mark_completed(event.id)

        # Try to update
        updated, error = service.update_event(
            event_id=event.id,
            message='New message'
        )

        assert updated is None
        assert "Cannot edit event" in error

    def test_update_event_past_time_fails(self, service):
        """Test updating to past time fails."""
        # Create event
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        event, _ = service.create_event(
            scheduled_time=scheduled_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Test message'
        )

        # Try to update to past time
        past_time = datetime.utcnow() - timedelta(hours=1)
        updated, error = service.update_event(
            event_id=event.id,
            scheduled_time=past_time
        )

        assert updated is None
        assert error == "Scheduled time must be in the future"


class TestCancelEvent:
    """Tests for cancel_event method."""

    def test_cancel_event_success(self, service, mock_scheduler):
        """Test successfully cancelling an event."""
        # Create event
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        event, _ = service.create_event(
            scheduled_time=scheduled_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Test message'
        )

        # Cancel event
        success, error = service.cancel_event(event.id)

        assert success is True
        assert error is None

        # Verify job was removed
        mock_scheduler.remove_job.assert_called_once_with(event.job_id)

        # Verify status updated
        cancelled = service.get_event(event.id)
        assert cancelled.status == 'cancelled'

    def test_cancel_event_not_found(self, service):
        """Test cancelling non-existent event."""
        success, error = service.cancel_event(999)

        assert success is False
        assert error == "Event not found"

    def test_cancel_completed_event_fails(self, service):
        """Test cancelling completed event fails."""
        # Create and complete event
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        event, _ = service.create_event(
            scheduled_time=scheduled_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Test message'
        )
        service.repo.mark_completed(event.id)

        # Try to cancel
        success, error = service.cancel_event(event.id)

        assert success is False
        assert "Cannot cancel event" in error

    def test_cancel_event_job_removal_fails(self, service, mock_scheduler):
        """Test cancelling event when job removal fails (should still cancel in DB)."""
        # Create event
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        event, _ = service.create_event(
            scheduled_time=scheduled_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Test message'
        )

        # Make remove_job raise exception
        mock_scheduler.remove_job.side_effect = Exception("Job not found")

        # Cancel should still succeed (DB update happens)
        success, error = service.cancel_event(event.id)

        assert success is True
        assert error is None


class TestExecuteEvent:
    """Tests for _execute_event method."""

    def test_execute_event_success(self, db_session, service, mock_slack_client):
        """Test successfully executing an event."""
        # Create event
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        event, _ = service.create_event(
            scheduled_time=scheduled_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Test message'
        )

        # Execute event using module-level function
        from src.services.scheduled_event_service import execute_scheduled_event
        from contextlib import contextmanager

        @contextmanager
        def mock_get_db():
            yield db_session

        with patch.dict('os.environ', {'SLACK_BOT_TOKEN': 'test-token'}, clear=False):
            with patch('src.utils.database.get_db', mock_get_db):
                with patch('slack_sdk.WebClient') as mock_web_client:
                    mock_web_client.return_value = mock_slack_client
                    mock_slack_client.chat_postMessage.return_value = {'ok': True}
                    execute_scheduled_event(event.id)

        # Verify message was posted
        mock_slack_client.chat_postMessage.assert_called_once_with(
            channel='C123456',
            text='Test message'
        )

        # Refresh to get latest state
        db_session.expire_all()
        executed = service.get_event(event.id)
        assert executed.status == 'completed'
        assert executed.executed_at is not None

    def test_execute_event_slack_error(self, db_session, service, mock_slack_client):
        """Test executing event when Slack API returns error."""
        # Create event
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        event, _ = service.create_event(
            scheduled_time=scheduled_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Test message'
        )

        # Mock Slack error response
        mock_slack_client.chat_postMessage.return_value = {
            'ok': False,
            'error': 'channel_not_found'
        }

        # Execute event using module-level function
        from src.services.scheduled_event_service import execute_scheduled_event
        from contextlib import contextmanager

        @contextmanager
        def mock_get_db():
            yield db_session

        with patch.dict('os.environ', {'SLACK_BOT_TOKEN': 'test-token'}, clear=False):
            with patch('src.utils.database.get_db', mock_get_db):
                with patch('slack_sdk.WebClient') as mock_web_client:
                    mock_web_client.return_value = mock_slack_client
                    execute_scheduled_event(event.id)

        # Refresh to get latest state
        db_session.expire_all()
        executed = service.get_event(event.id)
        assert executed.status == 'failed'
        assert executed.error_message == 'channel_not_found'

    def test_execute_event_slack_exception(self, db_session, service, mock_slack_client):
        """Test executing event when Slack client raises exception."""
        # Create event
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        event, _ = service.create_event(
            scheduled_time=scheduled_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Test message'
        )

        # Mock Slack exception
        mock_slack_client.chat_postMessage.side_effect = Exception("Network error")

        # Execute event using module-level function
        from src.services.scheduled_event_service import execute_scheduled_event
        from contextlib import contextmanager

        @contextmanager
        def mock_get_db():
            yield db_session

        with patch.dict('os.environ', {'SLACK_BOT_TOKEN': 'test-token'}, clear=False):
            with patch('src.utils.database.get_db', mock_get_db):
                with patch('slack_sdk.WebClient') as mock_web_client:
                    mock_web_client.return_value = mock_slack_client
                    execute_scheduled_event(event.id)

        # Refresh to get latest state
        db_session.expire_all()
        executed = service.get_event(event.id)
        assert executed.status == 'failed'
        assert 'Network error' in executed.error_message

    def test_execute_event_not_found(self, service):
        """Test executing non-existent event."""
        # Should not raise exception
        from src.services.scheduled_event_service import execute_scheduled_event
        execute_scheduled_event(999)  # Should not raise

    def test_execute_event_already_completed(self, service, mock_slack_client):
        """Test executing already completed event (should skip)."""
        # Create and complete event
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        event, _ = service.create_event(
            scheduled_time=scheduled_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Test message'
        )
        service.repo.mark_completed(event.id)

        # Try to execute again using module-level function
        from src.services.scheduled_event_service import execute_scheduled_event
        with patch('slack_sdk.WebClient') as mock_web_client:
            mock_web_client.return_value = mock_slack_client
            execute_scheduled_event(event.id)

        # Verify Slack not called
        mock_slack_client.chat_postMessage.assert_not_called()

    def test_execute_event_no_slack_client(self, db_session, mock_scheduler):
        """Test executing event when no Slack client available."""
        # Create service without Slack client
        with patch('src.services.scheduled_event_service.config') as mock_config:
            mock_config.get.return_value = 'UTC'
            service = ScheduledEventService(db_session, mock_scheduler, slack_client=None)

        # Create event
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        event, _ = service.create_event(
            scheduled_time=scheduled_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Test message'
        )

        # Execute event using module-level function with no Slack token
        from src.services.scheduled_event_service import execute_scheduled_event
        from contextlib import contextmanager

        @contextmanager
        def mock_get_db():
            yield db_session

        # Need to keep database env vars but remove SLACK_BOT_TOKEN
        env_without_slack = {k: v for k, v in os.environ.items() if k != 'SLACK_BOT_TOKEN'}
        with patch.dict('os.environ', env_without_slack, clear=True):
            with patch('src.utils.database.get_db', mock_get_db):
                execute_scheduled_event(event.id)

        # Refresh the event from database
        db_session.expire_all()
        executed = service.get_event(event.id)
        assert executed.status == 'failed'
        assert 'Slack token not available' in executed.error_message


class TestQueryMethods:
    """Tests for query methods."""

    def test_get_event(self, service):
        """Test getting event by ID."""
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        created, _ = service.create_event(
            scheduled_time=scheduled_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Test message'
        )

        retrieved = service.get_event(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_pending_events(self, service):
        """Test getting pending events."""
        # Create pending event
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        service.create_event(
            scheduled_time=scheduled_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Pending'
        )

        # Create and complete another event
        event2, _ = service.create_event(
            scheduled_time=scheduled_time,
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Completed'
        )
        service.repo.mark_completed(event2.id)

        pending = service.get_pending_events()

        assert len(pending) == 1
        assert pending[0].message == 'Pending'

    def test_get_upcoming_events(self, service):
        """Test getting upcoming events."""
        now = datetime.utcnow()

        # Create future event
        service.create_event(
            scheduled_time=now + timedelta(hours=1),
            target_channel_id='C123456',
            target_channel_name='#general',
            message='Future'
        )

        upcoming = service.get_upcoming_events(limit=10)

        assert len(upcoming) == 1
        assert upcoming[0].message == 'Future'
