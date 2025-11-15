"""
Scheduled Events API Routes

Proxies scheduled events requests to the bot internal API.
Provides dashboard access to view, create, edit, and cancel scheduled channel messages.

All endpoints require authentication.
"""

from flask import Blueprint, request, jsonify
import logging

from ..auth import require_auth
from ..services.bot_invoker import invoke_bot_internal_api

logger = logging.getLogger(__name__)

scheduled_events_bp = Blueprint('scheduled_events', __name__)


@scheduled_events_bp.route('', methods=['GET'])
@require_auth
def list_scheduled_events():
    """
    List scheduled events with optional filtering.

    Query Parameters:
        status: Filter by status (pending, completed, cancelled, failed)
        limit: Maximum number of results (default: 100)
        offset: Skip N results (default: 0)

    Returns:
        200: List of scheduled events
        500: Bot API error
    """
    # Forward query parameters
    params = {
        'status': request.args.get('status'),
        'limit': request.args.get('limit', 100),
        'offset': request.args.get('offset', 0)
    }
    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}

    try:
        response = invoke_bot_internal_api(
            method='GET',
            endpoint='/api/internal/scheduled-events',
            params=params
        )
        return jsonify(response), 200
    except Exception as e:
        logger.error(f"Error listing scheduled events: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scheduled_events_bp.route('', methods=['POST'])
@require_auth
def create_scheduled_event():
    """
    Create a new scheduled event.

    Request Body:
        {
            "scheduled_time": "2025-10-31T15:00:00Z",
            "target_channel_id": "C123456",
            "target_channel_name": "#general",
            "message": "Meeting reminder",
            "created_by_user_id": "U123456",
            "created_by_user_name": "Admin"
        }

    Returns:
        201: Event created successfully
        400: Validation error
        500: Bot API error
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        response = invoke_bot_internal_api(
            method='POST',
            endpoint='/api/internal/scheduled-events',
            json=data
        )

        # Return 201 for created
        return jsonify(response), 201
    except Exception as e:
        logger.error(f"Error creating scheduled event: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scheduled_events_bp.route('/<int:event_id>', methods=['GET'])
@require_auth
def get_scheduled_event(event_id):
    """
    Get details of a specific scheduled event.

    Path Parameters:
        event_id: Event ID

    Returns:
        200: Event details
        404: Event not found
        500: Bot API error
    """
    try:
        response = invoke_bot_internal_api(
            method='GET',
            endpoint=f'/api/internal/scheduled-events/{event_id}'
        )
        return jsonify(response), 200
    except Exception as e:
        logger.error(f"Error getting scheduled event {event_id}: {e}")
        # Check if it's a 404
        if 'not found' in str(e).lower():
            return jsonify({
                'success': False,
                'error': 'Event not found'
            }), 404
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scheduled_events_bp.route('/<int:event_id>', methods=['PUT'])
@require_auth
def update_scheduled_event(event_id):
    """
    Update a pending scheduled event's time and/or message.

    Path Parameters:
        event_id: Event ID

    Request Body:
        {
            "scheduled_time": "2025-10-31T16:00:00Z",  // optional
            "message": "Updated message"  // optional
        }

    Returns:
        200: Event updated successfully
        400: Cannot edit or validation error
        404: Event not found
        500: Bot API error
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        response = invoke_bot_internal_api(
            method='PUT',
            endpoint=f'/api/internal/scheduled-events/{event_id}',
            json=data
        )
        return jsonify(response), 200
    except Exception as e:
        logger.error(f"Error updating scheduled event {event_id}: {e}")
        # Determine appropriate status code
        error_str = str(e).lower()
        if 'not found' in error_str:
            status_code = 404
        elif 'cannot edit' in error_str or 'must be in the future' in error_str:
            status_code = 400
        else:
            status_code = 500

        return jsonify({
            'success': False,
            'error': str(e)
        }), status_code


@scheduled_events_bp.route('/<int:event_id>', methods=['DELETE'])
@require_auth
def cancel_scheduled_event(event_id):
    """
    Cancel a pending scheduled event.

    Path Parameters:
        event_id: Event ID

    Returns:
        200: Event cancelled successfully
        400: Cannot cancel
        404: Event not found
        500: Bot API error
    """
    try:
        response = invoke_bot_internal_api(
            method='DELETE',
            endpoint=f'/api/internal/scheduled-events/{event_id}'
        )
        return jsonify(response), 200
    except Exception as e:
        logger.error(f"Error cancelling scheduled event {event_id}: {e}")
        # Determine appropriate status code
        error_str = str(e).lower()
        if 'not found' in error_str:
            status_code = 404
        elif 'cannot cancel' in error_str:
            status_code = 400
        else:
            status_code = 500

        return jsonify({
            'success': False,
            'error': str(e)
        }), status_code


# ===== UNIFIED VIEW ENDPOINTS =====


@scheduled_events_bp.route('/all', methods=['GET'])
@require_auth
def list_all_scheduled_events():
    """
    Get unified view of all scheduled events.

    Includes:
    - User-created channel messages
    - System recurring tasks (Random DMs, Image Posts)

    Query Parameters:
        status: Filter by status (pending, completed, cancelled, failed)
        limit: Maximum number of results (default: 100)

    Returns:
        200: Unified list of all scheduled events
        500: Bot API error
    """
    # Forward query parameters
    params = {
        'status': request.args.get('status'),
        'limit': request.args.get('limit', 100)
    }
    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}

    try:
        response = invoke_bot_internal_api(
            method='GET',
            endpoint='/api/internal/all-scheduled-events',
            params=params
        )
        return jsonify(response), 200
    except Exception as e:
        logger.error(f"Error listing all scheduled events: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@scheduled_events_bp.route('/recurring-task/<job_name>', methods=['DELETE'])
@require_auth
def cancel_recurring_task(job_name):
    """
    Cancel a recurring task (random_dm_task or image_post_task).

    Path Parameters:
        job_name: Job name (random_dm_task or image_post_task)

    Returns:
        200: Task cancelled successfully
        400: Invalid job name
        500: Bot API error
    """
    try:
        response = invoke_bot_internal_api(
            method='DELETE',
            endpoint=f'/api/internal/recurring-task/{job_name}'
        )
        return jsonify(response), 200
    except Exception as e:
        logger.error(f"Error cancelling recurring task {job_name}: {e}")
        # Determine appropriate status code
        error_str = str(e).lower()
        if 'invalid' in error_str:
            status_code = 400
        else:
            status_code = 500

        return jsonify({
            'success': False,
            'error': str(e)
        }), status_code
