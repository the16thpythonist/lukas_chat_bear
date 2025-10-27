"""
Message handler for direct messages and mentions.

Handles incoming messages from users and generates responses using LLM.
"""

import os
import asyncio
from slack_bolt.async_app import AsyncApp
from slack_sdk.errors import SlackApiError

from src.models.message import Message
from src.repositories.conversation_repo import ConversationRepository
from src.repositories.team_member_repo import TeamMemberRepository
from src.services.llm_service import llm_service
from src.utils.database import get_db
from src.utils.logger import logger


def get_llm_service():
    """
    Get the appropriate LLM service (agent or standard).

    Returns agent service if MCP is enabled and initialized,
    otherwise returns standard LLM service.

    Returns:
        LLM service instance (either agent or standard)
    """
    use_mcp = os.getenv("USE_MCP_AGENT", "true").lower() == "true"

    if use_mcp:
        try:
            from src.services.llm_agent_service import llm_agent_service
            # Check if agent has MCP tools loaded
            if llm_agent_service.agent is not None:
                logger.debug("Using MCP agent service with tools")
                return llm_agent_service
        except Exception as e:
            logger.debug(f"Agent service not available: {e}")

    logger.debug("Using standard LLM service")
    return llm_service


async def handle_direct_message(event: dict, say, client, logger_inst=logger):
    """
    Handle direct message events (async).

    Args:
        event: Slack event data
        say: Slack say function for responding
        client: Slack client
        logger_inst: Logger instance
    """
    try:
        # Extract event data
        user_id = event.get("user")
        text = event.get("text", "")
        channel = event.get("channel")
        ts = event.get("ts")

        # Ignore bot messages
        if event.get("bot_id"):
            return

        logger_inst.info(f"Received DM from user {user_id}: {text[:50]}...")

        # Get or create team member
        with get_db() as db:
            # Fetch user info from Slack
            try:
                user_info = await client.users_info(user=user_id)
                user_data = user_info["user"]
                display_name = user_data.get("profile", {}).get("display_name") or user_data.get("name")
                real_name = user_data.get("profile", {}).get("real_name")
                is_bot = user_data.get("is_bot", False)
            except SlackApiError as e:
                logger_inst.error(f"Error fetching user info: {e}")
                display_name = f"User_{user_id}"
                real_name = None
                is_bot = False

            # Get or create team member
            team_member_repo = TeamMemberRepository(db)
            team_member = team_member_repo.get_or_create(
                slack_user_id=user_id,
                display_name=display_name,
                real_name=real_name,
                is_bot=is_bot,
            )

            # Get or create conversation
            conv_repo = ConversationRepository(db)
            conversation = conv_repo.get_or_create_conversation(
                team_member_id=team_member.id,
                channel_type="dm",
                channel_id=channel,
            )

            # Get LLM service (agent or standard)
            service = get_llm_service()

            # Store user message
            token_count = service.estimate_tokens(text) if hasattr(service, 'estimate_tokens') else llm_service.estimate_message_tokens(text)
            conv_repo.add_message(
                conversation_id=conversation.id,
                sender_type="user",
                content=text,
                slack_ts=ts,
                token_count=token_count,
            )

            # Get conversation history
            recent_messages = conv_repo.get_recent_messages(
                conversation_id=conversation.id,
                limit=service.max_context_messages * 2,
            )

            # Send placeholder "thinking" message for immediate feedback
            placeholder_ts = None
            try:
                placeholder = await say(text="🐻 Thinking...", channel=channel)
                placeholder_ts = placeholder.get("ts")
                logger_inst.debug(f"Sent thinking placeholder with ts={placeholder_ts}")
            except Exception as e:
                logger_inst.warning(f"Failed to send thinking placeholder: {e}")
                # Continue without placeholder

            # Generate response (handle both sync and async)
            if asyncio.iscoroutinefunction(service.generate_response):
                response_text = await service.generate_response(
                    conversation_messages=recent_messages,
                    user_message=text,
                    user_id=user_id,
                    user_name=display_name,
                )
            else:
                response_text = service.generate_response(
                    conversation_messages=recent_messages,
                    user_message=text,
                    user_id=user_id,
                    user_name=display_name,
                )

            # Validate response is not empty
            if not response_text or not response_text.strip():
                logger_inst.error("Generated response is empty, using fallback message")
                response_text = "I'm having trouble processing that right now 🐻 Can you try again?"

            # Update placeholder or post new message
            try:
                if placeholder_ts:
                    # Update the thinking message with actual response
                    result = await client.chat_update(
                        channel=channel,
                        ts=placeholder_ts,
                        text=response_text
                    )
                    response_ts = placeholder_ts  # Use placeholder ts for storage
                    logger_inst.debug(f"Updated thinking message to response")
                else:
                    # Fallback: post as new message
                    result = await say(text=response_text, channel=channel)
                    response_ts = result.get("ts")

                # Store bot response
                response_token_count = service.estimate_tokens(response_text) if hasattr(service, 'estimate_tokens') else llm_service.estimate_message_tokens(response_text)
                conv_repo.add_message(
                    conversation_id=conversation.id,
                    sender_type="bot",
                    content=response_text,
                    slack_ts=response_ts,
                    token_count=response_token_count,
                )

                logger_inst.info(f"Sent response to user {user_id}")

            except SlackApiError as e:
                logger_inst.error(f"Error posting message to Slack: {e}")
                raise

            # Update engagement metrics
            team_member_repo.increment_message_count(team_member.id)

    except Exception as e:
        logger_inst.error(f"Error handling direct message: {e}", exc_info=True)
        # Try to send error message to user
        try:
            await say(text="I'm having trouble right now 🐻 Please try again in a moment!", channel=channel)
        except Exception:
            pass


