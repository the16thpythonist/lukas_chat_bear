"""
Scheduled Event Service

Business logic for managing scheduled channel messages.
"""

from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timedelta
import pytz
import dateparser
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.orm import Session

from src.models.scheduled_event import ScheduledEvent
from src.repositories.scheduled_event_repo import ScheduledEventRepository
from src.utils.logger import logger
from src.utils.config_loader import config


# Module-level execution function (must be picklable for APScheduler)
def execute_scheduled_event(event_id: int):
    """
    Execute a scheduled event (called by APScheduler).

    This is a module-level function (not a method) so it can be pickled
    by APScheduler's SQLAlchemy job store.

    Args:
        event_id: Event ID to execute
    """
    from src.utils.database import get_db
    from slack_sdk import WebClient

    try:
        logger.info(f"Executing scheduled event {event_id}")

        # Create new database session for this execution
        with get_db() as db:
            repo = ScheduledEventRepository(db)
            event = repo.get_by_id(event_id)

            if not event:
                logger.error(f"Event {event_id} not found for execution")
                return

            if event.status != 'pending':
                logger.warning(f"Event {event_id} has status '{event.status}', skipping execution")
                return

            # Get Slack client
            slack_token = os.getenv("SLACK_BOT_TOKEN")
            if not slack_token:
                repo.mark_failed(event_id, "Slack token not available")
                logger.error("Cannot execute event: SLACK_BOT_TOKEN not set")
                return

            slack_client = WebClient(token=slack_token)

            # Post message to Slack
            try:
                response = slack_client.chat_postMessage(
                    channel=event.target_channel_id,
                    text=event.message
                )

                if response.get('ok'):
                    # Mark as completed
                    repo.mark_completed(event_id)
                    logger.info(
                        f"Successfully posted scheduled message to {event.target_channel_name}"
                    )
                else:
                    # Mark as failed
                    error = response.get('error', 'Unknown Slack error')
                    repo.mark_failed(event_id, error)
                    logger.error(f"Slack API error: {error}")

            except Exception as e:
                # Mark as failed
                repo.mark_failed(event_id, str(e))
                logger.error(f"Failed to post message: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Error executing event {event_id}: {e}", exc_info=True)
        try:
            from src.utils.database import get_db
            with get_db() as db:
                repo = ScheduledEventRepository(db)
                repo.mark_failed(event_id, str(e))
        except:
            pass  # Best effort


