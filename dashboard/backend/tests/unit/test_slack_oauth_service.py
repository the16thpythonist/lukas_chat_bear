"""
Unit tests for Slack OAuth service.
Tests token exchange, file saving, and error handling.
"""
import json
import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from backend.services.slack_oauth_service import (
    exchange_code_for_tokens,
    save_tokens_to_file,
    get_oauth_error_message
)


class TestExchangeCodeForTokens:
    """Test cases for exchange_code_for_tokens function."""

    @patch('backend.services.slack_oauth_service.requests.post')
    def test_successful_token_exchange(self, mock_post):
        """Test successful OAuth token exchange."""
        # Mock successful Slack API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "ok": True,
            "access_token": "xoxb-test-token-123",
            "token_type": "bot",
            "scope": "chat:write,users:read",
            "bot_user_id": "U012345",
            "app_id": "A012345",
            "team": {
                "id": "T012345",
                "name": "Test Workspace"
            },
            "authed_user": {
                "id": "U67890"
            },
            "is_enterprise_install": False
        }
        mock_post.return_value = mock_response

        # Call function
        result = exchange_code_for_tokens(
            code="test-code-123",
            client_id="test-client-id",
            client_secret="test-client-secret"
        )

        # Verify result
        assert result is not None
        assert result["ok"] is True
        assert result["access_token"] == "xoxb-test-token-123"
        assert result["team"]["name"] == "Test Workspace"

        # Verify API call was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "https://slack.com/api/oauth.v2.access" in call_args[0]

    @patch('backend.services.slack_oauth_service.requests.post')
    def test_token_exchange_with_redirect_uri(self, mock_post):
        """Test token exchange with redirect_uri parameter."""
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True, "access_token": "xoxb-test"}
        mock_post.return_value = mock_response

        result = exchange_code_for_tokens(
            code="test-code",
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="https://example.com/callback"
        )

        # Verify redirect_uri was included in request
        call_kwargs = mock_post.call_args.kwargs
        assert "redirect_uri" in call_kwargs["data"]
        assert call_kwargs["data"]["redirect_uri"] == "https://example.com/callback"

    @patch('backend.services.slack_oauth_service.requests.post')
    def test_token_exchange_slack_error(self, mock_post):
        """Test handling of Slack API error response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "ok": False,
            "error": "invalid_code"
        }
        mock_post.return_value = mock_response

        result = exchange_code_for_tokens(
            code="invalid-code",
            client_id="test-id",
            client_secret="test-secret"
        )

        assert result is None

    @patch('backend.services.slack_oauth_service.requests.post')
    def test_token_exchange_network_error(self, mock_post):
        """Test handling of network errors."""
        import requests
        mock_post.side_effect = requests.exceptions.RequestException("Network error")

        result = exchange_code_for_tokens(
            code="test-code",
            client_id="test-id",
            client_secret="test-secret"
        )

        assert result is None

    @patch('backend.services.slack_oauth_service.requests.post')
    def test_token_exchange_timeout(self, mock_post):
        """Test handling of timeout errors."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        result = exchange_code_for_tokens(
            code="test-code",
            client_id="test-id",
            client_secret="test-secret"
        )

        assert result is None

    @patch('backend.services.slack_oauth_service.requests.post')
    def test_http_basic_auth_used(self, mock_post):
        """Test that HTTP Basic Auth is used for credentials."""
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True, "access_token": "xoxb-test"}
        mock_post.return_value = mock_response

        exchange_code_for_tokens(
            code="test-code",
            client_id="test-id",
            client_secret="test-secret"
        )

        # Verify Authorization header was set
        call_kwargs = mock_post.call_args.kwargs
        assert "Authorization" in call_kwargs["headers"]
        assert call_kwargs["headers"]["Authorization"].startswith("Basic ")


