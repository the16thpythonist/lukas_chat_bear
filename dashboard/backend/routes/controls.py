"""
Manual Controls API Routes

Provides endpoints for admins to manually trigger bot actions:
- Generate and post DALL-E images
- Send random proactive DMs

All endpoints require authentication and implement rate limiting.
All actions are logged to scheduled_tasks table for audit trail.
"""

from flask import Blueprint, request, jsonify, session
from functools import wraps
from datetime import datetime, timedelta
import logging
from typing import Dict, Any

from ..auth import require_auth
from ..services.bot_invoker import invoke_image_generation, invoke_random_dm

logger = logging.getLogger(__name__)

controls_bp = Blueprint('controls', __name__)

# Rate limiting storage (in-memory for simplicity)
# Key: session_id + action_type, Value: list of timestamps
_rate_limit_tracker: Dict[str, list] = {}


def rate_limit(max_requests: int, window_seconds: int):
    """
    Rate limiting decorator for manual control endpoints.

    Args:
        max_requests: Maximum number of requests allowed in window
        window_seconds: Time window in seconds

    Returns:
        Decorated function that enforces rate limit

    Example:
        @rate_limit(max_requests=10, window_seconds=3600)  # 10 per hour
        def generate_image():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get session ID for rate limiting key
            session_id = session.get('session_id')
            if not session_id:
                # Fallback to IP address if no session (shouldn't happen with auth)
                session_id = request.remote_addr

            # Create rate limit key
            action_name = f.__name__
            rate_key = f"{session_id}:{action_name}"

            # Get current timestamp
            now = datetime.utcnow()
            cutoff_time = now - timedelta(seconds=window_seconds)

            # Initialize or clean up old timestamps for this key
            if rate_key not in _rate_limit_tracker:
                _rate_limit_tracker[rate_key] = []

            # Remove timestamps outside the window
            _rate_limit_tracker[rate_key] = [
                ts for ts in _rate_limit_tracker[rate_key]
                if ts > cutoff_time
            ]

            # Check if limit exceeded
            if len(_rate_limit_tracker[rate_key]) >= max_requests:
                oldest_timestamp = min(_rate_limit_tracker[rate_key])
                retry_after = int((oldest_timestamp + timedelta(seconds=window_seconds) - now).total_seconds())

                logger.warning(f"Rate limit exceeded for {action_name} by session {session_id}")

                return jsonify({
                    'error': 'Rate limit exceeded',
                    'message': f'Maximum {max_requests} requests per {window_seconds // 60} minutes. Please try again later.',
                    'retry_after_seconds': retry_after
                }), 429

            # Record this request
            _rate_limit_tracker[rate_key].append(now)

            # Call the actual endpoint
            return f(*args, **kwargs)

        return decorated_function
    return decorator


@controls_bp.route('/generate-image', methods=['POST'])
@require_auth
@rate_limit(max_requests=10, window_seconds=3600)  # 10 images per hour
def generate_image():
    """
    Manually trigger image generation and posting.

    Request Body:
        {
            "theme": "optional theme string (e.g., 'celebration', 'nature')",
            "channel_id": "optional Slack channel ID (e.g., 'C123456')"
        }

    Response (Success - 200):
        {
            "success": true,
            "message": "Image generated and posted successfully to channel C123456",
            "image_id": 42,
            "image_url": "file:///app/data/images/abc123.png",
            "prompt": "A joyful bear celebrating..."
        }

    Response (Failure - 500):
        {
            "success": false,
            "message": "OpenAI API key not configured or invalid",
            "error": "Detailed error message"
        }

    Response (Rate Limited - 429):
        {
            "error": "Rate limit exceeded",
            "message": "Maximum 10 requests per 60 minutes. Please try again later.",
            "retry_after_seconds": 1800
        }

    Errors:
        - 400: Invalid request body
        - 401: Unauthorized (no session)
        - 429: Rate limit exceeded
        - 500: Image generation failed (OpenAI, Slack, or internal error)
    """
    try:
        # Parse request body
        data = request.get_json() or {}

        theme = data.get('theme')
        channel_id = data.get('channel_id')

        # Validate inputs
        if theme and not isinstance(theme, str):
            return jsonify({
                'error': 'Invalid request',
                'message': 'Theme must be a string'
            }), 400

        if channel_id and not isinstance(channel_id, str):
            return jsonify({
                'error': 'Invalid request',
                'message': 'Channel ID must be a string'
            }), 400

        if channel_id and not channel_id.startswith('C'):
            return jsonify({
                'error': 'Invalid request',
                'message': 'Channel ID must start with "C" (e.g., C123456)'
            }), 400

        logger.info(f"Manual image generation requested: theme={theme}, channel={channel_id}")

        # Invoke bot service
        result = invoke_image_generation(theme=theme, channel_id=channel_id)

        # Return response based on result
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f"Image generation endpoint error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Internal server error during image generation',
            'error': str(e)
        }), 500


@controls_bp.route('/send-dm', methods=['POST'])
@require_auth
@rate_limit(max_requests=20, window_seconds=3600)  # 20 DMs per hour
def send_dm():
    """
    Manually trigger random DM to a user.

    Request Body:
        {
            "user_id": "optional Slack user ID (e.g., 'U123456'). If omitted, selects random user."
        }

    Response (Success - 200):
        {
            "success": true,
            "message": "Random DM sent successfully to user U123456",
            "target_user": "U123456",
            "dm_content": "Hey there! Just wanted to check in..."
        }

    Response (Failure - 500):
        {
            "success": false,
            "message": "No active users available to send DM",
            "error": "Detailed error message"
        }

    Response (Rate Limited - 429):
        {
            "error": "Rate limit exceeded",
            "message": "Maximum 20 requests per 60 minutes. Please try again later.",
            "retry_after_seconds": 1200
        }

    Errors:
        - 400: Invalid request body
        - 401: Unauthorized (no session)
        - 429: Rate limit exceeded
        - 500: DM sending failed (no users, Slack error, or internal error)
    """
    try:
        # Parse request body
        data = request.get_json() or {}

        user_id = data.get('user_id')

        # Validate inputs
        if user_id and not isinstance(user_id, str):
            return jsonify({
                'error': 'Invalid request',
                'message': 'User ID must be a string'
            }), 400

        if user_id and not user_id.startswith('U'):
            return jsonify({
                'error': 'Invalid request',
                'message': 'User ID must start with "U" (e.g., U123456)'
            }), 400

        logger.info(f"Manual DM requested: user_id={user_id or 'random'}")

        # Invoke bot service
        result = invoke_random_dm(user_id=user_id)

        # Return response based on result
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 500

    except Exception as e:
        logger.error(f"DM sending endpoint error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Internal server error during DM sending',
            'error': str(e)
        }), 500


# Export blueprint
__all__ = ['controls_bp']
