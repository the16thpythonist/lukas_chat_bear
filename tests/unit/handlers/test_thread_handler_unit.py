"""
Unit tests for ThreadHandler class.

Tests thread monitoring, engagement decisions, and response generation.
Note: Integration tests exist in tests/integration/handlers/test_thread_handler_integration.py
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from src.handlers.thread_handler import ThreadHandler
from src.models.engagement_event import EngagementEvent
from src.models.team_member import TeamMember


# ===== INITIALIZATION TESTS =====


class TestThreadHandlerInit:
    """Test ThreadHandler initialization."""

    def test_initializes_with_required_dependencies(self, test_session):
        """Test that ThreadHandler initializes with app and db_session."""
        # Arrange
        mock_app = Mock()

        # Act
        handler = ThreadHandler(app=mock_app, db_session=test_session)

        # Assert
        assert handler.app == mock_app
        assert handler.db == test_session
        assert handler.engagement_service is not None
        assert handler.persona_service is not None
        assert handler.config_repo is not None
        assert handler.team_member_repo is not None
        assert handler.conversation_repo is not None

    def test_accepts_optional_service_dependencies(self, test_session):
        """Test that optional service dependencies can be injected."""
        # Arrange
        mock_app = Mock()
        mock_engagement = Mock()
        mock_persona = Mock()
        mock_config_repo = Mock()

        # Act
        handler = ThreadHandler(
            app=mock_app,
            db_session=test_session,
            engagement_service=mock_engagement,
            persona_service=mock_persona,
            config_repo=mock_config_repo
        )

        # Assert
        assert handler.engagement_service == mock_engagement
        assert handler.persona_service == mock_persona
        assert handler.config_repo == mock_config_repo

    def test_initializes_channel_cache(self, test_session):
        """Test that channel cache is initialized as empty dict."""
        # Arrange
        mock_app = Mock()

        # Act
        handler = ThreadHandler(app=mock_app, db_session=test_session)

        # Assert
        assert isinstance(handler._channel_cache, dict)
        assert len(handler._channel_cache) == 0


# ===== IS_CHANNEL_MONITORED TESTS =====


class TestIsChannelMonitored:
    """Test is_channel_monitored method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_no_monitored_channels_configured(self, test_session):
        """Test that all channels are monitored when monitored_channels is empty."""
        # Arrange
        mock_app = Mock()
        handler = ThreadHandler(app=mock_app, db_session=test_session)

        with patch('src.handlers.thread_handler.config') as mock_config:
            mock_config.get.return_value = {"engagement": {"monitored_channels": []}}

            # Act
            result = await handler.is_channel_monitored("C123")

            # Assert
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_when_channel_id_in_monitored_list(self, test_session):
        """Test that channel is monitored when its ID is in the list."""
        # Arrange
        mock_app = Mock()
        handler = ThreadHandler(app=mock_app, db_session=test_session)

        with patch('src.handlers.thread_handler.config') as mock_config:
            mock_config.get.return_value = {"engagement": {"monitored_channels": ["C123", "C456"]}}

            # Act
            result = await handler.is_channel_monitored("C123")

            # Assert
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_when_channel_name_in_monitored_list(self, test_session):
        """Test that channel is monitored when its name is in the list."""
        # Arrange
        mock_app = AsyncMock()
        mock_app.client.conversations_info = AsyncMock(return_value={
            "channel": {"name": "general"}
        })
        handler = ThreadHandler(app=mock_app, db_session=test_session)

        with patch('src.handlers.thread_handler.config') as mock_config:
            mock_config.get.return_value = {"engagement": {"monitored_channels": ["#general"]}}

            # Act
            result = await handler.is_channel_monitored("C_GENERAL")

            # Assert
            assert result is True
            # Verify cache was updated
            assert handler._channel_cache["#general"] == "C_GENERAL"

    @pytest.mark.asyncio
    async def test_returns_false_when_channel_not_in_monitored_list(self, test_session):
        """Test that channel is not monitored when not in the list."""
        # Arrange
        mock_app = AsyncMock()
        mock_app.client.conversations_info = AsyncMock(return_value={
            "channel": {"name": "random"}
        })
        handler = ThreadHandler(app=mock_app, db_session=test_session)

        with patch('src.handlers.thread_handler.config') as mock_config:
            mock_config.get.return_value = {"engagement": {"monitored_channels": ["#general", "#dev"]}}

            # Act
            result = await handler.is_channel_monitored("C_RANDOM")

            # Assert
            assert result is False

    @pytest.mark.asyncio
    async def test_defaults_to_true_on_error(self, test_session):
        """Test that monitoring defaults to True when error occurs (fail open)."""
        # Arrange
        mock_app = Mock()
        handler = ThreadHandler(app=mock_app, db_session=test_session)

        with patch('src.handlers.thread_handler.config') as mock_config:
            mock_config.get.side_effect = Exception("Config error")

            # Act
            result = await handler.is_channel_monitored("C123")

            # Assert
            assert result is True  # Fail open


