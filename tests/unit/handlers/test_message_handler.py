"""
Unit tests for message_handler module.

Tests:
- LLM service selection (get_llm_service)
- Direct message handling
- App mention handling
- Handler registration
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from slack_sdk.errors import SlackApiError
from src.handlers.message_handler import (
    get_llm_service,
    handle_direct_message,
    handle_app_mention,
    register_message_handlers,
)
from src.models.team_member import TeamMember
from src.models.conversation import ConversationSession
from src.models.message import Message


# ===== GET_LLM_SERVICE TESTS =====


class TestGetLlmService:
    """Test LLM service selection logic."""

    def test_returns_agent_service_when_mcp_enabled_and_initialized(self):
        """Test that agent service is returned when MCP is enabled and agent is initialized."""
        # Arrange
        with patch.dict('os.environ', {'USE_MCP_AGENT': 'true'}):
            with patch('src.services.llm_agent_service.llm_agent_service') as mock_agent:
                mock_agent.agent = MagicMock()  # Agent is initialized

                # Act
                service = get_llm_service()

                # Assert
                assert service == mock_agent

    def test_returns_standard_service_when_mcp_disabled(self):
        """Test that standard LLM service is returned when MCP is disabled."""
        # Arrange
        with patch.dict('os.environ', {'USE_MCP_AGENT': 'false'}):
            with patch('src.handlers.message_handler.llm_service') as mock_service:
                # Act
                service = get_llm_service()

                # Assert
                assert service == mock_service

    def test_returns_standard_service_when_agent_not_initialized(self):
        """Test that standard service is returned when agent is not initialized."""
        # Arrange
        with patch.dict('os.environ', {'USE_MCP_AGENT': 'true'}):
            with patch('src.services.llm_agent_service.llm_agent_service') as mock_agent:
                mock_agent.agent = None  # Agent not initialized

                with patch('src.handlers.message_handler.llm_service') as mock_service:
                    # Act
                    service = get_llm_service()

                    # Assert
                    assert service == mock_service

    def test_returns_standard_service_when_agent_import_fails(self):
        """Test that standard service is returned when agent import fails."""
        # Arrange
        with patch.dict('os.environ', {'USE_MCP_AGENT': 'true'}):
            with patch('src.handlers.message_handler.llm_service') as mock_service:
                # Make the import fail
                with patch.dict('sys.modules', {'src.services.llm_agent_service': None}):
                    # Act
                    service = get_llm_service()

                    # Assert
                    assert service == mock_service


# ===== HANDLE_DIRECT_MESSAGE TESTS =====


class TestHandleDirectMessage:
    """Test handle_direct_message function."""

    @pytest.mark.asyncio
    async def test_ignores_bot_messages(self):
        """Test that bot messages are ignored."""
        # Arrange
        event = {
            "user": "U_BOT",
            "text": "bot message",
            "channel": "D123",
            "ts": "1234.5678",
            "bot_id": "B123"  # Bot message
        }
        say_mock = AsyncMock()
        client_mock = Mock()

        # Act
        await handle_direct_message(event, say_mock, client_mock)

        # Assert - should not interact with database or send messages
        say_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_new_team_member_from_slack_data(self, test_session):
        """Test that new team member is created from Slack user data."""
        # Arrange
        event = {
            "user": "U_NEW_USER",
            "text": "Hello Lukas",
            "channel": "D123",
            "ts": "1234.5678"
        }
        say_mock = AsyncMock()
        say_mock.return_value = {"ts": "1234.5679"}

        client_mock = AsyncMock()
        client_mock.users_info = AsyncMock(return_value={
            "user": {
                "id": "U_NEW_USER",
                "name": "newuser",
                "profile": {
                    "display_name": "New User",
                    "real_name": "New User Person"
                },
                "is_bot": False
            }
        })
        client_mock.chat_update = AsyncMock(return_value={"ok": True})

        # Act
        with patch('src.handlers.message_handler.get_db') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = test_session
            with patch('src.handlers.message_handler.get_llm_service') as mock_get_service:
                mock_service = Mock()
                mock_service.estimate_tokens = Mock(return_value=10)
                mock_service.max_context_messages = 10
                mock_service.generate_response = AsyncMock(return_value="Hello! How can I help?")
                mock_get_service.return_value = mock_service

                await handle_direct_message(event, say_mock, client_mock)

        # Assert - verify team member was created
        from src.repositories.team_member_repo import TeamMemberRepository
        repo = TeamMemberRepository(test_session)
        member = repo.get_by_slack_id("U_NEW_USER")
        assert member is not None
        assert member.display_name == "New User"
        assert member.real_name == "New User Person"

    @pytest.mark.asyncio
    async def test_handles_slack_api_error_when_fetching_user_info(self, test_session):
        """Test that Slack API errors are handled gracefully when fetching user info."""
        # Arrange
        event = {
            "user": "U_ERROR_USER",
            "text": "test",
            "channel": "D123",
            "ts": "1234.5678"
        }
        say_mock = AsyncMock()
        say_mock.return_value = {"ts": "1234.5679"}

        client_mock = AsyncMock()
        client_mock.users_info = AsyncMock(side_effect=SlackApiError("API error", response={"error": "user_not_found"}))
        client_mock.chat_update = AsyncMock(return_value={"ok": True})

        # Act
        with patch('src.handlers.message_handler.get_db') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = test_session
            with patch('src.handlers.message_handler.get_llm_service') as mock_get_service:
                mock_service = Mock()
                mock_service.estimate_tokens = Mock(return_value=10)
                mock_service.max_context_messages = 10
                mock_service.generate_response = AsyncMock(return_value="Hello!")
                mock_get_service.return_value = mock_service

                await handle_direct_message(event, say_mock, client_mock)

        # Assert - should still create member with fallback display name
        from src.repositories.team_member_repo import TeamMemberRepository
        repo = TeamMemberRepository(test_session)
        member = repo.get_by_slack_id("U_ERROR_USER")
        assert member is not None
        assert "User_" in member.display_name

    @pytest.mark.asyncio
    async def test_stores_user_message_in_database(self, test_session):
        """Test that user message is stored in database."""
        # Arrange - create existing user
        member = TeamMember(
            slack_user_id="U_EXISTING",
            display_name="Existing User",
            is_bot=False
        )
        test_session.add(member)
        test_session.commit()

        event = {
            "user": "U_EXISTING",
            "text": "Test message content",
            "channel": "D123",
            "ts": "1234.5678"
        }
        say_mock = AsyncMock()
        say_mock.return_value = {"ts": "1234.5679"}

        client_mock = AsyncMock()
        client_mock.users_info = AsyncMock(return_value={
            "user": {
                "id": "U_EXISTING",
                "name": "existing",
                "profile": {"display_name": "Existing User"},
                "is_bot": False
            }
        })
        client_mock.chat_update = AsyncMock(return_value={"ok": True})

        # Act
        with patch('src.handlers.message_handler.get_db') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = test_session
            with patch('src.handlers.message_handler.get_llm_service') as mock_get_service:
                mock_service = Mock()
                mock_service.estimate_tokens = Mock(return_value=15)
                mock_service.max_context_messages = 10
                mock_service.generate_response = AsyncMock(return_value="Response")
                mock_get_service.return_value = mock_service

                await handle_direct_message(event, say_mock, client_mock)

        # Assert - verify message was stored
        messages = test_session.query(Message).filter(Message.content == "Test message content").all()
        assert len(messages) > 0
        assert messages[0].sender_type == "user"
        assert messages[0].slack_ts == "1234.5678"

    @pytest.mark.asyncio
    async def test_sends_thinking_placeholder_message(self, test_session):
        """Test that thinking placeholder message is sent for immediate feedback."""
        # Arrange
        event = {
            "user": "U_TEST",
            "text": "Hello",
            "channel": "D123",
            "ts": "1234.5678"
        }
        say_mock = AsyncMock()
        say_mock.return_value = {"ts": "1234.5679"}  # Placeholder ts

        client_mock = AsyncMock()
        client_mock.users_info = AsyncMock(return_value={
            "user": {
                "id": "U_TEST",
                "name": "test",
                "profile": {"display_name": "Test"},
                "is_bot": False
            }
        })
        client_mock.chat_update = AsyncMock(return_value={"ok": True})

        # Act
        with patch('src.handlers.message_handler.get_db') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = test_session
            with patch('src.handlers.message_handler.get_llm_service') as mock_get_service:
                mock_service = Mock()
                mock_service.estimate_tokens = Mock(return_value=10)
                mock_service.max_context_messages = 10
                mock_service.generate_response = AsyncMock(return_value="Actual response")
                mock_get_service.return_value = mock_service

                await handle_direct_message(event, say_mock, client_mock)

        # Assert - verify placeholder was sent
        assert say_mock.call_count >= 1
        first_call = say_mock.call_args_list[0]
        assert "Thinking" in first_call[1]['text'] or "🐻" in first_call[1]['text']

    @pytest.mark.asyncio
    async def test_updates_placeholder_with_actual_response(self, test_session):
        """Test that placeholder message is updated with actual LLM response."""
        # Arrange
        event = {
            "user": "U_TEST",
            "text": "Question",
            "channel": "D123",
            "ts": "1234.5678"
        }
        placeholder_ts = "1234.5679"
        say_mock = AsyncMock()
        say_mock.return_value = {"ts": placeholder_ts}

        client_mock = AsyncMock()
        client_mock.users_info = AsyncMock(return_value={
            "user": {
                "id": "U_TEST",
                "name": "test",
                "profile": {"display_name": "Test"},
                "is_bot": False
            }
        })
        client_mock.chat_update = AsyncMock(return_value={"ok": True})

        # Act
        with patch('src.handlers.message_handler.get_db') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = test_session
            with patch('src.handlers.message_handler.get_llm_service') as mock_get_service:
                mock_service = Mock()
                mock_service.estimate_tokens = Mock(return_value=10)
                mock_service.max_context_messages = 10
                mock_service.generate_response = AsyncMock(return_value="Final answer")
                mock_get_service.return_value = mock_service

                await handle_direct_message(event, say_mock, client_mock)

        # Assert - verify chat_update was called to replace placeholder
        client_mock.chat_update.assert_called_once()
        update_args = client_mock.chat_update.call_args[1]
        assert update_args['ts'] == placeholder_ts
        assert update_args['text'] == "Final answer"

    @pytest.mark.asyncio
    async def test_handles_empty_llm_response(self, test_session):
        """Test that empty LLM responses are handled with fallback message."""
        # Arrange
        event = {
            "user": "U_TEST",
            "text": "test",
            "channel": "D123",
            "ts": "1234.5678"
        }
        say_mock = AsyncMock()
        say_mock.return_value = {"ts": "1234.5679"}

        client_mock = AsyncMock()
        client_mock.users_info = AsyncMock(return_value={
            "user": {
                "id": "U_TEST",
                "name": "test",
                "profile": {"display_name": "Test"},
                "is_bot": False
            }
        })
        client_mock.chat_update = AsyncMock(return_value={"ok": True})

        # Act
        with patch('src.handlers.message_handler.get_db') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = test_session
            with patch('src.handlers.message_handler.get_llm_service') as mock_get_service:
                mock_service = Mock()
                mock_service.estimate_tokens = Mock(return_value=10)
                mock_service.max_context_messages = 10
                mock_service.generate_response = AsyncMock(return_value="")  # Empty response
                mock_get_service.return_value = mock_service

                await handle_direct_message(event, say_mock, client_mock)

        # Assert - verify fallback message was used
        client_mock.chat_update.assert_called_once()
        update_text = client_mock.chat_update.call_args[1]['text']
        assert "trouble processing" in update_text or "try again" in update_text

    @pytest.mark.asyncio
    async def test_increments_user_message_count(self, test_session):
        """Test that user's message count is incremented after successful response."""
        # Arrange
        member = TeamMember(
            slack_user_id="U_COUNT_TEST",
            display_name="Count Test",
            is_bot=False,
            total_messages_sent=5  # Starting count
        )
        test_session.add(member)
        test_session.commit()

        event = {
            "user": "U_COUNT_TEST",
            "text": "test",
            "channel": "D123",
            "ts": "1234.5678"
        }
        say_mock = AsyncMock()
        say_mock.return_value = {"ts": "1234.5679"}

        client_mock = AsyncMock()
        client_mock.users_info = AsyncMock(return_value={
            "user": {
                "id": "U_COUNT_TEST",
                "name": "counttest",
                "profile": {"display_name": "Count Test"},
                "is_bot": False
            }
        })
        client_mock.chat_update = AsyncMock(return_value={"ok": True})

        # Act
        with patch('src.handlers.message_handler.get_db') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = test_session
            with patch('src.handlers.message_handler.get_llm_service') as mock_get_service:
                mock_service = Mock()
                mock_service.estimate_tokens = Mock(return_value=10)
                mock_service.max_context_messages = 10
                mock_service.generate_response = AsyncMock(return_value="Response")
                mock_get_service.return_value = mock_service

                await handle_direct_message(event, say_mock, client_mock)

        # Assert - verify message count incremented
        test_session.refresh(member)
        assert member.total_messages_sent == 6

    @pytest.mark.asyncio
    async def test_handles_sync_llm_service(self, test_session):
        """Test that synchronous LLM service generate_response is handled correctly."""
        # Arrange
        event = {
            "user": "U_SYNC",
            "text": "test",
            "channel": "D123",
            "ts": "1234.5678"
        }
        say_mock = AsyncMock()
        say_mock.return_value = {"ts": "1234.5679"}

        client_mock = AsyncMock()
        client_mock.users_info = AsyncMock(return_value={
            "user": {
                "id": "U_SYNC",
                "name": "sync",
                "profile": {"display_name": "Sync User"},
                "is_bot": False
            }
        })
        client_mock.chat_update = AsyncMock(return_value={"ok": True})

        # Act
        with patch('src.handlers.message_handler.get_db') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = test_session
            with patch('src.handlers.message_handler.get_llm_service') as mock_get_service:
                mock_service = Mock()
                mock_service.estimate_tokens = Mock(return_value=10)
                mock_service.max_context_messages = 10
                # Sync function (not async)
                mock_service.generate_response = Mock(return_value="Sync response")
                mock_get_service.return_value = mock_service

                await handle_direct_message(event, say_mock, client_mock)

        # Assert - verify sync service was called and worked
        mock_service.generate_response.assert_called_once()
        client_mock.chat_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_sends_error_message_on_exception(self, test_session):
        """Test that error message is sent to user when exception occurs."""
        # Arrange
        event = {
            "user": "U_ERROR",
            "text": "test",
            "channel": "D123",
            "ts": "1234.5678"
        }
        say_mock = AsyncMock()
        client_mock = AsyncMock()

        # Act
        with patch('src.handlers.message_handler.get_db') as mock_get_db:
            mock_get_db.side_effect = Exception("Database error")

            await handle_direct_message(event, say_mock, client_mock)

        # Assert - should send error message
        say_mock.assert_called()
        # Check if error message was sent
        assert any("trouble" in str(call).lower() for call in say_mock.call_args_list)


