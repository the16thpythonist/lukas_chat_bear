"""
Unit tests for query builder functions.
Tests pagination, filtering, and query construction logic.
"""
import pytest
from datetime import datetime, timedelta
from backend.services.query_builder import paginate, build_activity_query, build_events_query, get_upcoming_events


class TestPagination:
    """Test pagination utility function."""

    def test_paginate_first_page(self, db_session, sample_messages):
        """Test pagination returns correct first page."""
        from backend.models import Message

        query = db_session.query(Message)
        result = paginate(query, page=1, limit=5)

        assert result['page'] == 1
        assert result['limit'] == 5
        assert len(result['items']) == 5
        assert result['total'] == 20  # sample_messages creates 20 messages
        assert result['pages'] == 4  # 20/5 = 4 pages

    def test_paginate_middle_page(self, db_session, sample_messages):
        """Test pagination returns correct middle page."""
        from backend.models import Message

        query = db_session.query(Message)
        result = paginate(query, page=2, limit=7)

        assert result['page'] == 2
        assert len(result['items']) == 7
        assert result['total'] == 20

    def test_paginate_last_page(self, db_session, sample_messages):
        """Test pagination handles last page with fewer items."""
        from backend.models import Message

        query = db_session.query(Message)
        result = paginate(query, page=3, limit=10)

        assert result['page'] == 3
        assert len(result['items']) == 0  # 20 items, 10 per page, page 3 is empty
        assert result['total'] == 20

    def test_paginate_empty_query(self, db_session):
        """Test pagination handles empty query."""
        from backend.models import Message

        query = db_session.query(Message)  # No messages in this test
        result = paginate(query, page=1, limit=10)

        assert result['page'] == 1
        assert result['limit'] == 10
        assert len(result['items']) == 0
        assert result['total'] == 0
        assert result['pages'] == 0

    def test_paginate_respects_limit_cap(self, db_session, sample_messages):
        """Test pagination caps limit at 100."""
        from backend.models import Message

        query = db_session.query(Message)
        result = paginate(query, page=1, limit=200)  # Request 200, should cap at 100

        assert result['limit'] == 100


class TestBuildActivityQuery:
    """Test activity query builder."""

    def test_build_query_no_filters(self, db_session, sample_messages):
        """Test building activity query without filters."""
        query = build_activity_query(db_session)
        results = query.all()

        assert len(results) == 20  # All messages

    def test_build_query_with_date_filter(self, db_session, sample_messages):
        """Test filtering messages by start date."""
        start_date = (datetime.utcnow() - timedelta(days=2)).isoformat()

        filters = {'start_date': start_date}
        query = build_activity_query(db_session, filters)
        results = query.all()

        # Should return messages from last 2 days
        assert len(results) > 0
        assert len(results) < 20

    def test_build_query_with_channel_type_filter(self, db_session, sample_messages):
        """Test filtering messages by channel type."""
        filters = {'channel_type': 'dm'}
        query = build_activity_query(db_session, filters)
        results = query.all()

        # Half the messages are in DM channel
        assert len(results) == 10

    def test_build_query_sorts_by_timestamp_desc(self, db_session, sample_messages):
        """Test query sorts by timestamp descending."""
        query = build_activity_query(db_session)
        results = query.all()

        # First result should be most recent
        timestamps = [r.timestamp for r in results]
        assert timestamps == sorted(timestamps, reverse=True)


class TestBuildEventsQuery:
    """Test events query builder."""

    def test_build_upcoming_events_query(self, db_session, sample_scheduled_tasks):
        """Test building query for upcoming events."""
        query = build_events_query(db_session, event_type='upcoming')
        results = query.all()

        assert len(results) == 3  # 3 upcoming tasks in fixture
        for task in results:
            assert task.status == 'pending'
            assert task.scheduled_at > datetime.utcnow()

    def test_build_completed_events_query(self, db_session, sample_scheduled_tasks):
        """Test building query for completed events."""
        query = build_events_query(db_session, event_type='completed')
        results = query.all()

        assert len(results) == 5  # 5 completed tasks in fixture
        for task in results:
            assert task.status in ['completed', 'failed']

    def test_upcoming_events_sorted_asc(self, db_session, sample_scheduled_tasks):
        """Test upcoming events sorted by scheduled time ascending."""
        query = build_events_query(db_session, event_type='upcoming')
        results = query.all()

        scheduled_times = [t.scheduled_at for t in results]
        assert scheduled_times == sorted(scheduled_times)

    def test_completed_events_sorted_desc(self, db_session, sample_scheduled_tasks):
        """Test completed events sorted by executed time descending."""
        query = build_events_query(db_session, event_type='completed')
        results = query.all()

        executed_times = [t.executed_at for t in results]
        assert executed_times == sorted(executed_times, reverse=True)


class TestGetUpcomingEvents:
    """Test get_upcoming_events helper function."""

    def test_get_upcoming_events_returns_dicts(self, db_session, sample_scheduled_tasks):
        """Test function returns list of dictionaries."""
        events = get_upcoming_events(db_session, limit=10)

        assert isinstance(events, list)
        assert len(events) == 3

        for event in events:
            assert isinstance(event, dict)
            assert 'id' in event
            assert 'task_type' in event
            assert 'scheduled_time' in event
            assert 'status' in event

    def test_get_upcoming_events_respects_limit(self, db_session, sample_scheduled_tasks):
        """Test function respects limit parameter."""
        events = get_upcoming_events(db_session, limit=2)

        assert len(events) == 2

    def test_get_upcoming_events_formats_timestamps(self, db_session, sample_scheduled_tasks):
        """Test function formats timestamps as ISO strings."""
        events = get_upcoming_events(db_session, limit=10)

        for event in events:
            assert isinstance(event['scheduled_time'], str)
            # Should be valid ISO format
            datetime.fromisoformat(event['scheduled_time'])
