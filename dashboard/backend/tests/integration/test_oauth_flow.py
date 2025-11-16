"""
Integration tests for OAuth flow.
Tests the complete OAuth callback flow with mocked Slack API.
"""
import json
import pytest
from unittest.mock import patch, Mock
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def oauth_config(app):
    """Configure OAuth settings for testing."""
    app.config['SLACK_CLIENT_ID'] = 'test-client-id'
    app.config['SLACK_CLIENT_SECRET'] = 'test-client-secret'
    app.config['OAUTH_TOKENS_DIR'] = tempfile.mkdtemp()

    yield app

    # Cleanup
    if Path(app.config['OAUTH_TOKENS_DIR']).exists():
        shutil.rmtree(app.config['OAUTH_TOKENS_DIR'])


class TestOAuthCallback:
    """Test OAuth callback endpoint."""

    @patch('backend.services.slack_oauth_service.requests.post')
    def test_successful_oauth_callback(self, mock_post, client, oauth_config):
        """Test successful OAuth callback with valid code."""
        # Mock successful Slack API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "ok": True,
            "access_token": "xoxb-test-token-123456",
            "token_type": "bot",
            "scope": "chat:write,users:read,channels:read",
            "bot_user_id": "U012345ABCD",
            "app_id": "A012345WXYZ",
            "team": {
                "id": "T12345TEST",
                "name": "Test Workspace"
            },
            "authed_user": {
                "id": "U67890USER"
            },
            "is_enterprise_install": False
        }
        mock_post.return_value = mock_response

        # Make OAuth callback request
        response = client.get('/api/oauth/callback?code=test-code-123456')

        # Verify response
        assert response.status_code == 200
        assert b"Slack Installation Successful" in response.data
        assert b"Test Workspace" in response.data
        assert b"T12345TEST" in response.data

        # Verify Slack API was called correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "https://slack.com/api/oauth.v2.access" in call_args[0]
        assert call_args.kwargs["data"]["code"] == "test-code-123456"

        # Verify token file was created
        token_dir = Path(oauth_config.config['OAUTH_TOKENS_DIR'])
        token_files = list(token_dir.glob("tokens_T12345TEST_*.json"))
        assert len(token_files) == 1

        # Verify token file contents
        with open(token_files[0]) as f:
            saved_tokens = json.load(f)
        assert saved_tokens["access_token"] == "xoxb-test-token-123456"
        assert saved_tokens["team"]["name"] == "Test Workspace"
        assert "installed_at" in saved_tokens

    @patch('backend.services.slack_oauth_service.requests.post')
    def test_oauth_callback_with_user_token(self, mock_post, client, oauth_config):
        """Test OAuth callback that includes user token."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "ok": True,
            "access_token": "xoxb-bot-token",
            "bot_user_id": "U012345",
            "scope": "chat:write",
            "app_id": "A012345",
            "team": {"id": "T12345", "name": "Test"},
            "authed_user": {
                "id": "U67890",
                "access_token": "xoxp-user-token-987654",
                "token_type": "user",
                "scope": "search:read"
            }
        }
        mock_post.return_value = mock_response

        response = client.get('/api/oauth/callback?code=test-code')

        assert response.status_code == 200

        # Verify both tokens were saved
        token_dir = Path(oauth_config.config['OAUTH_TOKENS_DIR'])
        token_files = list(token_dir.glob("tokens_T12345_*.json"))
        with open(token_files[0]) as f:
            saved_tokens = json.load(f)
        assert saved_tokens["authed_user"]["access_token"] == "xoxp-user-token-987654"

    def test_oauth_callback_missing_code(self, client, oauth_config):
        """Test OAuth callback without code parameter."""
        response = client.get('/api/oauth/callback')

        assert response.status_code == 400
        assert b"Missing authorization code" in response.data

    def test_oauth_callback_user_denied(self, client, oauth_config):
        """Test OAuth callback when user denies installation."""
        response = client.get('/api/oauth/callback?error=access_denied')

        assert response.status_code == 400
        assert b"cancelled by the user" in response.data

    @patch('backend.services.slack_oauth_service.requests.post')
    def test_oauth_callback_invalid_code(self, mock_post, client, oauth_config):
        """Test OAuth callback with invalid/expired code."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "ok": False,
            "error": "invalid_code"
        }
        mock_post.return_value = mock_response

        response = client.get('/api/oauth/callback?code=invalid-code')

        assert response.status_code == 400
        assert b"invalid or has expired" in response.data

    @patch('backend.services.slack_oauth_service.requests.post')
    def test_oauth_callback_bad_redirect_uri(self, mock_post, client, oauth_config):
        """Test OAuth callback with redirect URI mismatch."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "ok": False,
            "error": "bad_redirect_uri"
        }
        mock_post.return_value = mock_response

        response = client.get('/api/oauth/callback?code=test-code')

        assert response.status_code == 400
        assert b"redirect URI" in response.data

    @patch('backend.services.slack_oauth_service.requests.post')
    def test_oauth_callback_network_error(self, mock_post, client, oauth_config):
        """Test OAuth callback with network error."""
        import requests
        mock_post.side_effect = requests.exceptions.RequestException("Network error")

        response = client.get('/api/oauth/callback?code=test-code')

        assert response.status_code == 500
        assert b"Failed to exchange" in response.data

    @patch('backend.services.slack_oauth_service.requests.post')
    def test_oauth_callback_file_write_error(self, mock_post, client, oauth_config):
        """Test OAuth callback when file write fails."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "ok": True,
            "access_token": "xoxb-test",
            "bot_user_id": "U012345",
            "scope": "chat:write",
            "app_id": "A012345",
            "team": {"id": "T12345", "name": "Test"}
        }
        mock_post.return_value = mock_response

        # Make directory read-only to cause write error
        import os
        token_dir = Path(oauth_config.config['OAUTH_TOKENS_DIR'])
        os.chmod(token_dir, 0o444)

        response = client.get('/api/oauth/callback?code=test-code')

        # Restore permissions
        os.chmod(token_dir, 0o755)

        assert response.status_code == 500
        assert b"failed to save" in response.data

    def test_oauth_callback_missing_credentials(self, client, app):
        """Test OAuth callback when credentials not configured."""
        # Clear OAuth config
        app.config['SLACK_CLIENT_ID'] = None
        app.config['SLACK_CLIENT_SECRET'] = None

        response = client.get('/api/oauth/callback?code=test-code')

        assert response.status_code == 500
        assert b"not set" in response.data


