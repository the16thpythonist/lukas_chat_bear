"""
Reusable database query builders for dashboard backend.
Provides functions for building complex queries with pagination and filtering.
"""
from sqlalchemy import and_, or_, func
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def paginate(query, page=1, limit=50):
    """
    Apply pagination to a SQLAlchemy query and return results with metadata.

    Args:
        query: SQLAlchemy query object
        page: Page number (1-indexed)
        limit: Items per page

    Returns:
        dict: {
            'items': List of query results,
            'page': Current page number,
            'limit': Items per page,
            'total': Total number of items,
            'pages': Total number of pages
        }

    Note:
        This is a reusable utility for all paginated endpoints.
        Implements LIMIT/OFFSET pagination per T035.5 requirement.
    """
    # Ensure page and limit are valid
    page = max(1, int(page))
    limit = max(1, min(100, int(limit)))  # Cap at 100 items per page

    # Get total count
    total = query.count()

    # Calculate total pages
    pages = (total + limit - 1) // limit if total > 0 else 0

    # Calculate offset
    offset = (page - 1) * limit

    # Apply pagination
    items = query.limit(limit).offset(offset).all()

    return {
        'items': items,
        'page': page,
        'limit': limit,
        'total': total,
        'pages': pages
    }


def build_activity_query(session, filters=None):
    """
    Build a query for activity logs (bot messages) with optional filters.

    Args:
        session: SQLAlchemy session
        filters: dict with optional keys:
            - start_date: Filter messages after this date (ISO format)
            - end_date: Filter messages before this date (ISO format)
            - recipient: Filter by user_id (from conversation)
            - channel_type: Filter by channel type ('dm', 'channel', 'thread')

    Returns:
        SQLAlchemy query object

    Note:
        Implements query logic per data-model.md activity log query.
        Uses indexes: idx_messages_timestamp, idx_messages_conversation_sender
    """
    from backend.models import Message, Conversation, TeamMember

    # Base query: JOIN messages with conversations and team_members
    query = session.query(
        Message.id,
        Message.content,
        Message.timestamp,
        Message.token_count,
        Message.conversation_id,
        Conversation.channel_id,
        Conversation.channel_type,
        Conversation.team_member_id.label('user_id'),
        TeamMember.display_name,
        TeamMember.real_name
    ).join(
        Conversation, Message.conversation_id == Conversation.id
    ).outerjoin(
        TeamMember, Conversation.team_member_id == TeamMember.id
    ).filter(
        Message.sender_type == 'bot'  # Only bot messages
    )

    # Apply filters if provided
    if filters:
        conditions = []

        # Date range filter
        if filters.get('start_date'):
            try:
                start_date = datetime.fromisoformat(filters['start_date'])
                conditions.append(Message.timestamp >= start_date)
            except ValueError:
                logger.warning(f"Invalid start_date format: {filters['start_date']}")

        if filters.get('end_date'):
            try:
                end_date = datetime.fromisoformat(filters['end_date'])
                conditions.append(Message.timestamp <= end_date)
            except ValueError:
                logger.warning(f"Invalid end_date format: {filters['end_date']}")

        # Recipient filter (by slack_user_id)
        if filters.get('recipient'):
            conditions.append(TeamMember.slack_user_id == filters['recipient'])

        # Channel type filter
        if filters.get('channel_type'):
            conditions.append(Conversation.channel_type == filters['channel_type'])

        if conditions:
            query = query.filter(and_(*conditions))

    # Order by timestamp (most recent first)
    query = query.order_by(Message.timestamp.desc())

    return query


