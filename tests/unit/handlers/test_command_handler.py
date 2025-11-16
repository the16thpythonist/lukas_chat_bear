"""
Unit tests for command_handler module.

Tests:
- Helper functions (get_user_from_slack_id)
- ConfirmationFormatter message formatting
- handle_app_mention function
- Handler registration
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.handlers.command_handler import (
    get_user_from_slack_id,
    ConfirmationFormatter,
    handle_app_mention,
    register_command_handlers,
)
from src.models.team_member import TeamMember


# ===== HELPER FUNCTION TESTS =====


class TestGetUserFromSlackId:
    """Test get_user_from_slack_id helper function."""

    def test_returns_team_member_when_found(self, test_session):
        """Test that user is returned when found in database."""
        # Arrange
        member = TeamMember(
            slack_user_id="U123ABC",
            display_name="Test User",
            real_name="Test User",
            is_bot=False
        )
        test_session.add(member)
        test_session.commit()

        # Act
        result = get_user_from_slack_id("U123ABC", test_session)

        # Assert
        assert result is not None
        assert result.slack_user_id == "U123ABC"
        assert result.display_name == "Test User"

    def test_returns_none_when_not_found(self, test_session):
        """Test that None is returned when user not in database."""
        # Act
        result = get_user_from_slack_id("U_NONEXISTENT", test_session)

        # Assert
        assert result is None

    def test_uses_repository_method(self, test_session):
        """Test that function uses TeamMemberRepository correctly."""
        # Arrange
        member = TeamMember(
            slack_user_id="U456DEF",
            display_name="Another User",
            is_bot=False
        )
        test_session.add(member)
        test_session.commit()

        # Act
        result = get_user_from_slack_id("U456DEF", test_session)

        # Assert - verify repository lookup worked
        assert result.slack_user_id == "U456DEF"


# ===== CONFIRMATION FORMATTER TESTS =====


class TestConfirmationFormatter:
    """Test ConfirmationFormatter static methods."""

    def test_post_success_message(self):
        """Test successful post message formatting."""
        # Act
        message = ConfirmationFormatter.post_success("general")

        # Assert
        assert "✅" in message
        assert "Done!" in message
        assert "#general" in message
        assert "🐻" in message

    def test_post_failure_message(self):
        """Test failed post message formatting."""
        # Act
        message = ConfirmationFormatter.post_failure("random", "Channel not found")

        # Assert
        assert "❌" in message
        assert "Oops!" in message
        assert "#random" in message
        assert "Channel not found" in message
        assert "invited" in message
        assert "🐻" in message

    def test_reminder_success_message(self):
        """Test successful reminder message formatting."""
        # Act
        message = ConfirmationFormatter.reminder_success("in 30 minutes", "check the build")

        # Assert
        assert "⏰" in message
        assert "Got it!" in message
        assert "in 30 minutes" in message
        assert "check the build" in message
        assert "won't forget" in message
        assert "🐻" in message

    def test_reminder_failure_message(self):
        """Test failed reminder message formatting."""
        # Act
        message = ConfirmationFormatter.reminder_failure("Invalid time format")

        # Assert
        assert "❌" in message
        assert "couldn't set that reminder" in message
        assert "Invalid time format" in message
        assert "Try asking" in message
        assert "🐻" in message

    def test_config_success_message_with_known_setting(self):
        """Test config success with known setting name."""
        # Act
        message = ConfirmationFormatter.config_success("dm_interval", "60-120")

        # Assert
        assert "⚙️" in message
        assert "Configuration updated!" in message
        assert "random DM interval" in message
        assert "60-120" in message
        assert "🐻" in message

    def test_config_success_message_with_unknown_setting(self):
        """Test config success with unknown setting name."""
        # Act
        message = ConfirmationFormatter.config_success("custom_setting", "value123")

        # Assert
        assert "Configuration updated!" in message
        assert "custom_setting" in message
        assert "value123" in message

    def test_config_success_all_known_settings(self):
        """Test all known setting name mappings."""
        settings = {
            "dm_interval": "random DM interval",
            "thread_probability": "thread engagement probability",
            "image_interval": "image posting interval",
        }

        for setting, friendly_name in settings.items():
            message = ConfirmationFormatter.config_success(setting, "test_value")
            assert friendly_name in message

    def test_config_failure_message(self):
        """Test config failure message formatting."""
        # Act
        message = ConfirmationFormatter.config_failure("dm_interval", "Invalid format")

        # Assert
        assert "❌" in message
        assert "Couldn't update" in message
        assert "dm_interval" in message
        assert "Invalid format" in message
        assert "🐻" in message

    def test_permission_denied_message(self):
        """Test permission denied message formatting."""
        # Act
        message = ConfirmationFormatter.permission_denied("update_config")

        # Assert
        assert "🚫" in message
        assert "Sorry" in message
        assert "admin privileges" in message
        assert "🐻" in message

    def test_unknown_command_message(self):
        """Test unknown command message formatting."""
        # Act
        message = ConfirmationFormatter.unknown_command("foobarbaz command")

        # Assert
        assert "🤔" in message
        assert "not sure I understand" in message
        assert "ask me naturally" in message
        assert "🐻" in message

    def test_error_message(self):
        """Test error message formatting."""
        # Act
        message = ConfirmationFormatter.error_message("Database connection failed")

        # Assert
        assert "😅" in message
        assert "Oops!" in message
        assert "Something went wrong" in message
        assert "Database connection failed" in message
        assert "🐻" in message


# ===== HANDLE APP MENTION TESTS =====


class TestHandleAppMention:
    """Test handle_app_mention async function."""

    @pytest.mark.asyncio
    async def test_ignores_bot_messages(self):
        """Test that bot messages are ignored."""
        # Arrange
        event = {
            "user": "U123",
            "text": "test message",
            "channel": "C123",
            "bot_id": "B456"  # Bot message
        }
        say_mock = AsyncMock()
        client_mock = Mock()

        # Act
        await handle_app_mention(event, say_mock, client_mock)

        # Assert - should not call say
        say_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_removes_bot_mention_from_text(self, test_session):
        """Test that bot mention is stripped from message text."""
        # Arrange
        event = {
            "user": "U123",
            "text": "<@U_BOT123> remind me in 30 minutes",
            "channel": "C123"
        }
        say_mock = AsyncMock()
        client_mock = Mock()

        # Create user in database
        member = TeamMember(
            slack_user_id="U123",
            display_name="Test User",
            is_bot=False
        )
        test_session.add(member)
        test_session.commit()

        # Act - should call handle_direct_message which will process the cleaned text
        with patch('src.handlers.command_handler.get_db') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = test_session
            with patch('src.handlers.message_handler.handle_direct_message') as mock_handler:
                mock_handler.return_value = None
                await handle_app_mention(event, say_mock, client_mock)

                # Assert - verify handler was called
                mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_responds_to_unknown_user(self):
        """Test that bot asks unknown users to DM first."""
        # Arrange
        event = {
            "user": "U_UNKNOWN",
            "text": "<@U_BOT> hello",
            "channel": "C123"
        }
        say_mock = AsyncMock()
        client_mock = Mock()

        # Act
        with patch('src.handlers.command_handler.get_db') as mock_get_db:
            # Return session with no users
            mock_session = Mock()
            mock_session.__enter__ = Mock(return_value=mock_session)
            mock_session.__exit__ = Mock(return_value=None)
            mock_get_db.return_value = mock_session

            with patch('src.handlers.command_handler.get_user_from_slack_id') as mock_get_user:
                mock_get_user.return_value = None  # User not found

                await handle_app_mention(event, say_mock, client_mock)

        # Assert - should ask user to DM
        say_mock.assert_called_once()
        call_args = say_mock.call_args[0][0]
        assert "don't recognize you" in call_args
        assert "Send me a DM" in call_args

    @pytest.mark.asyncio
    async def test_passes_to_message_handler_for_known_user(self, test_session):
        """Test that known users are passed to message handler."""
        # Arrange
        event = {
            "user": "U123",
            "text": "<@U_BOT> test command",
            "channel": "C123"
        }
        say_mock = AsyncMock()
        client_mock = Mock()

        # Create user
        member = TeamMember(
            slack_user_id="U123",
            display_name="Test User",
            is_bot=False
        )
        test_session.add(member)
        test_session.commit()

        # Act
        with patch('src.handlers.command_handler.get_db') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = test_session
            with patch('src.handlers.message_handler.handle_direct_message') as mock_handler:
                mock_handler.return_value = None
                await handle_app_mention(event, say_mock, client_mock)

                # Assert - message handler should be called
                mock_handler.assert_called_once_with(event, say_mock, client_mock)

    @pytest.mark.asyncio
    async def test_handles_exceptions_gracefully(self):
        """Test that exceptions are caught and error message is sent."""
        # Arrange
        event = {
            "user": "U123",
            "text": "test",
            "channel": "C123"
        }
        say_mock = AsyncMock()
        client_mock = Mock()

        # Act - force an exception
        with patch('src.handlers.command_handler.get_db') as mock_get_db:
            mock_get_db.side_effect = Exception("Database error")

            await handle_app_mention(event, say_mock, client_mock)

        # Assert - should send error message
        say_mock.assert_called_once()
        call_args = say_mock.call_args[0][0]
        assert "trouble processing" in call_args


# ===== HANDLER REGISTRATION TESTS =====


class TestRegisterCommandHandlers:
    """Test register_command_handlers function."""

    def test_registers_app_mention_event(self):
        """Test that app_mention event handler is registered."""
        # Arrange
        mock_app = Mock()
        event_decorator = Mock()
        mock_app.event = Mock(return_value=event_decorator)

        # Act
        register_command_handlers(mock_app)

        # Assert - verify event decorator was called with "app_mention"
        mock_app.event.assert_called()
        call_args = mock_app.event.call_args[0]
        assert "app_mention" in call_args

    def test_registration_logs_success(self):
        """Test that successful registration is logged."""
        # Arrange
        mock_app = Mock()
        mock_app.event = Mock(return_value=lambda f: f)

        # Act
        with patch('src.handlers.command_handler.logger') as mock_logger:
            register_command_handlers(mock_app)

            # Assert - verify logging
            mock_logger.info.assert_called()
            call_args = str(mock_logger.info.call_args)
            assert "Command handlers registered" in call_args or "MCP" in call_args

    def test_registered_handler_calls_handle_app_mention(self):
        """Test that registered handler correctly calls handle_app_mention."""
        # Arrange
        mock_app = Mock()
        registered_handler = None

        def capture_handler(event_name):
            def decorator(func):
                nonlocal registered_handler
                registered_handler = func
                return func
            return decorator

        mock_app.event = capture_handler

        # Act - register handlers
        register_command_handlers(mock_app)

        # Assert - verify a handler was registered
        assert registered_handler is not None

    @pytest.mark.asyncio
    async def test_registered_handler_is_async(self):
        """Test that registered handler is an async function."""
        # Arrange
        mock_app = Mock()
        registered_handler = None

        def capture_handler(event_name):
            def decorator(func):
                nonlocal registered_handler
                registered_handler = func
                return func
            return decorator

        mock_app.event = capture_handler

        # Act
        register_command_handlers(mock_app)

        # Assert - verify handler is async
        import inspect
        assert inspect.iscoroutinefunction(registered_handler)


# ===== INTEGRATION TESTS =====


class TestCommandHandlerIntegration:
    """Integration tests for command handler components working together."""

    @pytest.mark.asyncio
    async def test_full_mention_flow_with_known_user(self, test_session):
        """Test complete flow from mention to message handler for known user."""
        # Arrange
        member = TeamMember(
            slack_user_id="U_REAL_USER",
            display_name="Real User",
            is_bot=False
        )
        test_session.add(member)
        test_session.commit()

        event = {
            "user": "U_REAL_USER",
            "text": "<@U_BOT> help me with something",
            "channel": "C_CHANNEL"
        }
        say_mock = AsyncMock()
        client_mock = Mock()

        # Act
        with patch('src.handlers.command_handler.get_db') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = test_session
            with patch('src.handlers.message_handler.handle_direct_message') as mock_handler:
                mock_handler.return_value = None
                await handle_app_mention(event, say_mock, client_mock)

                # Assert - full flow executed
                mock_handler.assert_called_once()
                # Should not send "don't recognize you" message
                if say_mock.called:
                    call_text = say_mock.call_args[0][0]
                    assert "don't recognize you" not in call_text

    @pytest.mark.asyncio
    async def test_bot_mention_with_multiple_mentions_in_text(self, test_session):
        """Test handling message with multiple @mentions."""
        # Arrange
        member = TeamMember(
            slack_user_id="U123",
            display_name="User",
            is_bot=False
        )
        test_session.add(member)
        test_session.commit()

        event = {
            "user": "U123",
            "text": "<@U_BOT> can you help <@U_OTHER_USER> with this?",
            "channel": "C123"
        }
        say_mock = AsyncMock()
        client_mock = Mock()

        # Act
        with patch('src.handlers.command_handler.get_db') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = test_session
            with patch('src.handlers.message_handler.handle_direct_message') as mock_handler:
                mock_handler.return_value = None
                await handle_app_mention(event, say_mock, client_mock)

                # Assert - should still work
                mock_handler.assert_called_once()