class TestOAuthInstallInfo:
    """Test OAuth install info endpoint."""

    def test_install_info_configured(self, client, oauth_config):
        """Test install info when OAuth is configured."""
        response = client.get('/api/oauth/install')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "install_url" in data
        assert "client_id=test-client-id" in data["install_url"]
        assert data["configured"] is True
        assert "callback_url" in data

    def test_install_info_not_configured(self, client, app):
        """Test install info when OAuth credentials missing."""
        app.config['SLACK_CLIENT_ID'] = None

        response = client.get('/api/oauth/install')

        assert response.status_code == 500
        data = json.loads(response.data)
        assert "not configured" in data["error"]

    def test_install_info_with_redirect_uri(self, client, oauth_config):
        """Test install info with redirect URI configured."""
        oauth_config.config['SLACK_REDIRECT_URI'] = 'https://example.com/callback'

        response = client.get('/api/oauth/install')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["redirect_uri_configured"] is True


class TestOAuthTokenPersistence:
    """Test token file persistence and format."""

    @patch('backend.services.slack_oauth_service.requests.post')
    def test_token_file_format(self, mock_post, client, oauth_config):
        """Test that token files are saved in correct format."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "ok": True,
            "access_token": "xoxb-test-token",
            "token_type": "bot",
            "scope": "chat:write,users:read",
            "bot_user_id": "U012345",
            "app_id": "A012345",
            "team": {"id": "T12345", "name": "Test Workspace"},
            "is_enterprise_install": False
        }
        mock_post.return_value = mock_response

        client.get('/api/oauth/callback?code=test-code')

        # Find and read token file
        token_dir = Path(oauth_config.config['OAUTH_TOKENS_DIR'])
        token_files = list(token_dir.glob("tokens_T12345_*.json"))

        with open(token_files[0]) as f:
            tokens = json.load(f)

        # Verify all required fields are present
        assert tokens["ok"] is True
        assert tokens["access_token"] == "xoxb-test-token"
        assert tokens["team"]["id"] == "T12345"
        assert "installed_at" in tokens
        # Verify ISO format timestamp
        from datetime import datetime
        datetime.fromisoformat(tokens["installed_at"].replace('Z', '+00:00'))

    @patch('backend.services.slack_oauth_service.requests.post')
    def test_multiple_installations(self, mock_post, client, oauth_config):
        """Test that multiple installations create separate files."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "ok": True,
            "access_token": "xoxb-test",
            "bot_user_id": "U012345",
            "scope": "chat:write",
            "app_id": "A012345",
            "team": {"id": "T12345", "name": "Test"}
        }
        mock_post.return_value = mock_response

        # Install twice
        client.get('/api/oauth/callback?code=test-code-1')
        client.get('/api/oauth/callback?code=test-code-2')

        # Verify two files were created
        token_dir = Path(oauth_config.config['OAUTH_TOKENS_DIR'])
        token_files = list(token_dir.glob("tokens_T12345_*.json"))
        assert len(token_files) == 2