# ===== SHOULD_ENGAGE_WITH_THREAD TESTS =====


class TestShouldEngageWithThread:
    """Test should_engage_with_thread decision logic."""

    def test_returns_false_when_already_engaged(self, test_session):
        """Test that engagement is skipped for threads already engaged with."""
        # Arrange
        mock_app = Mock()
        handler = ThreadHandler(app=mock_app, db_session=test_session)

        # Create existing engagement event
        event = EngagementEvent(
            channel_id="C123",
            thread_ts="1234.5678",
            event_type="thread_response",
            decision_probability=0.5,
            random_value=0.3,
            engaged=True,
            timestamp=datetime.now()
        )
        test_session.add(event)
        test_session.commit()

        # Act
        should_engage, prob, rand_val = handler.should_engage_with_thread(
            channel_id="C123",
            thread_ts="1234.5678"
        )

        # Assert
        assert should_engage is False
        assert prob == 0.0

    def test_returns_false_when_outside_active_hours(self, test_session):
        """Test that engagement is skipped outside active hours."""
        # Arrange
        mock_app = Mock()
        mock_engagement = Mock()
        mock_engagement.get_active_hours.return_value = (9, 17, "UTC")  # 9am-5pm
        mock_engagement.is_within_active_hours.return_value = False  # Outside hours
        handler = ThreadHandler(
            app=mock_app,
            db_session=test_session,
            engagement_service=mock_engagement
        )

        # Act
        should_engage, prob, rand_val = handler.should_engage_with_thread(
            channel_id="C123",
            thread_ts="1234.5678"
        )

        # Assert
        assert should_engage is False

    def test_returns_false_when_thread_too_active(self, test_session):
        """Test that engagement is skipped when thread has too many messages."""
        # Arrange
        mock_app = Mock()
        mock_engagement = Mock()
        mock_engagement.get_active_hours.return_value = (0, 24, "UTC")
        mock_engagement.is_within_active_hours.return_value = True
        mock_engagement.is_thread_too_active.return_value = True  # Too many messages
        handler = ThreadHandler(
            app=mock_app,
            db_session=test_session,
            engagement_service=mock_engagement
        )

        # Act
        should_engage, prob, rand_val = handler.should_engage_with_thread(
            channel_id="C123",
            thread_ts="1234.5678",
            message_count=50  # High count
        )

        # Assert
        assert should_engage is False

    def test_returns_true_when_probability_check_passes(self, test_session):
        """Test that engagement proceeds when all checks pass and probability succeeds."""
        # Arrange
        mock_app = Mock()
        mock_engagement = Mock()
        mock_engagement.get_active_hours.return_value = (0, 24, "UTC")
        mock_engagement.is_within_active_hours.return_value = True
        mock_engagement.is_thread_too_active.return_value = False
        mock_engagement.get_engagement_probability.return_value = 0.8
        mock_engagement.should_engage.return_value = True  # Probability check passed
        handler = ThreadHandler(
            app=mock_app,
            db_session=test_session,
            engagement_service=mock_engagement
        )

        # Act
        should_engage, prob, rand_val = handler.should_engage_with_thread(
            channel_id="C123",
            thread_ts="1234.5678"
        )

        # Assert
        assert should_engage is True
        assert prob == 0.8

    def test_returns_false_when_probability_check_fails(self, test_session):
        """Test that engagement is skipped when probability check fails."""
        # Arrange
        mock_app = Mock()
        mock_engagement = Mock()
        mock_engagement.get_active_hours.return_value = (0, 24, "UTC")
        mock_engagement.is_within_active_hours.return_value = True
        mock_engagement.is_thread_too_active.return_value = False
        mock_engagement.get_engagement_probability.return_value = 0.1
        mock_engagement.should_engage.return_value = False  # Probability check failed
        handler = ThreadHandler(
            app=mock_app,
            db_session=test_session,
            engagement_service=mock_engagement
        )

        # Act
        should_engage, prob, rand_val = handler.should_engage_with_thread(
            channel_id="C123",
            thread_ts="1234.5678"
        )

        # Assert
        assert should_engage is False
        assert prob == 0.1


