"""
Main Slack Bolt application for Lukas the Bear chatbot.

Initializes the Slack app, registers event handlers, and starts Socket Mode.
"""

import os
import sys
import asyncio

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from src.utils.logger import logger
from src.utils.config_loader import config
from src.utils.database import check_db_connection, get_db


# Initialize Slack app (ASYNC)
app = AsyncApp(
    token=os.getenv("SLACK_BOT_TOKEN"),
    # Signing secret not needed for Socket Mode, but kept for future Events API support
    signing_secret=os.getenv("SLACK_SIGNING_SECRET", ""),
)


def register_handlers():
    """
    Register all Slack event handlers.

    Handlers will be imported and registered once implemented.
    """
    from src.handlers.message_handler import register_message_handlers
    from src.handlers.thread_handler import ThreadHandler
    from src.handlers.command_handler import register_command_handlers
    from src.utils.database import get_db

    # Register message handlers (DMs and mentions)
    register_message_handlers(app)

    # Register thread/channel monitoring handlers
    with get_db() as db:
        thread_handler = ThreadHandler(app=app, db_session=db)
        thread_handler.register_handlers()

    # Register command handlers (admin commands, image generation, etc.)
    register_command_handlers(app)

    logger.info("Event handlers registered")


# Import scheduled task functions from separate module (not __main__)
# This prevents APScheduler serialization issues when restoring jobs from database
from src.scheduled_tasks import scheduled_random_dm_task, scheduled_image_post_task


def init_scheduler():
    """
    Initialize APScheduler for background tasks.
    """
    from src.services.scheduler_service import (
        init_scheduler as setup_scheduler,
        schedule_image_post_task,
        schedule_random_dm_task,
        restore_scheduled_events,
        get_scheduler
    )
    from src.services.scheduled_event_service import ScheduledEventService
    from src.services.image_service import image_service

    # Initialize scheduler
    setup_scheduler()
    logger.info("APScheduler initialized")

    # Restore pending scheduled events from database
    try:
        with get_db() as db:
            scheduled_event_service = ScheduledEventService(
                db_session=db,
                scheduler=get_scheduler(),
                slack_client=app.client
            )
            restored_count = restore_scheduled_events(scheduled_event_service)
            logger.info(f"Restored {restored_count} scheduled events")
    except Exception as e:
        logger.warning(f"Failed to restore scheduled events: {e}")

    # Schedule random DMs if enabled
    random_dm_interval = config.get("bot.engagement.random_dm_interval_hours", 24)

    try:
        schedule_random_dm_task(
            interval_hours=random_dm_interval,
            send_random_dm_func=scheduled_random_dm_task
        )
        logger.info(f"Random DM scheduled (every {random_dm_interval} hours)")
    except Exception as e:
        logger.warning(f"Failed to schedule random DM: {e}")

    # Schedule image posting if enabled and configured
    image_interval_days = config.get("bot.image_posting.interval_days", 7)
    image_channel = config.get("bot.image_posting.channel", "#random")

    if image_service:
        try:
            schedule_image_post_task(
                interval_days=image_interval_days,
                channel_id=image_channel,
                post_image_func=scheduled_image_post_task
            )
            logger.info(f"Image posting scheduled (every {image_interval_days} days to {image_channel})")
        except Exception as e:
            logger.warning(f"Failed to schedule image posting: {e}")
    else:
        logger.warning("Image service not initialized - image posting disabled")


def seed_database():
    """Seed database with default configurations."""
    from src.utils.database import get_db
    from src.repositories.config_repo import ConfigurationRepository

    try:
        with get_db() as db:
            config_repo = ConfigurationRepository(db)
            config_repo.seed_default_configs()
            logger.info("Database seeded with default configurations")
    except Exception as e:
        logger.error(f"Error seeding database: {e}")


async def init_mcp_agent():
    """
    Initialize MCP agent service for tool-augmented conversations.

    This enables Lukas to use web search and other tools when helpful.
    Gracefully degrades if MCP servers are unavailable.
    """
    # Check if MCP integration is enabled
    use_mcp = os.getenv("USE_MCP_AGENT", "true").lower() == "true"

    if not use_mcp:
        logger.info("MCP agent disabled (USE_MCP_AGENT=false)")
        return

    try:
        from src.services.llm_agent_service import llm_agent_service

        logger.info("Initializing MCP agent service...")
        await llm_agent_service.initialize_mcp()
        logger.info("MCP agent service initialized successfully")

    except Exception as e:
        logger.warning(f"Failed to initialize MCP agent service: {e}")
        logger.info("Bot will use standard LLM service without tools")


def init_image_service():
    """Initialize image service for bear image generation."""
    from src.services.image_service import ImageService
    from src.utils.database import get_db
    import src.services.image_service as img_module

    # Check if OpenAI API key is configured
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY not set - image generation disabled")
        return

    try:
        with get_db() as db:
            # Get Slack client from app
            slack_client = app.client

            # Initialize global image service
            img_module.image_service = ImageService(
                db_session=db,
                slack_client=slack_client
            )

            logger.info("Image service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize image service: {e}")


async def main():
    """Main entry point for the bot application (async)."""
    logger.info("Starting Lukas the Bear chatbot...")

    # Check database connection
    if not check_db_connection():
        logger.error("Failed to connect to database. Exiting.")
        sys.exit(1)

    # Seed database with defaults
    seed_database()

    # Initialize image service
    init_image_service()

    # Initialize MCP agent service
    logger.info("Setting up MCP agent integration...")
    await init_mcp_agent()

    # Register event handlers
    register_handlers()

    # Initialize scheduler
    init_scheduler()

    # Get Socket Mode token
    socket_token = os.getenv("SLACK_APP_TOKEN")
    if not socket_token:
        logger.error("SLACK_APP_TOKEN not found in environment. Exiting.")
        sys.exit(1)

    # Start Socket Mode handler (async)
    logger.info("Connecting to Slack via Socket Mode...")
    handler = AsyncSocketModeHandler(app, socket_token)

    logger.info("🐻 Lukas the Bear is online and ready!")
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
