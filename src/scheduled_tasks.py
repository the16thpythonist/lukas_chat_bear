"""
Scheduled task functions for APScheduler.

These functions must be in a separate module (not __main__/bot.py) so APScheduler
can properly serialize and deserialize them when restoring jobs from the database.
"""

import asyncio
from src.utils.database import get_db
from src.utils.config_loader import config
from src.utils.logger import logger


def scheduled_random_dm_task():
    """
    Scheduled task wrapper for sending random DMs.

    This function must be at module level (not __main__) for APScheduler serialization.
    """
    from src.services.proactive_dm_service import send_random_proactive_dm

    async def _send():
        # Import app here to avoid circular imports
        from src.bot import app

        with get_db() as db:
            await send_random_proactive_dm(
                app=app,
                db_session=db,
                slack_client=app.client
            )

    asyncio.run(_send())


def scheduled_image_post_task():
    """
    Scheduled task wrapper for posting images.

    This function must be at module level (not __main__) for APScheduler serialization.
    """
    from src.services.image_service import image_service

    async def _post():
        # Get channel from config
        channel = config.get("bot.image_posting.channel", "#random")
        if image_service:
            await image_service.generate_and_post(channel_id=channel)
        else:
            logger.warning("Image service not initialized - skipping scheduled image post")

    asyncio.run(_post())