class ScheduledEventService:
    """
    Service for managing scheduled events.

    Handles time parsing, event creation, APScheduler integration, and execution.
    """

    def __init__(self, db_session: Session, scheduler: BackgroundScheduler, slack_client=None):
        """
        Initialize service.

        Args:
            db_session: Database session
            scheduler: APScheduler instance
            slack_client: Slack client for posting messages (optional, for execution)
        """
        self.db_session = db_session
        self.repo = ScheduledEventRepository(db_session)
        self.scheduler = scheduler
        self.slack_client = slack_client

        # Get timezone from config
        timezone_str = config.get('bot.timezone', 'UTC')
        self.timezone = pytz.timezone(timezone_str)

    def parse_time(self, time_string: str, reference_time: Optional[datetime] = None) -> Optional[datetime]:
        """
        Parse natural language time string to datetime.

        Args:
            time_string: Natural language time (e.g., "3pm Friday", "in 30 minutes", "tomorrow at 2pm")
            reference_time: Reference time for relative parsing (default: now)

        Returns:
            Parsed datetime in UTC, or None if parsing fails

        Examples:
            >>> service.parse_time("3pm Friday")
            datetime(2025, 10, 31, 15, 0, 0)  # Next Friday at 3pm
            >>> service.parse_time("in 30 minutes")
            datetime(2025, 10, 29, 21, 30, 0)  # 30 minutes from now
            >>> service.parse_time("tomorrow at 2pm")
            datetime(2025, 10, 30, 14, 0, 0)  # Tomorrow at 2pm
        """
        if not time_string:
            return None

        try:
            # Use dateparser with timezone-aware settings
            settings = {
                'TIMEZONE': str(self.timezone),
                'RETURN_AS_TIMEZONE_AWARE': True,
                'PREFER_DATES_FROM': 'future',  # Prefer future dates
                'RELATIVE_BASE': reference_time if reference_time else datetime.now(self.timezone)
            }

            parsed = dateparser.parse(time_string, settings=settings)

            if parsed:
                # Convert to UTC for storage
                utc_time = parsed.astimezone(pytz.UTC)
                logger.debug(f"Parsed '{time_string}' as {utc_time} UTC")
                return utc_time.replace(tzinfo=None)  # Store as naive UTC

            logger.warning(f"Failed to parse time string: '{time_string}'")
            return None

        except Exception as e:
            logger.error(f"Error parsing time '{time_string}': {e}")
            return None

    def create_event(
        self,
        scheduled_time: datetime,
        target_channel_id: str,
        target_channel_name: str,
        message: str,
        created_by_user_id: Optional[str] = None,
        created_by_user_name: Optional[str] = None
    ) -> Tuple[Optional[ScheduledEvent], Optional[str]]:
        """
        Create a new scheduled event.

        Args:
            scheduled_time: When to post the message (UTC)
            target_channel_id: Slack channel ID
            target_channel_name: Channel name for display
            message: Message content
            created_by_user_id: User ID who created the event
            created_by_user_name: User name who created the event

        Returns:
            Tuple of (created event, error message if failed)

        Example:
            >>> event, error = service.create_event(
            ...     scheduled_time=datetime(2025, 10, 31, 15, 0),
            ...     target_channel_id='C123456',
            ...     target_channel_name='#general',
            ...     message='Meeting at 3pm',
            ...     created_by_user_id='U123456'
            ... )
            >>> if event:
            ...     print(f"Event {event.id} scheduled for {event.scheduled_time}")
        """
        try:
            # Validate scheduled time is in the future
            now = datetime.utcnow()
            if scheduled_time <= now:
                return None, "Scheduled time must be in the future"

            # Create event record
            event = ScheduledEvent(
                scheduled_time=scheduled_time,
                target_channel_id=target_channel_id,
                target_channel_name=target_channel_name,
                message=message,
                created_by_user_id=created_by_user_id,
                created_by_user_name=created_by_user_name
            )

            # Save to database
            created = self.repo.create(event)

            # Schedule APScheduler job (use module-level function for picklability)
            job_id = f"scheduled_event_{created.id}"
            self.scheduler.add_job(
                func=execute_scheduled_event,
                trigger=DateTrigger(run_date=scheduled_time),
                args=[created.id],
                id=job_id,
                name=f"Event {created.id}: {message[:50]}",
                misfire_grace_time=300  # 5 minutes grace period
            )

            # Update event with job ID
            created.job_id = job_id
            self.repo.update(created)

            logger.info(
                f"Created scheduled event {created.id} for {scheduled_time} "
                f"in channel {target_channel_name}"
            )

            return created, None

        except Exception as e:
            logger.error(f"Failed to create scheduled event: {e}", exc_info=True)
            return None, str(e)

    def create_from_natural_language(
        self,
        time_string: str,
        target_channel_id: str,
        target_channel_name: str,
        message: str,
        created_by_user_id: Optional[str] = None,
        created_by_user_name: Optional[str] = None
    ) -> Tuple[Optional[ScheduledEvent], Optional[str]]:
        """
        Create event from natural language time string.

        Args:
            time_string: Natural language time (e.g., "3pm Friday")
            target_channel_id: Slack channel ID
            target_channel_name: Channel name
            message: Message content
            created_by_user_id: Creator user ID
            created_by_user_name: Creator name

        Returns:
            Tuple of (created event, error message if failed)
        """
        # Parse time
        scheduled_time = self.parse_time(time_string)
        if not scheduled_time:
            return None, f"Could not parse time '{time_string}'. Please provide a clearer date/time."

        # Create event
        return self.create_event(
            scheduled_time=scheduled_time,
            target_channel_id=target_channel_id,
            target_channel_name=target_channel_name,
            message=message,
            created_by_user_id=created_by_user_id,
            created_by_user_name=created_by_user_name
        )

    def update_event(
        self,
        event_id: int,
        scheduled_time: Optional[datetime] = None,
        message: Optional[str] = None
    ) -> Tuple[Optional[ScheduledEvent], Optional[str]]:
        """
        Update an existing event's time and/or message.

        Args:
            event_id: Event ID to update
            scheduled_time: New scheduled time (if changing)
            message: New message content (if changing)

        Returns:
            Tuple of (updated event, error message if failed)
        """
        try:
            event = self.repo.get_by_id(event_id)
            if not event:
                return None, "Event not found"

            if not event.can_be_edited():
                return None, f"Cannot edit event with status '{event.status}'"

            # Update fields
            if scheduled_time:
                # Validate future time
                if scheduled_time <= datetime.utcnow():
                    return None, "Scheduled time must be in the future"

                event.scheduled_time = scheduled_time

                # Reschedule job
                if event.job_id:
                    self.scheduler.reschedule_job(
                        job_id=event.job_id,
                        trigger=DateTrigger(run_date=scheduled_time)
                    )

            if message:
                event.message = message

            # Save changes
            updated = self.repo.update(event)
            logger.info(f"Updated scheduled event {event_id}")

            return updated, None

        except Exception as e:
            logger.error(f"Failed to update event {event_id}: {e}", exc_info=True)
            return None, str(e)

    def cancel_event(self, event_id: int) -> Tuple[bool, Optional[str]]:
        """
        Cancel a scheduled event.

        Args:
            event_id: Event ID to cancel

        Returns:
            Tuple of (success boolean, error message if failed)
        """
        try:
            event = self.repo.get_by_id(event_id)
            if not event:
                return False, "Event not found"

            if not event.can_be_cancelled():
                return False, f"Cannot cancel event with status '{event.status}'"

            # Remove APScheduler job
            if event.job_id:
                try:
                    self.scheduler.remove_job(event.job_id)
                except Exception as e:
                    logger.warning(f"Failed to remove job {event.job_id}: {e}")
                    # Continue anyway - mark as cancelled in DB

            # Mark as cancelled
            cancelled = self.repo.cancel(event_id)
            if cancelled:
                logger.info(f"Cancelled scheduled event {event_id}")
                return True, None
            else:
                return False, "Failed to cancel event in database"

        except Exception as e:
            logger.error(f"Failed to cancel event {event_id}: {e}", exc_info=True)
            return False, str(e)


    def get_event(self, event_id: int) -> Optional[ScheduledEvent]:
        """Get event by ID."""
        return self.repo.get_by_id(event_id)

    def get_all_events(
        self,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ScheduledEvent]:
        """Get all events with optional filtering."""
        return self.repo.get_all(status=status, limit=limit, offset=offset)

    def get_pending_events(self) -> List[ScheduledEvent]:
        """Get all pending events."""
        return self.repo.get_pending()

    def get_upcoming_events(self, limit: int = 10) -> List[ScheduledEvent]:
        """Get upcoming pending events."""
        return self.repo.get_upcoming(limit=limit)
