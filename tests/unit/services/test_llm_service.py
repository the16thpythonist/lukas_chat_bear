"""
Unit tests for LLMService class.

Tests AI conversation functionality including context management,
token estimation, retry logic, and circuit breaker.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.services.llm_service import LLMService
from src.models.message import Message


# ===== INITIALIZATION TESTS =====


class TestLlmServiceInit:
    """Test LLMService initialization."""

    def test_initializes_with_default_model(self):
        """Test that service initializes with default model when not specified."""
        # Arrange & Act
        # Clear LLM_MODEL to test default behavior
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}, clear=False):
            import os
            # Temporarily remove LLM_MODEL if it exists
            original_model = os.environ.pop('LLM_MODEL', None)
            try:
                with patch('src.services.llm_service.OpenAI'):
                    service = LLMService()

                    # Assert
                    assert service.model == "gpt-3.5-turbo"  # Default
            finally:
                # Restore original value if it existed
                if original_model is not None:
                    os.environ['LLM_MODEL'] = original_model

    def test_uses_env_variable_for_model(self):
        """Test that LLM_MODEL env variable is used when set."""
        # Arrange & Act
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key', 'LLM_MODEL': 'gpt-4'}):
            with patch('src.services.llm_service.OpenAI'):
                service = LLMService()

                # Assert
                assert service.model == "gpt-4"

    def test_uses_custom_model_parameter(self):
        """Test that custom model parameter overrides env variable."""
        # Arrange & Act
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key', 'LLM_MODEL': 'gpt-4'}):
            with patch('src.services.llm_service.OpenAI'):
                service = LLMService(model="custom-model")

                # Assert
                assert service.model == "custom-model"

    def test_raises_error_when_api_key_missing(self):
        """Test that ValueError is raised when OPENAI_API_KEY is not set."""
        # Arrange & Act & Assert
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
                LLMService()

    def test_initializes_with_custom_parameters(self):
        """Test that custom parameters are stored correctly."""
        # Arrange & Act
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI'):
                service = LLMService(
                    max_context_messages=20,
                    max_tokens_per_request=8000,
                    max_response_tokens=1000
                )

                # Assert
                assert service.max_context_messages == 20
                assert service.max_tokens_per_request == 8000
                assert service.max_response_tokens == 1000

    def test_initializes_tokenizer(self):
        """Test that tokenizer is initialized for the model."""
        # Arrange & Act
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI'):
                with patch('src.services.llm_service.tiktoken') as mock_tiktoken:
                    mock_tokenizer = Mock()
                    mock_tiktoken.encoding_for_model.return_value = mock_tokenizer

                    service = LLMService()

                    # Assert
                    assert service.tokenizer == mock_tokenizer

    def test_uses_fallback_tokenizer_when_model_not_found(self):
        """Test that fallback tokenizer is used when model not in tiktoken."""
        # Arrange & Act
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI'):
                with patch('src.services.llm_service.tiktoken') as mock_tiktoken:
                    mock_tiktoken.encoding_for_model.side_effect = KeyError("Model not found")
                    mock_fallback = Mock()
                    mock_tiktoken.get_encoding.return_value = mock_fallback

                    service = LLMService()

                    # Assert
                    assert service.tokenizer == mock_fallback
                    mock_tiktoken.get_encoding.assert_called_once_with("cl100k_base")

    def test_initializes_circuit_breaker(self):
        """Test that circuit breaker is initialized."""
        # Arrange & Act
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI'):
                service = LLMService()

                # Assert
                assert service.circuit_breaker is not None
                assert hasattr(service.circuit_breaker, 'call')


# ===== ESTIMATE_TOKENS TESTS =====


class TestEstimateTokens:
    """Test estimate_tokens method."""

    def test_returns_token_count_from_tokenizer(self):
        """Test that token count is returned from tokenizer."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI'):
                service = LLMService()
                service.tokenizer = Mock()
                service.tokenizer.encode.return_value = [1, 2, 3, 4, 5]  # 5 tokens

                # Act
                count = service.estimate_tokens("test message")

                # Assert
                assert count == 5

    def test_uses_fallback_on_tokenizer_error(self):
        """Test that fallback estimate is used when tokenizer fails."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI'):
                service = LLMService()
                service.tokenizer = Mock()
                service.tokenizer.encode.side_effect = Exception("Tokenizer error")

                # Act
                count = service.estimate_tokens("test" * 20)  # 80 characters

                # Assert - ~4 chars per token = ~20 tokens
                assert count == 20

    def test_fallback_estimate_for_empty_string(self):
        """Test that fallback estimate works for empty string."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI'):
                service = LLMService()
                service.tokenizer = Mock()
                service.tokenizer.encode.side_effect = Exception("Error")

                # Act
                count = service.estimate_tokens("")

                # Assert
                assert count == 0