async def handle_app_mention(event: dict, say, client, logger_inst=logger):
    """
    Handle app mention events in channels (async).

    Args:
        event: Slack event data
        say: Slack say function for responding
        client: Slack client
        logger_inst: Logger instance
    """
    try:
        # Extract event data
        user_id = event.get("user")
        text = event.get("text", "")
        channel = event.get("channel")
        ts = event.get("ts")
        thread_ts = event.get("thread_ts", ts)  # Use message ts if not in thread

        # Ignore bot messages
        if event.get("bot_id"):
            return

        logger_inst.info(f"Received mention from user {user_id} in channel {channel}")

        # Get or create team member
        with get_db() as db:
            # Fetch user info
            try:
                user_info = await client.users_info(user=user_id)
                user_data = user_info["user"]
                display_name = user_data.get("profile", {}).get("display_name") or user_data.get("name")
                real_name = user_data.get("profile", {}).get("real_name")
                is_bot = user_data.get("is_bot", False)
            except SlackApiError as e:
                logger_inst.error(f"Error fetching user info: {e}")
                display_name = f"User_{user_id}"
                real_name = None
                is_bot = False

            # Get or create team member
            team_member_repo = TeamMemberRepository(db)
            team_member = team_member_repo.get_or_create(
                slack_user_id=user_id,
                display_name=display_name,
                real_name=real_name,
                is_bot=is_bot,
            )

            # Get or create conversation (thread-based)
            conv_repo = ConversationRepository(db)
            conversation = conv_repo.get_or_create_conversation(
                team_member_id=team_member.id,
                channel_type="thread",
                channel_id=channel,
                thread_ts=thread_ts,
            )

            # Get LLM service (agent or standard)
            service = get_llm_service()

            # Store user message
            token_count = service.estimate_tokens(text) if hasattr(service, 'estimate_tokens') else llm_service.estimate_message_tokens(text)
            conv_repo.add_message(
                conversation_id=conversation.id,
                sender_type="user",
                content=text,
                slack_ts=ts,
                token_count=token_count,
            )

            # Get conversation history
            recent_messages = conv_repo.get_recent_messages(
                conversation_id=conversation.id,
                limit=service.max_context_messages * 2,
            )

            # Send placeholder "thinking" message for immediate feedback
            placeholder_ts = None
            try:
                placeholder = await say(text="🐻 Thinking...", thread_ts=thread_ts)
                placeholder_ts = placeholder.get("ts")
                logger_inst.debug(f"Sent thinking placeholder in thread with ts={placeholder_ts}")
            except Exception as e:
                logger_inst.warning(f"Failed to send thinking placeholder: {e}")
                # Continue without placeholder

            # Generate response (handle both sync and async)
            if asyncio.iscoroutinefunction(service.generate_response):
                response_text = await service.generate_response(
                    conversation_messages=recent_messages,
                    user_message=text,
                    user_id=user_id,
                    user_name=display_name,
                )
            else:
                response_text = service.generate_response(
                    conversation_messages=recent_messages,
                    user_message=text,
                    user_id=user_id,
                    user_name=display_name,
                )

            # Validate response is not empty
            if not response_text or not response_text.strip():
                logger_inst.error("Generated response is empty, using fallback message")
                response_text = "I'm having trouble processing that right now 🐻 Can you try again?"

            # Update placeholder or post new message in thread
            try:
                if placeholder_ts:
                    # Update the thinking message with actual response
                    result = await client.chat_update(
                        channel=channel,
                        ts=placeholder_ts,
                        text=response_text
                    )
                    response_ts = placeholder_ts  # Use placeholder ts for storage
                    logger_inst.debug(f"Updated thinking message to response in thread")
                else:
                    # Fallback: post as new message
                    result = await say(text=response_text, thread_ts=thread_ts)
                    response_ts = result.get("ts")

                # Store bot response
                response_token_count = service.estimate_tokens(response_text) if hasattr(service, 'estimate_tokens') else llm_service.estimate_message_tokens(response_text)
                conv_repo.add_message(
                    conversation_id=conversation.id,
                    sender_type="bot",
                    content=response_text,
                    slack_ts=response_ts,
                    token_count=response_token_count,
                )

                logger_inst.info(f"Sent response to mention in channel {channel}")

            except SlackApiError as e:
                logger_inst.error(f"Error posting message to Slack: {e}")
                raise

    except Exception as e:
        logger_inst.error(f"Error handling app mention: {e}", exc_info=True)
        # Try to send error message
        try:
            await say(text="I'm having trouble right now 🐻 Please try again in a moment!", thread_ts=thread_ts)
        except Exception:
            pass


def register_message_handlers(app: AsyncApp):
    """
    Register message event handlers with the Slack app (async).

    Args:
        app: Slack AsyncApp instance
    """
    # Matcher function for DMs only (must be async)
    async def is_dm(event: dict) -> bool:
        """Match only direct messages."""
        return event.get("channel_type") == "im"

    # Direct message handler - use matcher to only match DMs
    @app.event(event="message", matchers=[is_dm])
    async def message_handler(event, say, client):
        await handle_direct_message(event, say, client)

    # App mention handler
    @app.event("app_mention")
    async def mention_handler(event, say, client):
        await handle_app_mention(event, say, client)

    logger.info("Message handlers registered")
