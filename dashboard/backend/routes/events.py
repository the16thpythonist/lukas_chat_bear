"""
Events API Routes

Endpoints for viewing scheduled events (upcoming and completed).
"""

from flask import Blueprint, jsonify, request
from backend.auth import require_auth
from backend.services import get_session, get_upcoming_events, get_completed_events
from backend.utils.errors import handle_exception
import logging

logger = logging.getLogger(__name__)

events_bp = Blueprint('events', __name__)


@events_bp.route('/upcoming', methods=['GET'])
@require_auth
def upcoming():
    """
    Get list of upcoming (pending) scheduled events.

    Query Parameters:
        limit (int): Maximum number of events to return (default: 50, max: 100)

    Returns:
        200: List of upcoming events sorted by scheduled_time ASC
        500: Database error
    """
    try:
        # Get limit parameter (default 50, max 100)
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 100)  # Cap at 100

        # Get database session
        session = get_session()

        # Get upcoming events
        events = get_upcoming_events(session, limit=limit)

        return jsonify({
            'events': events,
            'count': len(events)
        }), 200

    except Exception as e:
        logger.error(f"Error fetching upcoming events: {e}")
        return handle_exception(e)


@events_bp.route('/completed', methods=['GET'])
@require_auth
def completed():
    """
    Get paginated list of completed scheduled events.

    Query Parameters:
        page (int): Page number (default: 1)
        limit (int): Items per page (default: 50, max: 100)

    Returns:
        200: Paginated list of completed events sorted by executed_at DESC
        500: Database error
    """
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)

        # Validate parameters
        page = max(1, page)
        limit = min(max(1, limit), 100)  # Between 1 and 100

        # Get database session
        session = get_session()

        # Get completed events
        result = get_completed_events(session, page=page, limit=limit)

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error fetching completed events: {e}")
        return handle_exception(e)