def build_images_query(session, filters=None):
    """
    Build a query for generated images with optional filters.

    Args:
        session: SQLAlchemy session
        filters: dict with optional keys:
            - start_date: Filter images after this date (ISO format)
            - end_date: Filter images before this date (ISO format)
            - status: Filter by status ('pending', 'posted', 'failed')

    Returns:
        SQLAlchemy query object

    Note:
        Implements query logic per data-model.md images query.
        Uses index: idx_generated_images_created_status
    """
    from backend.models import GeneratedImage

    # Base query
    query = session.query(GeneratedImage)

    # Apply filters if provided
    if filters:
        conditions = []

        # Date range filter
        if filters.get('start_date'):
            try:
                start_date = datetime.fromisoformat(filters['start_date'])
                conditions.append(GeneratedImage.created_at >= start_date)
            except ValueError:
                logger.warning(f"Invalid start_date format: {filters['start_date']}")

        if filters.get('end_date'):
            try:
                end_date = datetime.fromisoformat(filters['end_date'])
                conditions.append(GeneratedImage.created_at <= end_date)
            except ValueError:
                logger.warning(f"Invalid end_date format: {filters['end_date']}")

        # Status filter
        if filters.get('status'):
            conditions.append(GeneratedImage.status == filters['status'])

        if conditions:
            query = query.filter(and_(*conditions))

    # Order by created_at (most recent first)
    query = query.order_by(GeneratedImage.created_at.desc())

    return query


def build_events_query(session, event_type='upcoming', filters=None):
    """
    Build a query for scheduled events (tasks).

    Args:
        session: SQLAlchemy session
        event_type: 'upcoming' for pending events, 'completed' for historical events
        filters: dict with optional keys (for completed events):
            - status: Filter by status ('completed', 'failed', 'cancelled')

    Returns:
        SQLAlchemy query object

    Note:
        Implements query logic per data-model.md events queries.
        Uses indexes: idx_scheduled_tasks_status_time, idx_scheduled_tasks_executed
    """
    from backend.models import ScheduledTask

    # Base query
    query = session.query(ScheduledTask)

    if event_type == 'upcoming':
        # Upcoming events: pending status, scheduled in the future
        query = query.filter(
            and_(
                ScheduledTask.status == 'pending',
                ScheduledTask.scheduled_at >= func.current_timestamp()
            )
        ).order_by(ScheduledTask.scheduled_at.asc())

    elif event_type == 'completed':
        # Completed events: completed, failed, or cancelled status
        query = query.filter(
            ScheduledTask.status.in_(['completed', 'failed', 'cancelled'])
        )

        # Apply status filter if provided
        if filters and filters.get('status'):
            query = query.filter(ScheduledTask.status == filters['status'])

        # Order by execution time (most recent first)
        query = query.order_by(ScheduledTask.executed_at.desc())

    return query


def get_upcoming_events(session, limit=50):
    """
    Get list of upcoming (pending) scheduled events.

    Args:
        session: SQLAlchemy session
        limit: Maximum number of events to return

    Returns:
        List of upcoming events as dictionaries

    Note:
        Implements T068 requirement for upcoming events query.
        Sorted by scheduled_time ASC (soonest first).
    """
    query = build_events_query(session, event_type='upcoming')
    events = query.limit(limit).all()

    return [
        {
            'id': event.id,
            'task_type': event.task_type,
            'scheduled_time': event.scheduled_at.isoformat() if event.scheduled_at else None,
            'target_type': event.target_type,
            'target_id': event.target_id,
            'status': event.status,
            'metadata': event.meta,
            'created_at': event.created_at.isoformat() if event.created_at else None
        }
        for event in events
    ]


def get_completed_events(session, page=1, limit=50):
    """
    Get paginated list of completed scheduled events.

    Args:
        session: SQLAlchemy session
        page: Page number (1-indexed)
        limit: Items per page

    Returns:
        dict: Paginated results with metadata

    Note:
        Implements T068 requirement for completed events query.
        Sorted by executed_at DESC (most recent first).
    """
    query = build_events_query(session, event_type='completed')
    paginated = paginate(query, page=page, limit=limit)

    # Convert items to dictionaries
    events = [
        {
            'id': event.id,
            'task_type': event.task_type,
            'scheduled_time': event.scheduled_at.isoformat() if event.scheduled_at else None,
            'executed_at': event.executed_at.isoformat() if event.executed_at else None,
            'status': event.status,
            'metadata': event.meta,
            'error_message': event.error_message,
            'created_at': event.created_at.isoformat() if event.created_at else None
        }
        for event in paginated['items']
    ]

    return {
        'events': events,
        'page': paginated['page'],
        'limit': paginated['limit'],
        'total': paginated['total'],
        'pages': paginated['pages']
    }
