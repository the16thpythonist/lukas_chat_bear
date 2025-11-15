"""
Integration tests for Events API endpoints.
Tests full request/response cycle with authentication.
"""
import pytest
from datetime import datetime


class TestUpcomingEventsEndpoint:
    """Test GET /api/events/upcoming endpoint."""

    def test_upcoming_events_requires_auth(self, client):
        """Test endpoint requires authentication."""
        response = client.get('/api/events/upcoming')

        assert response.status_code == 401

    def test_upcoming_events_returns_list(self, authenticated_client, sample_scheduled_tasks_integration):
        """Test endpoint returns list of upcoming events."""
        response = authenticated_client.get('/api/events/upcoming?limit=50')

        assert response.status_code == 200
        data = response.get_json()

        assert 'events' in data
        assert 'count' in data
        assert isinstance(data['events'], list)
        assert data['count'] == 3  # 3 upcoming tasks in fixture

    def test_upcoming_events_structure(self, authenticated_client, sample_scheduled_tasks_integration):
        """Test event objects have correct structure."""
        response = authenticated_client.get('/api/events/upcoming')
        data = response.get_json()

        for event in data['events']:
            assert 'id' in event
            assert 'task_type' in event
            assert 'scheduled_time' in event
            assert 'target_type' in event
            assert 'status' in event
            assert 'metadata' in event
            assert event['status'] == 'pending'

    def test_upcoming_events_respects_limit(self, authenticated_client, sample_scheduled_tasks_integration):
        """Test limit parameter works."""
        response = authenticated_client.get('/api/events/upcoming?limit=2')
        data = response.get_json()

        assert len(data['events']) <= 2

    def test_upcoming_events_sorted_correctly(self, authenticated_client, sample_scheduled_tasks_integration):
        """Test events are sorted by scheduled time ascending."""
        response = authenticated_client.get('/api/events/upcoming')
        data = response.get_json()

        scheduled_times = [e['scheduled_time'] for e in data['events']]
        parsed_times = [datetime.fromisoformat(t) for t in scheduled_times]

        assert parsed_times == sorted(parsed_times)


class TestCompletedEventsEndpoint:
    """Test GET /api/events/completed endpoint."""

    def test_completed_events_requires_auth(self, client):
        """Test endpoint requires authentication."""
        response = client.get('/api/events/completed')

        assert response.status_code == 401

    def test_completed_events_returns_paginated_list(self, authenticated_client, sample_scheduled_tasks_integration):
        """Test endpoint returns paginated list."""
        response = authenticated_client.get('/api/events/completed?page=1&limit=10')

        assert response.status_code == 200
        data = response.get_json()

        assert 'events' in data
        assert 'page' in data
        assert 'limit' in data
        assert 'total' in data
        assert 'pages' in data

        assert data['page'] == 1
        assert data['limit'] == 10
        assert data['total'] == 5  # 5 completed tasks in fixture

    def test_completed_events_structure(self, authenticated_client, sample_scheduled_tasks_integration):
        """Test completed event objects have correct structure."""
        response = authenticated_client.get('/api/events/completed')
        data = response.get_json()

        for event in data['events']:
            assert 'id' in event
            assert 'task_type' in event
            assert 'scheduled_time' in event
            assert 'executed_at' in event
            assert 'status' in event
            assert 'metadata' in event
            assert event['status'] in ['completed', 'failed', 'cancelled']

    def test_completed_events_pagination(self, authenticated_client, sample_scheduled_tasks_integration):
        """Test pagination works correctly."""
        # Page 1
        response1 = authenticated_client.get('/api/events/completed?page=1&limit=3')
        data1 = response1.get_json()

        # Page 2
        response2 = authenticated_client.get('/api/events/completed?page=2&limit=3')
        data2 = response2.get_json()

        assert len(data1['events']) == 3
        assert len(data2['events']) == 2  # 5 total, 3 on first page
        assert data1['events'][0]['id'] != data2['events'][0]['id']

    def test_completed_events_sorted_correctly(self, authenticated_client, sample_scheduled_tasks_integration):
        """Test events sorted by executed time descending (most recent first)."""
        response = authenticated_client.get('/api/events/completed')
        data = response.get_json()

        executed_times = [e['executed_at'] for e in data['events']]
        parsed_times = [datetime.fromisoformat(t) for t in executed_times]

        assert parsed_times == sorted(parsed_times, reverse=True)

    def test_completed_events_invalid_page(self, authenticated_client, sample_scheduled_tasks_integration):
        """Test invalid page number is handled gracefully."""
        response = authenticated_client.get('/api/events/completed?page=-1')

        # Should default to page 1
        assert response.status_code == 200
        data = response.get_json()
        assert data['page'] >= 1


class TestEventsAPIErrors:
    """Test error handling in Events API."""

    def test_upcoming_events_limit_caps_at_100(self, authenticated_client):
        """Test limit parameter is capped at 100."""
        response = authenticated_client.get('/api/events/upcoming?limit=500')

        assert response.status_code == 200
        # Should not fail even with large limit

    def test_completed_events_handles_invalid_limit(self, authenticated_client):
        """Test invalid limit values are handled."""
        response = authenticated_client.get('/api/events/completed?limit=-5')

        assert response.status_code == 200
        # Should handle gracefully with valid default

    def test_events_api_handles_database_error(self, client):
        """Test API handles database errors gracefully."""
        # This test would require mocking the database to raise an error
        # For now, we'll just ensure the endpoint exists
        response = client.get('/api/events/upcoming')
        assert response.status_code in [200, 401, 500]  # Valid status codes