# ===== EXTRACT_THREAD_CONTEXT TESTS =====


class TestExtractThreadContext:
    """Test extract_thread_context method."""

    def test_returns_empty_string_for_no_messages(self, test_session):
        """Test that empty string is returned when no messages provided."""
        # Arrange
        mock_app = Mock()
        handler = ThreadHandler(app=mock_app, db_session=test_session)

        # Act
        context = handler.extract_thread_context([])

        # Assert
        assert context == ""

    def test_formats_messages_with_user_and_text(self, test_session):
        """Test that messages are formatted correctly."""
        # Arrange
        mock_app = Mock()
        handler = ThreadHandler(app=mock_app, db_session=test_session)

        messages = [
            {"user": "U123", "text": "First message"},
            {"user": "U456", "text": "Second message"}
        ]

        # Act
        context = handler.extract_thread_context(messages)

        # Assert
        assert "<U123>: First message" in context
        assert "<U456>: Second message" in context

    def test_limits_to_last_5_messages(self, test_session):
        """Test that only last 5 messages are included in context."""
        # Arrange
        mock_app = Mock()
        handler = ThreadHandler(app=mock_app, db_session=test_session)

        messages = [
            {"user": f"U{i}", "text": f"Message {i}"}
            for i in range(10)
        ]

        # Act
        context = handler.extract_thread_context(messages)

        # Assert - should only have last 5
        assert "Message 5" in context
        assert "Message 9" in context
        assert "Message 0" not in context
        assert "Message 4" not in context

    def test_handles_missing_user_field(self, test_session):
        """Test that missing user field is handled gracefully."""
        # Arrange
        mock_app = Mock()
        handler = ThreadHandler(app=mock_app, db_session=test_session)

        messages = [
            {"text": "Message without user"}
        ]

        # Act
        context = handler.extract_thread_context(messages)

        # Assert
        assert "unknown" in context
        assert "Message without user" in context


# ===== HANDLE_THREAD_MESSAGE TESTS =====


