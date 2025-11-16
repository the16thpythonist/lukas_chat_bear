"""
Thread handler.

Handles channel thread monitoring and probabilistic engagement decisions.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from slack_bolt import App
from sqlalchemy.orm import Session

from src.services.engagement_service import EngagementService
from src.services.llm_service import LLMService
from src.services.persona_service import PersonaService
from src.repositories.config_repo import ConfigurationRepository
from src.repositories.team_member_repo import TeamMemberRepository
from src.repositories.conversation_repo import ConversationRepository
from src.models.engagement_event import EngagementEvent
from src.models.conversation import ConversationSession
from src.models.message import Message
from src.handlers.message_handler import get_llm_service
from src.utils.logger import logger
from src.utils.config_loader import config


class ThreadHandler:
    """
    Handles channel thread monitoring and engagement.

    Monitors threads in configured channels and decides whether to engage
    based on probability, activity level, and active hours.
    """

    def __init__(
        self,
        app: App,
        db_session: Session,
        engagement_service: Optional[EngagementService] = None,
        persona_service: Optional[PersonaService] = None,
        config_repo: Optional[ConfigurationRepository] = None,
        team_member_repo: Optional[TeamMemberRepository] = None,
        conversation_repo: Optional[ConversationRepository] = None,
    ):
        """
        Initialize thread handler.

        Args:
            app: Slack Bolt app instance
            db_session: Database session
            engagement_service: Optional engagement service
            persona_service: Optional persona service
            config_repo: Optional configuration repository
            team_member_repo: Optional team member repository
            conversation_repo: Optional conversation repository
        """
        self.app = app
        self.db = db_session
        self.engagement_service = engagement_service or EngagementService(db_session)
        self.persona_service = persona_service or PersonaService()
        self.config_repo = config_repo or ConfigurationRepository(db_session)
        self.team_member_repo = team_member_repo or TeamMemberRepository(db_session)
        self.conversation_repo = conversation_repo or ConversationRepository(db_session)

        # Cache for channel name -> ID mapping
        self._channel_cache: Dict[str, str] = {}

    async def is_channel_monitored(self, channel_id: str) -> bool:
        """
        Check if a channel should be monitored for proactive engagement.

        Args:
            channel_id: Slack channel ID

        Returns:
            True if channel should be monitored, False otherwise
        """
        try:
            # Get monitored channels from config
            monitored_channels = config.get("bot", {}).get("engagement", {}).get("monitored_channels", [])

            # Empty list means monitor ALL channels
            if not monitored_channels:
                logger.debug(f"No monitored_channels configured, monitoring all channels")
                return True

            # Check if channel ID is in the list
            if channel_id in monitored_channels:
                return True

            # Try to resolve channel name from cache or Slack API
            try:
                channel_info = await self.app.client.conversations_info(channel=channel_id)
                channel_name = f"#{channel_info['channel']['name']}"

                # Cache the mapping
                self._channel_cache[channel_name] = channel_id

                # Check if channel name is in monitored list
                if channel_name in monitored_channels:
                    logger.debug(f"Channel {channel_name} ({channel_id}) is monitored")
                    return True

                logger.info(f"🚫 Channel {channel_name} ({channel_id}) not in monitored list, skipping")
                return False

            except Exception as e:
                logger.warning(f"Could not resolve channel name for {channel_id}: {e}")
                # If we can't resolve the name, default to not monitoring
                return False

        except Exception as e:
            logger.error(f"Error checking monitored channels: {e}")
            # On error, default to monitoring (fail open)
            return True

    def should_engage_with_thread(
        self,
        channel_id: str,
        thread_ts: str,
        message_count: int = 0
    ) -> tuple[bool, float, float]:
        """
        Decide whether to engage with a thread.

        Checks:
        1. Active hours
        2. Thread activity level
        3. Probability-based decision
        4. Not already engaged with this thread

        Args:
            channel_id: Slack channel ID
            thread_ts: Thread timestamp
            message_count: Number of messages in thread

        Returns:
            Tuple of (should_engage, probability, random_value)
        """
        # Check if already engaged with this thread
        existing_event = (
            self.db.query(EngagementEvent)
            .filter(
                EngagementEvent.channel_id == channel_id,
                EngagementEvent.thread_ts == thread_ts,
                EngagementEvent.engaged == True
            )
            .first()
        )

        if existing_event:
            logger.info(f"🔄 Thread {thread_ts}: Already engaged, skipping")
            return False, 0.0, 0.0

        # Check active hours
        start_hour, end_hour, timezone = self.engagement_service.get_active_hours()
        if not self.engagement_service.is_within_active_hours(
            start_hour=start_hour,
            end_hour=end_hour,
            timezone=timezone
        ):
            logger.info(f"⏰ Thread {thread_ts}: Outside active hours, not engaging")
            return False, 0.0, 0.0

        # Check thread activity level
        if self.engagement_service.is_thread_too_active(message_count):
            logger.info(f"📊 Thread {thread_ts}: Too active ({message_count} messages), not engaging")
            return False, 0.0, 0.0

        # Get probability and make decision
        probability = self.engagement_service.get_engagement_probability()
        should_engage = self.engagement_service.should_engage(probability)

        return should_engage, probability, 0.0  # Would store actual random value in production

    def extract_thread_context(self, messages: list[Dict[str, Any]]) -> str:
        """
        Extract relevant context from thread messages.

        Args:
            messages: List of Slack message dictionaries

        Returns:
            Formatted context string for LLM
        """
        if not messages:
            return ""

        # Limit to last 5 messages to keep context manageable
        recent_messages = messages[-5:]

        context_parts = []
        for msg in recent_messages:
            user = msg.get("user", "unknown")
            text = msg.get("text", "")
            context_parts.append(f"<{user}>: {text}")

        context = "\n".join(context_parts)
        logger.debug(f"Extracted thread context: {len(context)} chars from {len(recent_messages)} messages")
        return context

    async def handle_thread_message(
        self,
        channel_id: str,
        thread_ts: str,
        message_text: str,
        user_id: str,
        message_ts: str
    ) -> Optional[str]:
        """
        Handle a new message in a monitored thread.

        Args:
            channel_id: Slack channel ID
            thread_ts: Thread timestamp
            message_text: Message content
            user_id: User who sent message
            message_ts: Message timestamp

        Returns:
            Response text if engaged, None otherwise
        """
        try:
            # Fetch thread history to get message count and context
            result = await self.app.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=20
            )
            messages = result.get("messages", [])
            message_count = len(messages)

            # Decide whether to engage
            should_engage, probability, random_value = self.should_engage_with_thread(
                channel_id=channel_id,
                thread_ts=thread_ts,
                message_count=message_count
            )

            # Create engagement event for audit trail
            event = EngagementEvent(
                channel_id=channel_id,
                thread_ts=thread_ts,
                event_type='thread_response' if should_engage else 'ignored',
                decision_probability=probability,
                random_value=random_value,
                engaged=should_engage,
                timestamp=datetime.now()
            )
            self.db.add(event)
            self.db.commit()

            if not should_engage:
                logger.info(f"🎲 Thread {thread_ts}: Probability check failed ({probability:.0%}), not engaging")
                return None

            # Log successful engagement decision
            logger.info(f"✅ Thread {thread_ts}: Engaging! (probability={probability:.0%}, {message_count} messages)")

            # Extract context
            thread_context = self.extract_thread_context(messages)

            # Generate response
            response = await self._generate_thread_response(
                thread_context=thread_context,
                channel_id=channel_id,
                thread_ts=thread_ts
            )

            return response

        except Exception as e:
            logger.error(f"Error handling thread message: {e}", exc_info=True)
            return None

    async def _generate_thread_response(
        self,
        thread_context: str,
        channel_id: str,
        thread_ts: str
    ) -> Optional[str]:
        """
        Generate contextual response for thread.

        Args:
            thread_context: Extracted thread context
            channel_id: Slack channel ID
            thread_ts: Thread timestamp

        Returns:
            Generated response text or None on error
        """
        try:
            # Get LLM service (with MCP if available)
            llm_service = get_llm_service()

            # Build user message with thread context
            user_message = f"I saw this conversation in a Slack thread:\n\n{thread_context}\n\nPlease respond naturally to engage with the discussion. Keep it brief and conversational."

            # Generate response
            # Note: Thread responses don't create ConversationSession records
            # since they're not tied to a specific team member. Engagement
            # tracking is handled via EngagementEvent instead.
            response = await llm_service.generate_response(
                conversation_messages=[],  # No prior conversation for proactive engagement
                user_message=user_message
            )

            return response

        except Exception as e:
            logger.error(f"Error generating thread response: {e}", exc_info=True)
            return None

    async def handle_top_level_message(
        self,
        channel_id: str,
        message_text: str,
        user_id: str,
        message_ts: str
    ) -> Optional[str]:
        """
        Handle a new top-level message in a monitored channel.

        Makes TWO INDEPENDENT decisions:
        1. Should add emoji reaction? (uses reaction_probability)
        2. Should respond with text? (uses thread_response_probability)

        Both can happen, only one, or neither.

        Args:
            channel_id: Slack channel ID
            message_text: Message content
            user_id: User who sent message
            message_ts: Message timestamp

        Returns:
            Response text if text response was generated, None otherwise
        """
        try:
            # Check if already engaged with this specific message
            existing_event = (
                self.db.query(EngagementEvent)
                .filter(
                    EngagementEvent.channel_id == channel_id,
                    EngagementEvent.thread_ts == message_ts,  # Use message_ts as unique identifier
                    EngagementEvent.engaged == True
                )
                .first()
            )

            if existing_event:
                logger.info(f"🔄 Message {message_ts}: Already engaged, skipping")
                return None

            # Check active hours
            start_hour, end_hour, timezone = self.engagement_service.get_active_hours()
            if not self.engagement_service.is_within_active_hours(
                start_hour=start_hour,
                end_hour=end_hour,
                timezone=timezone
            ):
                logger.info(f"⏰ Message {message_ts}: Outside active hours, not engaging")
                return None

            # TWO INDEPENDENT DECISIONS

            # Decision 1: Should add emoji reaction?
            should_react = self.engagement_service.should_add_reaction()

            # Decision 2: Should respond with text?
            should_respond_text = self.engagement_service.should_respond_with_text()

            if not should_react and not should_respond_text:
                # Neither action chosen - create ignored event
                event = EngagementEvent(
                    channel_id=channel_id,
                    thread_ts=message_ts,
                    event_type='ignored',
                    decision_probability=0.0,
                    random_value=0.0,
                    engaged=False,
                    timestamp=datetime.now()
                )
                self.db.add(event)
                self.db.commit()
                logger.info(f"🎲 Message {message_ts}: Neither reaction nor text chosen, not engaging")
                return None

            logger.info(f"✅ Message {message_ts}: Engaging! (reaction={should_react}, text={should_respond_text})")

            response_text = None

            # ACTION 1: Add emoji reaction if decided
            if should_react:
                try:
                    emoji = await self._select_emoji_via_llm(message_text)
                    await self.app.client.reactions_add(
                        channel=channel_id,
                        timestamp=message_ts,
                        name=emoji
                    )
                    logger.info(f"👍 Added emoji reaction to {message_ts}: :{emoji}:")

                    # Store reaction event
                    event = EngagementEvent(
                        channel_id=channel_id,
                        thread_ts=message_ts,
                        event_type='reaction',
                        decision_probability=self.engagement_service.get_reaction_probability(),
                        random_value=0.0,
                        engaged=True,
                        timestamp=datetime.now()
                    )
                    self.db.add(event)
                    self.db.commit()
                except Exception as e:
                    logger.error(f"Failed to add reaction to {message_ts}: {e}")

            # ACTION 2: Generate text response if decided
            if should_respond_text:
                try:
                    response_text = await self._generate_channel_response(
                        message_text=message_text,
                        channel_id=channel_id,
                        message_ts=message_ts
                    )

                    # Store text response event
                    event = EngagementEvent(
                        channel_id=channel_id,
                        thread_ts=message_ts,
                        event_type='thread_response',
                        decision_probability=self.engagement_service.get_engagement_probability(),
                        random_value=0.0,
                        engaged=True,
                        timestamp=datetime.now()
                    )
                    self.db.add(event)
                    self.db.commit()
                    logger.info(f"💬 Generated text response for {message_ts}")
                except Exception as e:
                    logger.error(f"Failed to generate text response for {message_ts}: {e}")

            return response_text

        except Exception as e:
            logger.error(f"Error handling top-level message: {e}", exc_info=True)
            return None

    async def _generate_channel_response(
        self,
        message_text: str,
        channel_id: str,
        message_ts: str
    ) -> Optional[str]:
        """
        Generate contextual response for channel message.

        Args:
            message_text: The channel message content
            channel_id: Slack channel ID
            message_ts: Message timestamp

        Returns:
            Generated response text or None on error
        """
        try:
            # Get LLM service (with MCP if available)
            llm_service = get_llm_service()

            # Build user message with channel message content
            user_message = f"I saw this message in a Slack channel:\n\n{message_text}\n\nPlease respond naturally to engage with this message. Keep it brief and conversational."

            # Generate response
            # Note: Channel responses don't create ConversationSession records
            # since they're proactive engagement. Tracking is via EngagementEvent.
            response = await llm_service.generate_response(
                conversation_messages=[],  # No prior conversation for proactive engagement
                user_message=user_message
            )

            return response

        except Exception as e:
            logger.error(f"Error generating channel response: {e}", exc_info=True)
            return None

    async def _select_emoji_via_llm(self, message_text: str) -> str:
        """
        Use LLM to select an appropriate emoji reaction for a message.

        The agent analyzes the message content and chooses a contextually
        appropriate emoji from the available list.

        Args:
            message_text: The message to react to

        Returns:
            Emoji name (e.g., 'heart', 'bear', 'thumbsup')
        """
        try:
            # Get available emojis from engagement service
            available_emojis = self.engagement_service.get_available_emojis()

            # Get LLM service (basic service, no need for full agent with tools)
            from src.services.llm_service import llm_service

            # Truncate message if too long
            truncated_message = message_text[:300] if len(message_text) > 300 else message_text

            # Build prompt for emoji selection
            prompt = f"""Select ONE appropriate emoji reaction for this Slack message.

