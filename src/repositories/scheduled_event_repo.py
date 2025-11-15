"""
Scheduled Event Repository

Data access layer for scheduled events.
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.models.scheduled_event import ScheduledEvent
from src.utils.logger import logger


class ScheduledEventRepository:
    """
    Repository for scheduled event data access.

    Provides CRUD operations and queries for scheduled events.
    """

    def __init__(self, db_session: Session):
        """
        Initialize repository with database session.

        Args:
            db_session: SQLAlchemy session instance
        """
        self.db_session = db_session

    def create(self, event: ScheduledEvent) -> ScheduledEvent:
        """
        Create a new scheduled event.

        Args:
            event: ScheduledEvent instance to create

        Returns:
            Created event with ID populated

        Example:
            >>> event = ScheduledEvent(
            ...     scheduled_time=datetime(2025, 10, 31, 15, 0),
            ...     target_channel_id='C123456',
            ...     message='Meeting at 3pm'
            ... )
            >>> created = repo.create(event)
            >>> print(created.id)
            1
        """
        try:
            self.db_session.add(event)
            self.db_session.commit()
            self.db_session.refresh(event)
            logger.info(f"Created scheduled event {event.id} for {event.scheduled_time}")
            return event
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to create scheduled event: {e}")
            raise

    def get_by_id(self, event_id: int) -> Optional[ScheduledEvent]:
        """
        Get scheduled event by ID.

        Args:
            event_id: Event ID

        Returns:
            ScheduledEvent if found, None otherwise
        """
        return self.db_session.query(ScheduledEvent).filter(
            ScheduledEvent.id == event_id
        ).first()

    def get_by_job_id(self, job_id: str) -> Optional[ScheduledEvent]:
        """
        Get scheduled event by APScheduler job ID.

        Args:
            job_id: APScheduler job ID

        Returns:
            ScheduledEvent if found, None otherwise
        """
        return self.db_session.query(ScheduledEvent).filter(
            ScheduledEvent.job_id == job_id
        ).first()

    def get_all(
        self,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = 0
    ) -> List[ScheduledEvent]:
        """
        Get all scheduled events with optional filtering.

        Args:
            status: Filter by status (pending, completed, cancelled, failed)
            limit: Maximum number of events to return
            offset: Number of events to skip (for pagination)

        Returns:
            List of scheduled events

        Example:
            >>> # Get all pending events
            >>> pending = repo.get_all(status='pending')
            >>> # Get first 10 events
            >>> first_page = repo.get_all(limit=10, offset=0)
        """
        query = self.db_session.query(ScheduledEvent)

        if status:
            query = query.filter(ScheduledEvent.status == status)

        # Order by scheduled time (soonest first)
        query = query.order_by(ScheduledEvent.scheduled_time.asc())

        if offset:
            query = query.offset(offset)

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_pending(self) -> List[ScheduledEvent]:
        """
        Get all pending scheduled events.

        Returns:
            List of pending events ordered by scheduled time
        """
        return self.get_all(status='pending')

    def get_upcoming(self, limit: int = 10) -> List[ScheduledEvent]:
        """
        Get upcoming pending events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of upcoming pending events
        """
        return self.db_session.query(ScheduledEvent).filter(
            and_(
                ScheduledEvent.status == 'pending',
                ScheduledEvent.scheduled_time > datetime.utcnow()
            )
        ).order_by(ScheduledEvent.scheduled_time.asc()).limit(limit).all()

    def get_by_creator(self, user_id: str) -> List[ScheduledEvent]:
        """
        Get all events created by a specific user.

        Args:
            user_id: Slack user ID

        Returns:
            List of events created by this user
        """
        return self.db_session.query(ScheduledEvent).filter(
            ScheduledEvent.created_by_user_id == user_id
        ).order_by(ScheduledEvent.created_at.desc()).all()

    def update(self, event: ScheduledEvent) -> ScheduledEvent:
        """
        Update an existing scheduled event.

        Args:
            event: ScheduledEvent instance with updated fields

        Returns:
            Updated event

        Example:
            >>> event = repo.get_by_id(1)
            >>> event.message = 'Updated message'
            >>> event.updated_at = datetime.utcnow()
            >>> updated = repo.update(event)
        """
        try:
            event.updated_at = datetime.utcnow()
            self.db_session.commit()
            self.db_session.refresh(event)
            logger.info(f"Updated scheduled event {event.id}")
            return event
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Failed to update scheduled event {event.id}: {e}")
            raise

    def mark_completed(self, event_id: int) -> Optional[ScheduledEvent]:
        """
        Mark event as completed.

        Args:
            event_id: Event ID

        Returns:
            Updated event if found, None otherwise
        """
        event = self.get_by_id(event_id)
        if event:
            event.status = 'completed'
            event.executed_at = datetime.utcnow()
            event.updated_at = datetime.utcnow()
            return self.update(event)
        return None

    def mark_failed(self, event_id: int, error_message: str) -> Optional[ScheduledEvent]:
        """
        Mark event as failed with error message.

        Args:
            event_id: Event ID
            error_message: Error details

        Returns:
            Updated event if found, None otherwise
        """
        event = self.get_by_id(event_id)
        if event:
            event.status = 'failed'
            event.error_message = error_message
            event.executed_at = datetime.utcnow()
            event.updated_at = datetime.utcnow()
            return self.update(event)
        return None

    def cancel(self, event_id: int) -> Optional[ScheduledEvent]:
        """
        Cancel a pending event.

        Args:
            event_id: Event ID

        Returns:
            Updated event if found and was pending, None otherwise
        """
        event = self.get_by_id(event_id)
        if event and event.can_be_cancelled():
            event.status = 'cancelled'
            event.updated_at = datetime.utcnow()
            return self.update(event)
        return None

    def delete(self, event_id: int) -> bool:
        """
        Delete a scheduled event.

        Args:
            event_id: Event ID

        Returns:
            True if deleted, False if not found
        """
        event = self.get_by_id(event_id)
        if event:
            try:
                self.db_session.delete(event)
                self.db_session.commit()
                logger.info(f"Deleted scheduled event {event_id}")
                return True
            except Exception as e:
                self.db_session.rollback()
                logger.error(f"Failed to delete scheduled event {event_id}: {e}")
                raise
        return False

    def count_by_status(self, status: str) -> int:
        """
        Count events by status.

        Args:
            status: Status to count

        Returns:
            Number of events with this status
        """
        return self.db_session.query(ScheduledEvent).filter(
            ScheduledEvent.status == status
        ).count()

    def count_pending(self) -> int:
        """
        Count pending events.

        Returns:
            Number of pending events
        """
        return self.count_by_status('pending')