class TestHandleThreadMessage:
    """Test handle_thread_message method."""

    @pytest.mark.asyncio
    async def test_fetches_thread_history(self, test_session):
        """Test that thread history is fetched from Slack API."""
        # Arrange
        mock_app = AsyncMock()
        mock_app.client.conversations_replies = AsyncMock(return_value={
            "messages": [
                {"user": "U1", "text": "msg1"},
                {"user": "U2", "text": "msg2"}
            ]
        })
        mock_engagement = Mock()
        mock_engagement.get_active_hours.return_value = (0, 24, "UTC")
        mock_engagement.is_within_active_hours.return_value = True
        mock_engagement.is_thread_too_active.return_value = False
        mock_engagement.get_engagement_probability.return_value = 0.5
        mock_engagement.should_engage.return_value = False
        handler = ThreadHandler(
            app=mock_app,
            db_session=test_session,
            engagement_service=mock_engagement
        )

        # Act
        await handler.handle_thread_message(
            channel_id="C123",
            thread_ts="1234.5678",
            message_text="new message",
            user_id="U3",
            message_ts="1234.6789"
        )

        # Assert
        mock_app.client.conversations_replies.assert_called_once_with(
            channel="C123",
            ts="1234.5678",
            limit=20
        )

    @pytest.mark.asyncio
    async def test_creates_engagement_event_when_not_engaging(self, test_session):
        """Test that engagement event is created even when not engaging."""
        # Arrange
        mock_app = AsyncMock()
        mock_app.client.conversations_replies = AsyncMock(return_value={
            "messages": [{"user": "U1", "text": "msg"}]
        })
        mock_engagement = Mock()
        mock_engagement.get_active_hours.return_value = (0, 24, "UTC")
        mock_engagement.is_within_active_hours.return_value = True
        mock_engagement.is_thread_too_active.return_value = False
        mock_engagement.get_engagement_probability.return_value = 0.1
        mock_engagement.should_engage.return_value = False  # Not engaging
        handler = ThreadHandler(
            app=mock_app,
            db_session=test_session,
            engagement_service=mock_engagement
        )

        # Act
        result = await handler.handle_thread_message(
            channel_id="C123",
            thread_ts="1234.5678",
            message_text="test",
            user_id="U1",
            message_ts="1234.6789"
        )

        # Assert
        assert result is None
        # Verify event was created
        events = test_session.query(EngagementEvent).all()
        assert len(events) == 1
        assert events[0].engaged is False
        assert events[0].event_type == "ignored"

    @pytest.mark.asyncio
    async def test_generates_response_when_engaging(self, test_session):
        """Test that response is generated when engagement decision is True."""
        # Arrange
        mock_app = AsyncMock()
        mock_app.client.conversations_replies = AsyncMock(return_value={
            "messages": [{"user": "U1", "text": "msg"}]
        })
        mock_engagement = Mock()
        mock_engagement.get_active_hours.return_value = (0, 24, "UTC")
        mock_engagement.is_within_active_hours.return_value = True
        mock_engagement.is_thread_too_active.return_value = False
        mock_engagement.get_engagement_probability.return_value = 0.9
        mock_engagement.should_engage.return_value = True  # Engaging!
        handler = ThreadHandler(
            app=mock_app,
            db_session=test_session,
            engagement_service=mock_engagement
        )

        with patch.object(handler, '_generate_thread_response', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = "Generated response"

            # Act
            result = await handler.handle_thread_message(
                channel_id="C123",
                thread_ts="1234.5678",
                message_text="test",
                user_id="U1",
                message_ts="1234.6789"
            )

            # Assert
            assert result == "Generated response"
            mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self, test_session):
        """Test that None is returned when exception occurs."""
        # Arrange
        mock_app = AsyncMock()
        mock_app.client.conversations_replies = AsyncMock(side_effect=Exception("API error"))
        handler = ThreadHandler(app=mock_app, db_session=test_session)

        # Act
        result = await handler.handle_thread_message(
            channel_id="C123",
            thread_ts="1234.5678",
            message_text="test",
            user_id="U1",
            message_ts="1234.6789"
        )

        # Assert
        assert result is None


# ===== SELECT_EMOJI_VIA_LLM TESTS =====


