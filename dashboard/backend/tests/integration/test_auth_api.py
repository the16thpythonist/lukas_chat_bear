"""
Integration tests for Authentication API endpoints.
Tests login, logout, and session management.
"""
import pytest


class TestLoginEndpoint:
    """Test POST /api/auth/login endpoint."""

    def test_login_with_correct_password(self, client):
        """Test successful login with correct password."""
        response = client.post('/api/auth/login', json={
            'password': 'test_password_123'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Login successful'

    def test_login_with_incorrect_password(self, client):
        """Test login fails with incorrect password."""
        response = client.post('/api/auth/login', json={
            'password': 'wrong_password'
        })

        assert response.status_code == 401
        data = response.get_json()
        assert 'message' in data or 'error' in data
        assert data.get('success') is False

    def test_login_without_password(self, client):
        """Test login fails without password in request."""
        response = client.post('/api/auth/login', json={})

        assert response.status_code == 400

    def test_login_creates_session(self, client):
        """Test successful login creates session."""
        # Login
        response = client.post('/api/auth/login', json={
            'password': 'test_password_123'
        })

        assert response.status_code == 200

        # Verify session exists by accessing protected endpoint
        response = client.get('/api/auth/session')
        assert response.status_code == 200
        data = response.get_json()
        assert data['authenticated'] is True


class TestLogoutEndpoint:
    """Test POST /api/auth/logout endpoint."""

    def test_logout_clears_session(self, authenticated_client):
        """Test logout clears the session."""
        # Verify we're authenticated
        response = authenticated_client.get('/api/auth/session')
        assert response.get_json()['authenticated'] is True

        # Logout
        response = authenticated_client.post('/api/auth/logout')
        assert response.status_code == 200

        # Verify session is cleared
        response = authenticated_client.get('/api/auth/session')
        assert response.get_json()['authenticated'] is False

    def test_logout_when_not_logged_in(self, client):
        """Test logout when not authenticated."""
        response = client.post('/api/auth/logout')

        # Should succeed even if not logged in
        assert response.status_code == 200


class TestSessionEndpoint:
    """Test GET /api/auth/session endpoint."""

    def test_session_when_authenticated(self, authenticated_client):
        """Test session endpoint returns authenticated status."""
        response = authenticated_client.get('/api/auth/session')

        assert response.status_code == 200
        data = response.get_json()
        assert data['authenticated'] is True

    def test_session_when_not_authenticated(self, client):
        """Test session endpoint when not logged in."""
        response = client.get('/api/auth/session')

        assert response.status_code == 200
        data = response.get_json()
        assert data['authenticated'] is False


class TestAuthenticationFlow:
    """Test complete authentication flow."""

    def test_full_auth_workflow(self, client):
        """Test complete login -> use API -> logout workflow."""
        # 1. Start unauthenticated
        response = client.get('/api/auth/session')
        assert response.get_json()['authenticated'] is False

        # 2. Access protected endpoint (should fail)
        response = client.get('/api/activity')
        assert response.status_code == 401

        # 3. Login
        response = client.post('/api/auth/login', json={
            'password': 'test_password_123'
        })
        assert response.status_code == 200

        # 4. Verify authenticated
        response = client.get('/api/auth/session')
        assert response.get_json()['authenticated'] is True

        # 5. Access protected endpoint (should succeed)
        response = client.get('/api/activity')
        assert response.status_code in [200, 500]  # 200 or 500 (no data), not 401

        # 6. Logout
        response = client.post('/api/auth/logout')
        assert response.status_code == 200

        # 7. Verify unauthenticated
        response = client.get('/api/auth/session')
        assert response.get_json()['authenticated'] is False

        # 8. Access protected endpoint should fail again
        response = client.get('/api/activity')
        assert response.status_code == 401

    def test_session_persists_across_requests(self, client):
        """Test session persists across multiple requests."""
        # Login
        client.post('/api/auth/login', json={
            'password': 'test_password_123'
        })

        # Make multiple requests
        for _ in range(5):
            response = client.get('/api/auth/session')
            assert response.get_json()['authenticated'] is True