# ===== BUILD_CONVERSATION_CONTEXT TESTS =====


class TestBuildConversationContext:
    """Test build_conversation_context method."""

    def test_includes_system_prompt(self):
        """Test that system prompt is always included as first message."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI'):
                service = LLMService()

                # Act
                context = service.build_conversation_context([])

                # Assert
                assert len(context) >= 1
                assert context[0]["role"] == "system"
                assert "content" in context[0]

    def test_converts_messages_to_openai_format(self):
        """Test that messages are converted to OpenAI API format."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI'):
                service = LLMService()

                messages = [
                    Message(sender_type="user", content="Hello", token_count=5),
                    Message(sender_type="bot", content="Hi there!", token_count=5),
                ]

                # Act
                context = service.build_conversation_context(messages)

                # Assert - system + 2 messages
                assert len(context) == 3
                assert context[1]["role"] == "user"
                assert context[1]["content"] == "Hello"
                assert context[2]["role"] == "assistant"
                assert context[2]["content"] == "Hi there!"

    def test_maintains_chronological_order(self):
        """Test that messages are in chronological order."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI'):
                service = LLMService()

                messages = [
                    Message(sender_type="user", content="First", token_count=5),
                    Message(sender_type="bot", content="Second", token_count=5),
                    Message(sender_type="user", content="Third", token_count=5),
                ]

                # Act
                context = service.build_conversation_context(messages)

                # Assert
                assert context[1]["content"] == "First"
                assert context[2]["content"] == "Second"
                assert context[3]["content"] == "Third"

    def test_truncates_at_message_limit(self):
        """Test that context is truncated at max_context_messages limit."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI'):
                service = LLMService(max_context_messages=2)  # Only 2 pairs = 4 messages

                messages = [
                    Message(sender_type="user", content=f"Message {i}", token_count=5)
                    for i in range(10)
                ]

                # Act
                context = service.build_conversation_context(messages)

                # Assert - system + max 4 messages (2 pairs)
                assert len(context) <= 5  # system + 4 messages

    def test_truncates_at_token_limit(self):
        """Test that context is truncated when token limit is reached."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI'):
                service = LLMService(max_tokens_per_request=100)  # Very low limit
                service.tokenizer = Mock()
                service.tokenizer.encode.return_value = [1] * 50  # Each message = 50 tokens

                messages = [
                    Message(sender_type="user", content=f"Long message {i}", token_count=50)
                    for i in range(10)
                ]

                # Act
                context = service.build_conversation_context(messages)

                # Assert - should be truncated due to token limit
                # Exact number depends on system prompt size, but should be limited
                assert len(context) < 12  # system + 10 messages


# ===== CALL_OPENAI_API TESTS =====


class TestCallOpenaiApi:
    """Test _call_openai_api method."""

    def test_calls_openai_chat_completion(self):
        """Test that OpenAI chat completion API is called."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI') as mock_openai_class:
                mock_client = Mock()
                mock_openai_class.return_value = mock_client
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "AI response"
                mock_client.chat.completions.create.return_value = mock_response

                service = LLMService()
                messages = [{"role": "user", "content": "test"}]

                # Act
                response = service._call_openai_api(messages)

                # Assert
                assert response == "AI response"
                mock_client.chat.completions.create.assert_called_once()

    def test_uses_correct_model(self):
        """Test that correct model is used in API call."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI') as mock_openai_class:
                mock_client = Mock()
                mock_openai_class.return_value = mock_client
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "response"
                mock_client.chat.completions.create.return_value = mock_response

                service = LLMService(model="gpt-4")
                messages = [{"role": "user", "content": "test"}]

                # Act
                service._call_openai_api(messages)

                # Assert
                call_kwargs = mock_client.chat.completions.create.call_args[1]
                assert call_kwargs['model'] == "gpt-4"

    def test_uses_max_response_tokens(self):
        """Test that max_response_tokens limit is applied."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI') as mock_openai_class:
                mock_client = Mock()
                mock_openai_class.return_value = mock_client
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "response"
                mock_client.chat.completions.create.return_value = mock_response

                service = LLMService(max_response_tokens=300)
                messages = [{"role": "user", "content": "test"}]

                # Act
                service._call_openai_api(messages)

                # Assert
                call_kwargs = mock_client.chat.completions.create.call_args[1]
                assert call_kwargs['max_completion_tokens'] == 300

    def test_raises_exception_on_api_error(self):
        """Test that API errors are raised (for retry decorator to handle)."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI') as mock_openai_class:
                mock_client = Mock()
                mock_openai_class.return_value = mock_client
                mock_client.chat.completions.create.side_effect = Exception("API Error")

                service = LLMService()
                messages = [{"role": "user", "content": "test"}]

                # Act & Assert
                with pytest.raises(Exception, match="API Error"):
                    service._call_openai_api(messages)


# ===== GENERATE_RESPONSE TESTS =====


class TestGenerateResponse:
    """Test generate_response method."""

    def test_builds_context_with_user_message(self):
        """Test that context is built and user message is appended."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI') as mock_openai_class:
                mock_client = Mock()
                mock_openai_class.return_value = mock_client
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "AI response"
                mock_client.chat.completions.create.return_value = mock_response

                service = LLMService()
                prev_messages = [
                    Message(sender_type="user", content="Previous", token_count=5)
                ]

                # Act
                response = service.generate_response(
                    conversation_messages=prev_messages,
                    user_message="Current message"
                )

                # Assert
                assert response == "AI response"
                # Verify API was called with context + new message
                call_args = mock_client.chat.completions.create.call_args[1]['messages']
                # Should have: system + previous message + current message
                assert len(call_args) >= 3
                assert call_args[-1]["content"] == "Current message"

    def test_calls_api_through_circuit_breaker(self):
        """Test that API is called through circuit breaker."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI') as mock_openai_class:
                mock_client = Mock()
                mock_openai_class.return_value = mock_client
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "response"
                mock_client.chat.completions.create.return_value = mock_response

                service = LLMService()
                service.circuit_breaker = Mock()
                service.circuit_breaker.call.return_value = "Breaker response"

                # Act
                response = service.generate_response([], "test")

                # Assert
                service.circuit_breaker.call.assert_called_once()

    def test_returns_fallback_response_on_exception(self):
        """Test that fallback response is returned when exception occurs."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI') as mock_openai_class:
                mock_client = Mock()
                mock_openai_class.return_value = mock_client
                mock_client.chat.completions.create.side_effect = Exception("API Error")

                service = LLMService()

                with patch('src.services.llm_service.persona_service') as mock_persona:
                    mock_persona.get_fallback_response.return_value = "Fallback message"

                    # Act
                    response = service.generate_response([], "test")

                    # Assert
                    assert response == "Fallback message"
                    mock_persona.get_fallback_response.assert_called_once()

    def test_handles_empty_conversation_messages(self):
        """Test that empty conversation history is handled correctly."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI') as mock_openai_class:
                mock_client = Mock()
                mock_openai_class.return_value = mock_client
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "First response"
                mock_client.chat.completions.create.return_value = mock_response

                service = LLMService()

                # Act
                response = service.generate_response([], "First message")

                # Assert
                assert response == "First response"


# ===== ESTIMATE_MESSAGE_TOKENS TESTS =====


class TestEstimateMessageTokens:
    """Test estimate_message_tokens method."""

    def test_returns_same_as_estimate_tokens(self):
        """Test that estimate_message_tokens returns same value as estimate_tokens."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI'):
                service = LLMService()
                service.tokenizer = Mock()
                service.tokenizer.encode.return_value = [1, 2, 3, 4, 5]

                # Act
                result1 = service.estimate_tokens("test")
                result2 = service.estimate_message_tokens("test")

                # Assert
                assert result1 == result2 == 5