class TestSelectEmojiViaLlm:
    """Test _select_emoji_via_llm method."""

    @pytest.mark.asyncio
    async def test_uses_engagement_service_for_available_emojis(self, test_session):
        """Test that available emojis are fetched from engagement service."""
        # Arrange
        mock_app = Mock()
        mock_engagement = Mock()
        mock_engagement.get_available_emojis.return_value = ["heart", "thumbsup", "bear"]
        handler = ThreadHandler(
            app=mock_app,
            db_session=test_session,
            engagement_service=mock_engagement
        )

        with patch('src.services.llm_service.llm_service') as mock_llm:
            mock_llm.generate_response.return_value = "heart"

            # Act
            emoji = await handler._select_emoji_via_llm("Great work!")

            # Assert
            mock_engagement.get_available_emojis.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_llm_selected_emoji_when_valid(self, test_session):
        """Test that LLM-selected emoji is returned when it's in available list."""
        # Arrange
        mock_app = Mock()
        mock_engagement = Mock()
        mock_engagement.get_available_emojis.return_value = ["heart", "thumbsup", "bear"]
        handler = ThreadHandler(
            app=mock_app,
            db_session=test_session,
            engagement_service=mock_engagement
        )

        with patch('src.services.llm_service.llm_service') as mock_llm:
            mock_llm.generate_response.return_value = "heart"

            # Act
            emoji = await handler._select_emoji_via_llm("Great work!")

            # Assert
            assert emoji == "heart"

    @pytest.mark.asyncio
    async def test_returns_bear_fallback_when_llm_selects_invalid_emoji(self, test_session):
        """Test that 'bear' fallback is used when LLM selects invalid emoji."""
        # Arrange
        mock_app = Mock()
        mock_engagement = Mock()
        mock_engagement.get_available_emojis.return_value = ["heart", "thumbsup", "bear"]
        handler = ThreadHandler(
            app=mock_app,
            db_session=test_session,
            engagement_service=mock_engagement
        )

        with patch('src.services.llm_service.llm_service') as mock_llm:
            mock_llm.generate_response.return_value = "invalid_emoji_not_in_list"

            # Act
            emoji = await handler._select_emoji_via_llm("Test message")

            # Assert
            assert emoji == "bear"

    @pytest.mark.asyncio
    async def test_truncates_long_messages(self, test_session):
        """Test that long messages are truncated before sending to LLM."""
        # Arrange
        mock_app = Mock()
        mock_engagement = Mock()
        mock_engagement.get_available_emojis.return_value = ["heart"]
        handler = ThreadHandler(
            app=mock_app,
            db_session=test_session,
            engagement_service=mock_engagement
        )

        long_message = "x" * 500  # 500 character message

        with patch('src.services.llm_service.llm_service') as mock_llm:
            mock_llm.generate_response.return_value = "heart"

            # Act
            await handler._select_emoji_via_llm(long_message)

            # Assert - verify message was truncated in prompt
            call_args = mock_llm.generate_response.call_args[1]['user_message']
            assert len(long_message[:300]) <= 300
            assert long_message[:300] in call_args

    @pytest.mark.asyncio
    async def test_returns_bear_on_exception(self, test_session):
        """Test that 'bear' fallback is returned when exception occurs."""
        # Arrange
        mock_app = Mock()
        mock_engagement = Mock()
        mock_engagement.get_available_emojis.side_effect = Exception("Error")
        handler = ThreadHandler(
            app=mock_app,
            db_session=test_session,
            engagement_service=mock_engagement
        )

        # Act
        emoji = await handler._select_emoji_via_llm("Test")

        # Assert
        assert emoji == "bear"


# ===== HANDLE_TOP_LEVEL_MESSAGE TESTS =====


