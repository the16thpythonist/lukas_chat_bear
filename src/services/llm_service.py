"""
LLM service.

Handles AI conversation using OpenAI or other LLM providers.
Includes context management, retry logic, and circuit breaker.
"""

import os
from typing import List, Dict, Optional

import tiktoken
from openai import OpenAI
from pybreaker import CircuitBreaker

from src.models.message import Message
from src.services.persona_service import persona_service
from src.utils.logger import logger
from src.utils.retry import retry_on_api_error


class LLMService:
    """
    Service for LLM-powered conversation.

    Features:
    - OpenAI integration (easily extensible to other providers)
    - Sliding window context management (last N message pairs)
    - Token estimation and truncation
    - Exponential backoff retry
    - Circuit breaker for sustained failures
    - Graceful degradation with fallback responses
    """

    def __init__(
        self,
        model: Optional[str] = None,
        max_context_messages: int = 10,
        max_tokens_per_request: int = 4000,
        max_response_tokens: int = 500,
    ):
        """
        Initialize LLM service.

        Args:
            model: LLM model name (defaults to env LLM_MODEL or gpt-3.5-turbo)
            max_context_messages: Maximum message pairs in context
            max_tokens_per_request: Maximum tokens per request
            max_response_tokens: Maximum tokens in response
        """
        self.model = model or os.getenv("LLM_MODEL", "gpt-3.5-turbo")
        self.max_context_messages = max_context_messages
        self.max_tokens_per_request = max_tokens_per_request
        self.max_response_tokens = max_response_tokens

        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY not set in environment")
            raise ValueError("OPENAI_API_KEY is required")

        self.client = OpenAI(api_key=api_key)

        # Initialize tokenizer for token counting
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.model)
        except KeyError:
            logger.warning(f"Model {self.model} not found in tiktoken, using cl100k_base")
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

        # Circuit breaker for sustained failures
        self.circuit_breaker = CircuitBreaker(
            fail_max=5,  # Open circuit after 5 failures
            reset_timeout=60,  # Try again after 60 seconds
        )

        logger.info(f"LLM service initialized with model {self.model}")

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for a text string.

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        try:
            return len(self.tokenizer.encode(text))
        except Exception as e:
            logger.error(f"Error estimating tokens: {e}")
            # Rough estimate: ~4 characters per token
            return len(text) // 4

    def build_conversation_context(self, messages: List[Message]) -> List[Dict[str, str]]:
        """
        Build conversation context from message history.

        Implements sliding window with token-based truncation.

        Args:
            messages: List of Message objects (ordered oldest to newest)

        Returns:
            List of message dicts for OpenAI API
        """
        # Get system prompt
        system_prompt = persona_service.get_system_prompt()
        context = [
            {"role": "system", "content": system_prompt}
        ]

        # Calculate system prompt tokens
        total_tokens = self.estimate_tokens(system_prompt)

        # Add messages from newest to oldest (will reverse later)
        included_messages = []
        for message in reversed(messages):
            # Convert to OpenAI format
            role = "assistant" if message.sender_type == "bot" else "user"
            msg_dict = {"role": role, "content": message.content}

            # Estimate tokens
            msg_tokens = self.estimate_tokens(message.content) + 4  # 4 tokens overhead per message

            # Check if adding this message would exceed limits
            if total_tokens + msg_tokens > self.max_tokens_per_request:
                logger.debug(f"Context truncated: would exceed {self.max_tokens_per_request} tokens")
                break

            # Check if we've hit message pair limit
            if len(included_messages) >= self.max_context_messages * 2:
                logger.debug(f"Context truncated: reached {self.max_context_messages} message pairs")
                break

            included_messages.append(msg_dict)
            total_tokens += msg_tokens

        # Reverse to get chronological order
        context.extend(reversed(included_messages))

        logger.debug(f"Built context with {len(included_messages)} messages (~{total_tokens} tokens)")
        return context

    @retry_on_api_error(max_attempts=3, min_wait=1, max_wait=10)
    def _call_openai_api(self, messages: List[Dict[str, str]]) -> str:
        """
        Call OpenAI API with retry logic.

        Args:
            messages: List of message dicts

        Returns:
            AI response text

        Raises:
            Exception: If API call fails after retries
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_completion_tokens=self.max_response_tokens,
                # temperature removed - some models only support default (1)
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def generate_response(
        self,
        conversation_messages: List[Message],
        user_message: str,
    ) -> str:
        """
        Generate AI response with circuit breaker and fallback.

        Args:
            conversation_messages: Previous messages in conversation
            user_message: Latest user message

        Returns:
            AI-generated response or fallback
        """
        try:
            # Build context
            context = self.build_conversation_context(conversation_messages)

            # Add current user message
            context.append({"role": "user", "content": user_message})

            # Call API with circuit breaker protection
            response = self.circuit_breaker.call(self._call_openai_api, context)

            logger.info(f"Generated response ({len(response)} chars)")
            return response

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            # Return fallback response
            fallback = persona_service.get_fallback_response()
            logger.info("Using fallback response due to error")
            return fallback

    def estimate_message_tokens(self, content: str) -> int:
        """
        Estimate tokens for a message (for database storage).

        Args:
            content: Message content

        Returns:
            Estimated token count
        """
        return self.estimate_tokens(content)


# Global LLM service instance
llm_service = LLMService()
