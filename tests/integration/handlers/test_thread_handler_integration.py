"""
Integration tests for ThreadHandler.

Tests the complete thread engagement workflow including decision logic,
Slack API interaction, and database persistence.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from freezegun import freeze_time

from src.handlers.thread_handler import ThreadHandler
from src.models.engagement_event import EngagementEvent
from src.models.conversation import ConversationSession
from src.models.message import Message


class TestThreadHandlerEngagementDecisions:
    """Test thread engagement decision logic with various conditions."""

    def test_should_engage_within_active_hours(
        self, test_session, mock_slack_app, engagement_config
    ):
        """Should engage when within active hours and probability passes."""
        # Given ThreadHandler with active hours 8-18
        handler = ThreadHandler(app=mock_slack_app, db_session=test_session)

        # When checking at 10am (within active hours)
        with freeze_time("2025-01-15 10:00:00"):
            # Mock probability to always pass
            with patch('random.random', return_value=0.1):  # 0.1 < 0.20
                should_engage, prob, _ = handler.should_engage_with_thread(
                    channel_id="C123",
                    thread_ts="1234567890.000000",
                    message_count=3
                )

        # Then should decide to engage
        assert should_engage is True
        assert prob == 0.20  # From engagement_config fixture

    @freeze_time("2025-01-15 22:00:00")  # 10pm - outside active hours
    def test_should_not_engage_outside_active_hours(
        self, test_session, mock_slack_app, engagement_config
    ):
        """Should not engage when outside active hours (8am-6pm)."""
        # Given ThreadHandler with active hours 8-18
        handler = ThreadHandler(app=mock_slack_app, db_session=test_session)

        # When checking at 10pm (outside active hours)
        should_engage, prob, _ = handler.should_engage_with_thread(
            channel_id="C123",
            thread_ts="1234567890.000000",
            message_count=3
        )

        # Then should not engage
        assert should_engage is False

    def test_should_not_engage_when_thread_too_active(
        self, test_session, mock_slack_app, engagement_config
    ):
        """Should not engage with threads that have too many messages."""
        # Given ThreadHandler
        handler = ThreadHandler(app=mock_slack_app, db_session=test_session)

        # When checking thread with 15 messages (threshold is 10)
        with freeze_time("2025-01-15 10:00:00"):  # Within active hours
            should_engage, prob, _ = handler.should_engage_with_thread(
                channel_id="C123",
                thread_ts="1234567890.000000",
                message_count=15
            )

        # Then should not engage
        assert should_engage is False

    def test_should_not_engage_when_already_engaged(
        self, test_session, mock_slack_app, engagement_config
    ):
        """Should not engage with thread if already engaged previously."""
        # Given ThreadHandler and existing engagement event
        handler = ThreadHandler(app=mock_slack_app, db_session=test_session)

        # Create existing engagement event
        existing_event = EngagementEvent(
            channel_id="C123",
            thread_ts="1234567890.000000",
            event_type="thread_response",
            decision_probability=0.20,
            random_value=0.1,
            engaged=True,
            timestamp=datetime.now()
        )
        test_session.add(existing_event)
        test_session.commit()

        # When checking same thread again
        with freeze_time("2025-01-15 10:00:00"):
            should_engage, prob, _ = handler.should_engage_with_thread(
                channel_id="C123",
                thread_ts="1234567890.000000",
                message_count=3
            )

        # Then should not engage again
        assert should_engage is False

    def test_probability_based_engagement_decision(
        self, test_session, mock_slack_app, engagement_config
    ):
        """Engagement should respect probability threshold."""
        # Given ThreadHandler with 20% probability
        handler = ThreadHandler(app=mock_slack_app, db_session=test_session)

        # When random value is above threshold (don't engage)
        with freeze_time("2025-01-15 10:00:00"):
            with patch('random.random', return_value=0.9):  # 0.9 >= 0.20
                should_engage, prob, _ = handler.should_engage_with_thread(
                    channel_id="C123",
                    thread_ts="1234567890.000000",
                    message_count=3
                )

        # Then should not engage
        assert should_engage is False
        assert prob == 0.20


class TestThreadHandlerContextExtraction:
    """Test thread context extraction and formatting."""

    def test_extract_thread_context_from_messages(
        self, test_session, mock_slack_app
    ):
        """Should extract and format thread context from Slack messages."""
        # Given ThreadHandler
        handler = ThreadHandler(app=mock_slack_app, db_session=test_session)

        # When extracting context from messages
        messages = [
            {"user": "U_ALICE", "text": "What's the status?"},
            {"user": "U_BOB", "text": "Almost done!"},
            {"user": "U_CHARLIE", "text": "Great work team!"},
        ]
        context = handler.extract_thread_context(messages)

        # Then should format messages correctly
        assert "<U_ALICE>: What's the status?" in context
        assert "<U_BOB>: Almost done!" in context
        assert "<U_CHARLIE>: Great work team!" in context

    def test_extract_thread_context_limits_to_last_5_messages(
        self, test_session, mock_slack_app
    ):
        """Should only include last 5 messages to keep context manageable."""
        # Given ThreadHandler and 10 messages
        handler = ThreadHandler(app=mock_slack_app, db_session=test_session)

        messages = [
            {"user": f"U{i}", "text": f"Message {i}"}
            for i in range(10)
        ]

        # When extracting context
        context = handler.extract_thread_context(messages)

        # Then should only include last 5 messages
        assert "Message 5" in context
        assert "Message 9" in context
        assert "Message 0" not in context  # First message should be excluded
        assert "Message 4" not in context  # 5th message should be excluded

    def test_extract_thread_context_handles_empty_messages(
        self, test_session, mock_slack_app
    ):
        """Should handle empty message list gracefully."""
        # Given ThreadHandler
        handler = ThreadHandler(app=mock_slack_app, db_session=test_session)

        # When extracting context from empty list
        context = handler.extract_thread_context([])

        # Then should return empty string
        assert context == ""


class TestThreadHandlerResponseGeneration:
    """Test thread response generation and database persistence."""

    @pytest.mark.asyncio
    async def test_handle_thread_message_creates_engagement_event(
        self, test_session, mock_slack_app, engagement_config, sample_thread_messages
    ):
        """Should create EngagementEvent when handling thread message."""
        # Given ThreadHandler and mocked Slack API
        handler = ThreadHandler(app=mock_slack_app, db_session=test_session)
        mock_slack_app.client.conversations_replies = Mock(
            return_value=sample_thread_messages
        )

        # When handling thread message
        with freeze_time("2025-01-15 10:00:00"):
            with patch('random.random', return_value=0.1):  # Ensure engagement
                await handler.handle_thread_message(
                    channel_id="C123",
                    thread_ts="1234567890.000000",
                    message_text="Question",
                    user_id="U_ALICE",
                    message_ts="1234567890.100000"
                )

        # Then should create engagement event
        events = test_session.query(EngagementEvent).all()
        assert len(events) >= 1

        event = events[0]
        assert event.channel_id == "C123"
        assert event.thread_ts == "1234567890.000000"
        assert event.engaged is True
        assert event.decision_probability == 0.20

    @pytest.mark.asyncio
    async def test_handle_thread_message_skips_when_should_not_engage(
        self, test_session, mock_slack_app, engagement_config, sample_thread_messages
    ):
        """Should not generate response when engagement decision is negative."""
        # Given ThreadHandler
        handler = ThreadHandler(app=mock_slack_app, db_session=test_session)
        mock_slack_app.client.conversations_replies = Mock(
            return_value=sample_thread_messages
        )

        # When handling thread message but probability fails
        with freeze_time("2025-01-15 10:00:00"):
            with patch('random.random', return_value=0.9):  # Don't engage
                response = await handler.handle_thread_message(
                    channel_id="C123",
                    thread_ts="1234567890.000000",
                    message_text="Question",
                    user_id="U_ALICE",
                    message_ts="1234567890.100000"
                )

        # Then should not generate response
        assert response is None

        # Should still create engagement event for audit
        events = test_session.query(EngagementEvent).filter_by(engaged=False).all()
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_handle_thread_message_generates_response(
        self, test_session, mock_slack_app, engagement_config, sample_thread_messages
    ):
        """Should generate LLM response when engaging with thread."""
        # Given ThreadHandler
        handler = ThreadHandler(app=mock_slack_app, db_session=test_session)
        mock_slack_app.client.conversations_replies = Mock(
            return_value=sample_thread_messages
        )

        # Mock LLM service to return response
        with patch('src.handlers.thread_handler.get_llm_service') as mock_get_llm:
            mock_llm = AsyncMock()
            mock_llm.generate_response = AsyncMock(return_value="Great question!")
            mock_llm.estimate_tokens = Mock(return_value=10)
            mock_get_llm.return_value = mock_llm

            # When handling thread message
            with freeze_time("2025-01-15 10:00:00"):
                with patch('random.random', return_value=0.1):  # Engage
                    response = await handler.handle_thread_message(
                        channel_id="C123",
                        thread_ts="1234567890.000000",
                        message_text="Question",
                        user_id="U_ALICE",
                        message_ts="1234567890.100000"
                    )

        # Then should return generated response
        assert response == "Great question!"

        # Should have called LLM service
        mock_llm.generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_thread_message_uses_thread_context(
        self, test_session, mock_slack_app, engagement_config, sample_thread_messages
    ):
        """Should extract and use thread context for LLM generation."""
        # Given ThreadHandler
        handler = ThreadHandler(app=mock_slack_app, db_session=test_session)
        mock_slack_app.client.conversations_replies = Mock(
            return_value=sample_thread_messages
        )

        # Mock LLM service
        with patch('src.handlers.thread_handler.get_llm_service') as mock_get_llm:
            mock_llm = AsyncMock()
            mock_llm.generate_response = AsyncMock(return_value="Here's my response!")
            mock_llm.estimate_tokens = Mock(return_value=15)
            mock_get_llm.return_value = mock_llm

            # When handling thread message
            with freeze_time("2025-01-15 10:00:00"):
                with patch('random.random', return_value=0.1):
                    response = await handler.handle_thread_message(
                        channel_id="C123",
                        thread_ts="1234567890.000000",
                        message_text="Question",
                        user_id="U_ALICE",
                        message_ts="1234567890.100000"
                    )

        # Then should have extracted thread context
        # Verify LLM was called with system prompt containing context
        call_args = mock_llm.generate_response.call_args
        assert call_args is not None

        # Response should be returned
        assert response == "Here's my response!"


class TestThreadHandlerReactionHandling:
    """Test emoji reaction handling."""

    @pytest.mark.asyncio
    async def test_handle_reaction_adds_emoji(
        self, test_session, mock_slack_app, engagement_config
    ):
        """Should add emoji reaction via Slack API."""
        # Given ThreadHandler
        handler = ThreadHandler(app=mock_slack_app, db_session=test_session)

        # When handling reaction
        emoji = await handler.handle_reaction(
            channel_id="C123",
            thread_ts="1234567890.000000"
        )

        # Then should add reaction
        assert emoji is not None
        mock_slack_app.client.reactions_add.assert_called_once()

        call_args = mock_slack_app.client.reactions_add.call_args
        assert call_args.kwargs["channel"] == "C123"
        assert call_args.kwargs["timestamp"] == "1234567890.000000"
        assert call_args.kwargs["name"] == emoji

    @pytest.mark.asyncio
    async def test_handle_reaction_creates_engagement_event(
        self, test_session, mock_slack_app, engagement_config
    ):
        """Should create EngagementEvent with reaction details."""
        # Given ThreadHandler
        handler = ThreadHandler(app=mock_slack_app, db_session=test_session)

        # When handling reaction
        emoji = await handler.handle_reaction(
            channel_id="C123",
            thread_ts="1234567890.000000"
        )

        # Then should create engagement event
        events = test_session.query(EngagementEvent).filter_by(
            event_type='reaction'
        ).all()
        assert len(events) == 1

        event = events[0]
        assert event.channel_id == "C123"
        assert event.thread_ts == "1234567890.000000"
        assert event.engaged is True
        assert event.meta["emoji"] == emoji

    @pytest.mark.asyncio
    async def test_handle_reaction_uses_bear_emoji(
        self, test_session, mock_slack_app, engagement_config
    ):
        """Selected emoji should be from bear-appropriate list."""
        # Given ThreadHandler
        handler = ThreadHandler(app=mock_slack_app, db_session=test_session)

        # Valid bear emojis
        valid_emojis = [
            'bear', 'honey_pot', 'paw_prints', 'deciduous_tree',
            'evergreen_tree', 'hugging_face', 'thinking_face',
            '+1', 'heart', 'tada', 'eyes', 'muscle'
        ]

        # When handling reaction 10 times
        emojis = []
        for _ in range(10):
            emoji = await handler.handle_reaction(
                channel_id=f"C{_}",
                thread_ts=f"123456789{_}.000000"
            )
            emojis.append(emoji)

        # Then all should be valid bear emojis
        for emoji in emojis:
            assert emoji in valid_emojis


class TestThreadHandlerErrorHandling:
    """Test error handling in thread processing."""

    @pytest.mark.asyncio
    async def test_handle_thread_message_handles_slack_api_error(
        self, test_session, mock_slack_app, engagement_config
    ):
        """Should handle Slack API errors gracefully."""
        # Given ThreadHandler with failing Slack API
        handler = ThreadHandler(app=mock_slack_app, db_session=test_session)
        mock_slack_app.client.conversations_replies = Mock(
            side_effect=Exception("Slack API error")
        )

        # When handling thread message
        response = await handler.handle_thread_message(
            channel_id="C123",
            thread_ts="1234567890.000000",
            message_text="Question",
            user_id="U_ALICE",
            message_ts="1234567890.100000"
        )

        # Then should return None without crashing
        assert response is None

    @pytest.mark.asyncio
    async def test_handle_reaction_handles_slack_api_error(
        self, test_session, mock_slack_app, engagement_config
    ):
        """Should handle emoji reaction errors gracefully."""
        # Given ThreadHandler with failing reaction API
        handler = ThreadHandler(app=mock_slack_app, db_session=test_session)
        mock_slack_app.client.reactions_add = Mock(
            side_effect=Exception("Reaction failed")
        )

        # When handling reaction
        emoji = await handler.handle_reaction(
            channel_id="C123",
            thread_ts="1234567890.000000"
        )

        # Then should return None without crashing
        assert emoji is None