class TestHandleTopLevelMessage:
    """Test handle_top_level_message method."""

    @pytest.mark.asyncio
    async def test_skips_already_engaged_messages(self, test_session):
        """Test that messages already engaged with are skipped."""
        # Arrange
        mock_app = Mock()
        handler = ThreadHandler(app=mock_app, db_session=test_session)

        # Create existing engagement
        event = EngagementEvent(
            channel_id="C123",
            thread_ts="1234.5678",  # message_ts used as thread_ts for top-level
            event_type="reaction",
            decision_probability=0.5,
            random_value=0.3,
            engaged=True,
            timestamp=datetime.now()
        )
        test_session.add(event)
        test_session.commit()

        # Act
        result = await handler.handle_top_level_message(
            channel_id="C123",
            message_text="test",
            user_id="U1",
            message_ts="1234.5678"
        )

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_makes_independent_reaction_and_text_decisions(self, test_session):
        """Test that reaction and text decisions are independent."""
        # Arrange
        mock_app = AsyncMock()
        mock_app.client.reactions_add = AsyncMock()
        mock_engagement = Mock()
        mock_engagement.get_active_hours.return_value = (0, 24, "UTC")
        mock_engagement.is_within_active_hours.return_value = True
        mock_engagement.should_add_reaction.return_value = True  # React
        mock_engagement.should_respond_with_text.return_value = False  # Don't respond with text
        mock_engagement.get_reaction_probability.return_value = 0.5
        mock_engagement.get_engagement_probability.return_value = 0.5
        handler = ThreadHandler(
            app=mock_app,
            db_session=test_session,
            engagement_service=mock_engagement
        )

        with patch.object(handler, '_select_emoji_via_llm', new_callable=AsyncMock) as mock_emoji:
            mock_emoji.return_value = "thumbsup"

            # Act
            result = await handler.handle_top_level_message(
                channel_id="C123",
                message_text="test",
                user_id="U1",
                message_ts="1234.5678"
            )

            # Assert - reaction was added
            mock_app.client.reactions_add.assert_called_once()
            # But no text response
            assert result is None

    @pytest.mark.asyncio
    async def test_can_do_both_reaction_and_text(self, test_session):
        """Test that both reaction and text can be added to same message."""
        # Arrange
        mock_app = AsyncMock()
        mock_app.client.reactions_add = AsyncMock()
        mock_engagement = Mock()
        mock_engagement.get_active_hours.return_value = (0, 24, "UTC")
        mock_engagement.is_within_active_hours.return_value = True
        mock_engagement.should_add_reaction.return_value = True  # React
        mock_engagement.should_respond_with_text.return_value = True  # Also respond
        mock_engagement.get_reaction_probability.return_value = 0.5
        mock_engagement.get_engagement_probability.return_value = 0.5
        handler = ThreadHandler(
            app=mock_app,
            db_session=test_session,
            engagement_service=mock_engagement
        )

        with patch.object(handler, '_select_emoji_via_llm', new_callable=AsyncMock) as mock_emoji:
            mock_emoji.return_value = "heart"
            with patch.object(handler, '_generate_channel_response', new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = "Great point!"

                # Act
                result = await handler.handle_top_level_message(
                    channel_id="C123",
                    message_text="test",
                    user_id="U1",
                    message_ts="1234.5678"
                )

                # Assert - both reaction and text
                mock_app.client.reactions_add.assert_called_once()
                assert result == "Great point!"


# ===== REGISTER_HANDLERS TESTS =====


class TestRegisterHandlers:
    """Test register_handlers method."""

    def test_registers_message_event_handler(self, test_session):
        """Test that message event handler is registered."""
        # Arrange
        mock_app = Mock()
        registered_events = []

        def capture_event(event_name):
            registered_events.append(event_name)
            return lambda f: f

        mock_app.event = capture_event
        handler = ThreadHandler(app=mock_app, db_session=test_session)

        # Act
        handler.register_handlers()

        # Assert
        assert "message" in registered_events

    @pytest.mark.asyncio
    async def test_registered_handler_skips_bot_messages(self, test_session):
        """Test that registered handler skips bot messages."""
        # Arrange
        mock_app = Mock()
        registered_handler = None

        def capture_event(event_name):
            def decorator(func):
                nonlocal registered_handler
                registered_handler = func
                return func
            return decorator

        mock_app.event = capture_event
        handler = ThreadHandler(app=mock_app, db_session=test_session)
        handler.register_handlers()

        # Act - call with bot message
        event = {"bot_id": "B123", "channel": "C123"}
        say_mock = AsyncMock()
        client_mock = Mock()

        await registered_handler(event, say_mock, client_mock)

        # Assert - should not call anything
        say_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_registered_handler_skips_dm_messages(self, test_session):
        """Test that registered handler skips DM messages."""
        # Arrange
        mock_app = Mock()
        registered_handler = None

        def capture_event(event_name):
            def decorator(func):
                nonlocal registered_handler
                registered_handler = func
                return func
            return decorator

        mock_app.event = capture_event
        handler = ThreadHandler(app=mock_app, db_session=test_session)
        handler.register_handlers()

        # Act - call with DM
        event = {"channel_type": "im", "channel": "D123", "user": "U1"}
        say_mock = AsyncMock()
        client_mock = Mock()

        await registered_handler(event, say_mock, client_mock)

        # Assert - should not process DMs
        say_mock.assert_not_called()