class TestSaveTokensToFile:
    """Test cases for save_tokens_to_file function."""

    @patch('builtins.open', new_callable=mock_open)
    @patch('backend.services.slack_oauth_service.Path')
    @patch('builtins.print')
    def test_successful_file_save(self, mock_print, mock_path, mock_file):
        """Test successful saving of tokens to file."""
        # Mock Path operations
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True
        mock_path_instance.__truediv__ = lambda self, other: Path(f"/test/dir/{other}")

        oauth_response = {
            "ok": True,
            "access_token": "xoxb-test-token",
            "token_type": "bot",
            "scope": "chat:write",
            "bot_user_id": "U012345",
            "app_id": "A012345",
            "team": {
                "id": "T012345",
                "name": "Test Workspace"
            },
            "authed_user": {
                "id": "U67890"
            },
            "is_enterprise_install": False
        }

        result = save_tokens_to_file(oauth_response, "/test/dir")

        # Verify file was created
        assert result is not None
        assert "tokens_T012345_" in result
        assert result.endswith(".json")

    @patch('builtins.open', side_effect=PermissionError("Permission denied"))
    @patch('backend.services.slack_oauth_service.Path')
    def test_file_save_permission_error(self, mock_path, mock_file):
        """Test handling of permission errors when saving file."""
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True
        mock_path_instance.__truediv__ = lambda self, other: Path(f"/test/dir/{other}")

        oauth_response = {
            "team": {"id": "T012345", "name": "Test"},
            "access_token": "xoxb-test",
            "bot_user_id": "U012345",
            "scope": "chat:write",
            "app_id": "A012345"
        }

        result = save_tokens_to_file(oauth_response, "/test/dir")

        assert result is None

    @patch('builtins.open', new_callable=mock_open)
    @patch('backend.services.slack_oauth_service.Path')
    @patch('builtins.print')
    def test_save_with_user_token(self, mock_print, mock_path, mock_file):
        """Test saving tokens with user token included."""
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True
        mock_path_instance.__truediv__ = lambda self, other: Path(f"/test/dir/{other}")

        oauth_response = {
            "access_token": "xoxb-bot-token",
            "bot_user_id": "U012345",
            "scope": "chat:write",
            "app_id": "A012345",
            "team": {"id": "T012345", "name": "Test"},
            "authed_user": {
                "id": "U67890",
                "access_token": "xoxp-user-token"
            }
        }

        result = save_tokens_to_file(oauth_response, "/test/dir")

        assert result is not None
        # Verify user token was printed (check print was called)
        assert mock_print.called

    @patch('builtins.open', new_callable=mock_open)
    @patch('backend.services.slack_oauth_service.Path')
    @patch('builtins.print')
    def test_console_output_format(self, mock_print, mock_path, mock_file):
        """Test that tokens are printed to console in correct format."""
        mock_path_instance = Mock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True
        mock_path_instance.__truediv__ = lambda self, other: Path(f"/test/dir/{other}")

        oauth_response = {
            "access_token": "xoxb-test-token",
            "bot_user_id": "U012345",
            "scope": "chat:write",
            "app_id": "A012345",
            "team": {"id": "T012345", "name": "Test Workspace"}
        }

        save_tokens_to_file(oauth_response, "/test/dir")

        # Verify console output contains key information
        printed_output = ''.join(str(call[0][0]) for call in mock_print.call_args_list)
        assert "SLACK OAUTH INSTALLATION SUCCESSFUL" in printed_output
        assert "Test Workspace" in printed_output
        assert "xoxb-test-token" in printed_output


class TestGetOAuthErrorMessage:
    """Test cases for get_oauth_error_message function."""

    def test_known_error_codes(self):
        """Test that known error codes return specific messages."""
        assert "invalid or has expired" in get_oauth_error_message("invalid_code")
        assert "redirect URI" in get_oauth_error_message("bad_redirect_uri")
        assert "already been used" in get_oauth_error_message("code_already_used")
        assert "client ID" in get_oauth_error_message("invalid_client_id")
        assert "client secret" in get_oauth_error_message("bad_client_secret")

    def test_unknown_error_code(self):
        """Test that unknown error codes return generic message."""
        message = get_oauth_error_message("unknown_custom_error")
        assert "unknown_custom_error" in message
        assert "OAuth error" in message

    def test_empty_error_code(self):
        """Test handling of empty error code."""
        message = get_oauth_error_message("")
        assert "OAuth error" in message