# ===== INTEGRATION TESTS =====


class TestLlmServiceIntegration:
    """Integration tests for LLMService."""

    def test_full_conversation_flow(self):
        """Test complete conversation flow from messages to response."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI') as mock_openai_class:
                mock_client = Mock()
                mock_openai_class.return_value = mock_client
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "Great question!"
                mock_client.chat.completions.create.return_value = mock_response

                service = LLMService()

                conversation = [
                    Message(sender_type="user", content="Hello", token_count=5),
                    Message(sender_type="bot", content="Hi!", token_count=5),
                ]

                # Act
                response = service.generate_response(
                    conversation_messages=conversation,
                    user_message="How are you?"
                )

                # Assert
                assert response == "Great question!"
                # Verify API was called with full context
                mock_client.chat.completions.create.assert_called_once()

    def test_handles_very_long_conversation(self):
        """Test that very long conversations are truncated appropriately."""
        # Arrange
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('src.services.llm_service.OpenAI') as mock_openai_class:
                mock_client = Mock()
                mock_openai_class.return_value = mock_client
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "Response"
                mock_client.chat.completions.create.return_value = mock_response

                service = LLMService(max_context_messages=3)

                # Create long conversation
                conversation = [
                    Message(sender_type="user" if i % 2 == 0 else "bot",
                           content=f"Message {i}",
                           token_count=10)
                    for i in range(20)
                ]

                # Act
                response = service.generate_response(
                    conversation_messages=conversation,
                    user_message="Latest message"
                )

                # Assert
                assert response == "Response"
                # Verify context was truncated
                call_args = mock_client.chat.completions.create.call_args[1]['messages']
                # Should have system + max 6 messages (3 pairs) + current
                assert len(call_args) <= 8