# ===== HANDLE_APP_MENTION TESTS =====


class TestHandleAppMentionInMessageHandler:
    """Test handle_app_mention function in message_handler."""

    @pytest.mark.asyncio
    async def test_responds_in_thread(self, test_session):
        """Test that app mention responses are sent in thread."""
        # Arrange
        event = {
            "user": "U_THREAD",
            "text": "<@U_BOT> help",
            "channel": "C123",
            "ts": "1234.5678",
            "thread_ts": "1234.0000"  # In a thread
        }
        say_mock = AsyncMock()
        say_mock.return_value = {"ts": "1234.5679"}

        client_mock = AsyncMock()
        client_mock.users_info = AsyncMock(return_value={
            "user": {
                "id": "U_THREAD",
                "name": "thread",
                "profile": {"display_name": "Thread User"},
                "is_bot": False
            }
        })
        client_mock.chat_update = AsyncMock(return_value={"ok": True})

        # Act
        with patch('src.handlers.message_handler.get_db') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = test_session
            with patch('src.handlers.message_handler.get_llm_service') as mock_get_service:
                mock_service = Mock()
                mock_service.estimate_tokens = Mock(return_value=10)
                mock_service.max_context_messages = 10
                mock_service.generate_response = AsyncMock(return_value="Thread response")
                mock_get_service.return_value = mock_service

                await handle_app_mention(event, say_mock, client_mock)

        # Assert - verify response was sent with thread_ts
        assert say_mock.call_count >= 1
        # Check if any call included thread_ts
        assert any('thread_ts' in str(call) for call in say_mock.call_args_list)

    @pytest.mark.asyncio
    async def test_creates_thread_conversation_session(self, test_session):
        """Test that thread-based conversation session is created."""
        # Arrange
        event = {
            "user": "U_THREAD_CONV",
            "text": "test",
            "channel": "C123",
            "ts": "1234.5678",
            "thread_ts": "1234.0000"
        }
        say_mock = AsyncMock()
        say_mock.return_value = {"ts": "1234.5679"}

        client_mock = AsyncMock()
        client_mock.users_info = AsyncMock(return_value={
            "user": {
                "id": "U_THREAD_CONV",
                "name": "threadconv",
                "profile": {"display_name": "Thread Conv"},
                "is_bot": False
            }
        })
        client_mock.chat_update = AsyncMock(return_value={"ok": True})

        # Act
        with patch('src.handlers.message_handler.get_db') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = test_session
            with patch('src.handlers.message_handler.get_llm_service') as mock_get_service:
                mock_service = Mock()
                mock_service.estimate_tokens = Mock(return_value=10)
                mock_service.max_context_messages = 10
                mock_service.generate_response = AsyncMock(return_value="Response")
                mock_get_service.return_value = mock_service

                await handle_app_mention(event, say_mock, client_mock)

        # Assert - verify thread conversation was created
        conversations = test_session.query(ConversationSession).filter(
            ConversationSession.channel_type == "thread"
        ).all()
        assert len(conversations) > 0
        assert conversations[0].thread_ts == "1234.0000"