Message: "{truncated_message}"

Available emojis: {', '.join(available_emojis)}

Reply with ONLY the emoji name (e.g., 'thumbsup' or 'heart'). No colons, no explanation.
Consider Lukas the Bear's friendly, supportive personality when choosing."""

            # Generate response synchronously (llm_service.generate_response is sync)
            response = llm_service.generate_response(
                conversation_messages=[],
                user_message=prompt
            )

            # Extract emoji name from response
            emoji = response.strip().lower().replace(':', '').replace(' ', '_')

            # Validate it's in our available list
            if emoji in available_emojis:
                logger.debug(f"LLM selected emoji: {emoji}")
                return emoji
            else:
                logger.warning(f"LLM selected invalid emoji '{emoji}', using 'bear' as fallback")
                return 'bear'

        except Exception as e:
            logger.error(f"Error selecting emoji via LLM: {e}, using 'bear' as fallback")
            return 'bear'  # Safe fallback

    async def handle_reaction(
        self,
        channel_id: str,
        thread_ts: str
    ) -> Optional[str]:
        """
        Add emoji reaction to thread.

        Args:
            channel_id: Slack channel ID
            thread_ts: Thread timestamp

        Returns:
            Emoji name that was added, or None on error
        """
        try:
            # Select appropriate emoji from available options
            available_emojis = self.engagement_service.get_available_emojis()
            import random
            emoji = random.choice(available_emojis) if available_emojis else 'bear'

            # Add reaction via Slack API
            await self.app.client.reactions_add(
                channel=channel_id,
                timestamp=thread_ts,
                name=emoji
            )

            # Create engagement event
            event = EngagementEvent(
                channel_id=channel_id,
                thread_ts=thread_ts,
                event_type='reaction',
                decision_probability=self.engagement_service.get_engagement_probability(),
                random_value=0.0,  # Already decided to engage
                engaged=True,
                timestamp=datetime.now(),
                meta={"emoji": emoji}
            )
            self.db.add(event)
            self.db.commit()

            logger.info(f"😊 Thread {thread_ts}: Added emoji reaction :{emoji}:")
            return emoji

        except Exception as e:
            logger.error(f"Error adding reaction: {e}", exc_info=True)
            return None

    def register_handlers(self) -> None:
        """
        Register Slack event handlers for channel and thread monitoring.

        Monitors message events in configured channels (both top-level and threads).
        """
        @self.app.event("message")
        async def handle_channel_message(event, say, client):
            """Handle new messages in monitored channels (top-level and threads)."""
            try:
                # Log that we received an event (basic debug)
                logger.info(f"🔔 ThreadHandler received message event: channel_type={event.get('channel_type')}, bot_id={event.get('bot_id')}, channel={event.get('channel')}")

                # Don't respond to bot messages
                if event.get("bot_id"):
                    logger.debug(f"Skipping bot message")
                    return

                # Skip DMs (handled by message_handler)
                if event.get("channel_type") == "im":
                    logger.debug(f"Skipping DM (handled by message_handler)")
                    return

                channel_id = event.get("channel")
                message_text = event.get("text", "")
                user_id = event.get("user")
                message_ts = event.get("ts")
                thread_ts = event.get("thread_ts")

                # Create fresh DB session for this handler execution
                from src.utils.database import get_db
                with get_db() as db:
                    # Update instance db session for this execution
                    original_db = self.db
                    self.db = db

                    # Check if channel is monitored
                    if not await self.is_channel_monitored(channel_id):
                        return  # Skip non-monitored channels

                    # Distinguish between thread replies and top-level messages
                    is_thread_reply = thread_ts is not None and thread_ts != message_ts

                    if is_thread_reply:
                        # Thread reply - existing behavior
                        logger.info(f"📨 New thread message in channel {channel_id}, thread {thread_ts}")

                        # Check if should engage (text or reaction)
                        engagement_type = self.engagement_service.select_engagement_type()
                        logger.info(f"🎭 Selected engagement type: {engagement_type}")

                        if engagement_type == "text":
                            response = await self.handle_thread_message(
                                channel_id=channel_id,
                                thread_ts=thread_ts,
                                message_text=message_text,
                                user_id=user_id,
                                message_ts=message_ts
                            )

                            if response:
                                await say(text=response, thread_ts=thread_ts)

                        elif engagement_type == "reaction":
                            # Only react sometimes (already probabilistic in should_engage_with_thread)
                            should_engage, _, _ = self.should_engage_with_thread(
                                channel_id=channel_id,
                                thread_ts=thread_ts,
                                message_count=0  # Would fetch actual count
                            )

                            if should_engage:
                                await self.handle_reaction(
                                    channel_id=channel_id,
                                    thread_ts=thread_ts
                                )
                    else:
                        # Top-level channel message - new behavior
                        logger.info(f"📨 New channel message in channel {channel_id}")

                        # Apply probabilistic engagement
                        response = await self.handle_top_level_message(
                            channel_id=channel_id,
                            message_text=message_text,
                            user_id=user_id,
                            message_ts=message_ts
                        )

                        if response:
                            # Reply in a thread to keep channel organized
                            await say(text=response, thread_ts=message_ts)

                    # Restore original db session
                    self.db = original_db

            except Exception as e:
                logger.error(f"Error in channel message handler: {e}", exc_info=True)

        logger.info("Thread handler registered")