# ===== REGISTER_MESSAGE_HANDLERS TESTS =====


class TestRegisterMessageHandlers:
    """Test register_message_handlers function."""

    def test_registers_direct_message_handler(self):
        """Test that DM message handler is registered."""
        # Arrange
        mock_app = Mock()
        event_calls = []

        def capture_event(event, matchers=None):
            event_calls.append((event, matchers))
            return lambda f: f

        mock_app.event = capture_event

        # Act
        register_message_handlers(mock_app)

        # Assert - verify message event was registered with DM matcher
        assert any(call[0] == "message" for call in event_calls)
        # Verify matcher was provided
        message_events = [call for call in event_calls if call[0] == "message"]
        assert len(message_events) > 0
        assert message_events[0][1] is not None  # Has matchers

    def test_registers_app_mention_handler(self):
        """Test that app_mention handler is registered."""
        # Arrange
        mock_app = Mock()
        event_calls = []

        def capture_event(event, matchers=None):
            event_calls.append((event, matchers))
            return lambda f: f

        mock_app.event = capture_event

        # Act
        register_message_handlers(mock_app)

        # Assert - verify app_mention event was registered
        assert any(call[0] == "app_mention" for call in event_calls)

    @pytest.mark.asyncio
    async def test_dm_matcher_function_returns_true_for_dms(self):
        """Test that DM matcher correctly identifies direct messages."""
        # Arrange
        mock_app = Mock()
        registered_matchers = []

        def capture_event(event, matchers=None):
            if matchers:
                registered_matchers.extend(matchers)
            return lambda f: f

        mock_app.event = capture_event

        # Act
        register_message_handlers(mock_app)

        # Assert - test the matcher
        if registered_matchers:
            matcher = registered_matchers[0]
            dm_event = {"channel_type": "im"}
            channel_event = {"channel_type": "channel"}

            # Matcher should be async
            assert await matcher(dm_event) == True
            assert await matcher(channel_event) == False

    def test_logs_successful_registration(self):
        """Test that successful registration is logged."""
        # Arrange
        mock_app = Mock()
        mock_app.event = Mock(return_value=lambda f: f)

        # Act
        with patch('src.handlers.message_handler.logger') as mock_logger:
            register_message_handlers(mock_app)

            # Assert - verify logging
            mock_logger.info.assert_called()
            call_text = str(mock_logger.info.call_args)
            assert "Message handlers registered" in call_text
