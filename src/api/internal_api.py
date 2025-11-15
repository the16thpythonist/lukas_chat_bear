"""
Internal Bot API for Dashboard Communication

This Flask API exposes bot services to the dashboard container via the internal Docker network.
It is NOT exposed to the public internet - only accessible by dashboard container.

Architecture:
- Runs on port 5001 (internal only)
- Provides endpoints for manual control actions
- Returns JSON responses
- No authentication (trust internal network)

Endpoints:
- POST /api/internal/generate-image - Trigger DALL-E image generation
- POST /api/internal/send-dm - Send random proactive DM
- GET /api/internal/health - Health check
"""

from flask import Flask, request, jsonify
import logging
import os
from datetime import datetime
import json
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Lazy import bot services (imported when first endpoint is called)
_services_initialized = False
ImageService = None
ProactiveDMService = None
ScheduledTask = None
db_session = None
slack_app = None
slack_client = None


def initialize_services():
    """
    Lazy initialization of bot services.
    Only imports when first API call is made.
    """
    global _services_initialized, ImageService, ProactiveDMService, ScheduledTask, db_session
    global slack_app, slack_client

    if _services_initialized:
        return True

    try:
        from src.services.image_service import ImageService as ImgSvc
        from src.services.proactive_dm_service import send_random_proactive_dm
        from src.models.scheduled_task import ScheduledTask as Task
        from src.utils.database import get_db_session
        from slack_bolt import App
        from slack_sdk import WebClient  # Sync client for ImageService
        from slack_sdk.web.async_client import AsyncWebClient  # Async client for DM service

        ImageService = ImgSvc
        ProactiveDMService = send_random_proactive_dm  # Use module-level function
        ScheduledTask = Task
        db_session = get_db_session

        # Initialize Slack clients for posting
        slack_token = os.getenv("SLACK_BOT_TOKEN")
        if not slack_token:
            logger.warning("SLACK_BOT_TOKEN not found - Slack operations will fail")
            slack_client = None
            slack_app = None
        else:
            # Initialize both sync and async clients
            # - ImageService needs sync client (_post_to_slack is synchronous)
            # - ProactiveDMService needs async client (uses await)
            global slack_client_sync, slack_client_async
            slack_client_sync = WebClient(token=slack_token)
            slack_client_async = AsyncWebClient(token=slack_token)
            slack_client = slack_client_async  # Default to async

            # Create minimal app instance (we don't need full Socket Mode for API calls)
            slack_app = App(token=slack_token)
            logger.debug("Slack clients initialized for internal API (sync + async)")

        _services_initialized = True
        logger.info("✓ Bot services initialized for internal API")
        return True

    except ImportError as e:
        logger.error(f"Failed to import bot services: {e}")
        return False


@app.before_request
def log_request():
    """Log all incoming requests for debugging"""
    logger.info(f"Internal API: {request.method} {request.path} from {request.remote_addr}")


@app.route('/api/internal/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for dashboard to verify bot API is running.

    Returns:
        200: API is healthy and services are initialized
        503: API running but services failed to initialize
    """
    services_ok = initialize_services()

    return jsonify({
        'status': 'healthy' if services_ok else 'degraded',
        'services_initialized': services_ok,
        'timestamp': datetime.utcnow().isoformat()
    }), 200 if services_ok else 503


@app.route('/api/internal/generate-image', methods=['POST'])
async def generate_image_endpoint():
    """
    Trigger DALL-E image generation and post to Slack.

    Request Body:
        {
            "theme": "optional theme string",
            "channel_id": "optional Slack channel ID"
        }

    Returns:
        200: Image generated successfully
        400: Invalid request
        500: Image generation failed
    """
    try:
        # Initialize services if needed
        if not initialize_services():
            return jsonify({
                'success': False,
                'error': 'Bot services failed to initialize'
            }), 500

        # Parse request
        data = request.get_json() or {}
        theme = data.get('theme')
        channel_id = data.get('channel_id')

        logger.info(f"Manual image generation: theme={theme}, channel={channel_id}")

        # Create database session
        session = db_session()

        try:
            # Initialize image service with SYNC Slack client (ImageService uses synchronous _post_to_slack)
            image_service = ImageService(db_session=session, slack_client=slack_client_sync)

            # Get default channel if not specified
            if not channel_id:
                from src.utils.config_loader import config
                channel_id = config.get("bot.image_posting.channel", "#random")

            # Generate and post image (async call)
            result = await image_service.generate_and_post(
                channel_id=channel_id,
                theme=theme
            )

            if not result:
                return jsonify({
                    'success': False,
                    'error': 'Image service returned no result'
                }), 500

            # Log to scheduled_tasks for audit trail
            try:
                task = ScheduledTask(
                    task_type='manual_image',
                    scheduled_time=datetime.utcnow(),
                    executed_at=datetime.utcnow(),
                    status='completed',
                    metadata=json.dumps({
                        'source': 'dashboard_api',
                        'theme': theme,
                        'target_channel': channel_id or 'default',
                        'image_id': result.id
                    }),
                    target_type='manual',
                    target_id=channel_id or 'dashboard'
                )
                session.add(task)
                session.commit()
                logger.debug("Logged manual image generation to scheduled_tasks")
            except Exception as log_error:
                logger.error(f"Failed to log manual action: {log_error}")
                # Don't fail the request if logging fails

            logger.info(f"Image generated successfully: ID={result.id}")

            return jsonify({
                'success': True,
                'image_id': result.id,
                'image_url': result.image_url,
                'prompt': result.prompt
            }), 200

        finally:
            # Always close the session
            session.close()

    except Exception as e:
        logger.error(f"Image generation failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


async def _send_targeted_dm_internal(
    user_id: str,
    session,
    slack_client,
) -> Dict[str, Any]:
    """
    Internal helper to send DM to a specific user.

    This bypasses the random selection and sends directly to the specified user.
    """
    from src.services.persona_service import PersonaService
    from src.repositories.team_member_repo import TeamMemberRepository
    from src.services.engagement_service import EngagementService

    result = {
        "success": False,
        "user_selected": user_id,
        "message_sent": None,
        "error": None
    }

    try:
        # Verify user exists in database
        team_member_repo = TeamMemberRepository(session)
        recipient = team_member_repo.get_by_slack_id(user_id)

        if not recipient:
            result["error"] = f"User {user_id} not found in team members"
            return result

        # Generate greeting message
        persona_service = PersonaService()
        greeting = persona_service.get_greeting_template()
        result["message_sent"] = greeting

        # Open DM conversation
        logger.info(f"Opening DM conversation with user {user_id}")
        dm_response = await slack_client.conversations_open(users=[user_id])

        if not dm_response.get("ok"):
            result["error"] = f"Failed to open DM: {dm_response.get('error', 'unknown')}"
            return result

        dm_channel_id = dm_response["channel"]["id"]

        # Send message
        msg_response = await slack_client.chat_postMessage(
            channel=dm_channel_id,
            text=greeting
        )

        if not msg_response.get("ok"):
            result["error"] = f"Failed to send message: {msg_response.get('error', 'unknown')}"
            return result

        # Update user's last_proactive_dm_at timestamp
        engagement_service = EngagementService(session)
        engagement_service.update_last_proactive_dm(recipient)

        result["success"] = True
        logger.info(f"Successfully sent targeted DM to {user_id}")
        return result

    except Exception as e:
        logger.error(f"Error sending targeted DM: {e}", exc_info=True)
        result["error"] = str(e)
        return result


@app.route('/api/internal/send-dm', methods=['POST'])
async def send_dm_endpoint():
    """
    Send proactive DM to a user (random or targeted).

    Request Body:
        {
            "user_id": "optional Slack user ID (U123456). If omitted, selects random user."
        }

    Returns:
        200: DM sent successfully
        400: Invalid request
        500: DM sending failed
    """
    try:
        # Initialize services if needed
        if not initialize_services():
            return jsonify({
                'success': False,
                'error': 'Bot services failed to initialize'
            }), 500

        # Parse request
        data = request.get_json() or {}
        user_id = data.get('user_id')

        logger.info(f"Manual DM: user_id={user_id or 'random'}")

        # Create database session
        session = db_session()

        try:
            # Route to appropriate handler based on whether user_id is provided
            if user_id:
                # Send to specific user (uses ASYNC client for await operations)
                logger.info(f"Sending targeted DM to user {user_id}")
                result = await _send_targeted_dm_internal(
                    user_id=user_id,
                    session=session,
                    slack_client=slack_client_async
                )
            else:
                # Send to random user (uses ASYNC client for await operations)
                logger.info("Sending random DM")
                result = await ProactiveDMService(
                    app=slack_app,
                    db_session=session,
                    slack_client=slack_client_async
                )

            if not result or not result.get('success'):
                error_msg = result.get('error', 'DM service returned failure') if result else 'DM service returned no result'
                reason = result.get('reason') if result else None

                # Provide user-friendly error messages
                if reason == 'no_eligible_users':
                    user_friendly_msg = 'No eligible users available to send DM (all users may have been contacted recently)'
                else:
                    user_friendly_msg = error_msg

                return jsonify({
                    'success': False,
                    'error': user_friendly_msg
                }), 500

            target_user = result.get('user_selected', 'unknown')

            # Log to scheduled_tasks for audit trail
            try:
                task = ScheduledTask(
                    task_type='manual_dm',
                    scheduled_time=datetime.utcnow(),
                    executed_at=datetime.utcnow(),
                    status='completed',
                    metadata=json.dumps({
                        'source': 'dashboard_api',
                        'target_user': target_user,
                        'random_selection': user_id is None
                    }),
                    target_type='manual',
                    target_id=target_user
                )
                session.add(task)
                session.commit()
                logger.debug("Logged manual DM to scheduled_tasks")
            except Exception as log_error:
                logger.error(f"Failed to log manual action: {log_error}")
                # Don't fail the request if logging fails

            logger.info(f"DM sent successfully to {target_user}")

            return jsonify({
                'success': True,
                'target_user': target_user,
                'message_preview': result.get('message_sent', '(no preview)')
            }), 200

        finally:
            # Always close the session
            session.close()

    except Exception as e:
        logger.error(f"DM sending failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ===== SCHEDULED EVENTS ENDPOINTS =====

def _get_or_init_scheduler():
    """
    Get the scheduler instance, initializing it if necessary.

    The internal API runs in a separate Flask process from the main bot,
    so it needs its own scheduler instance.

    Returns:
        BackgroundScheduler instance
    """
    from src.services.scheduler_service import get_scheduler, init_scheduler

    try:
        return get_scheduler()
    except RuntimeError:
        logger.info("Initializing scheduler for internal API process")
        return init_scheduler()


@app.route('/api/internal/scheduled-events', methods=['GET'])
def list_scheduled_events():
    """
    List all scheduled events with optional filtering.

    Query Parameters:
        status: Filter by status (pending, completed, cancelled, failed)
        limit: Maximum number of results (default: 100)
        offset: Skip N results (for pagination, default: 0)

    Returns:
        200: List of scheduled events
        500: Server error
    """
    try:
        if not initialize_services():
            return jsonify({'error': 'Bot services failed to initialize'}), 500

        from src.services.scheduled_event_service import ScheduledEventService

        # Parse query parameters
        status = request.args.get('status')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))

        session = db_session()
        try:
            event_service = ScheduledEventService(
                db_session=session,
                scheduler=_get_or_init_scheduler(),
                slack_client=slack_client_sync
            )

            events = event_service.get_all_events(status=status, limit=limit, offset=offset)

            return jsonify({
                'success': True,
                'count': len(events),
                'events': [event.to_dict() for event in events]
            }), 200

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failed to list scheduled events: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/internal/scheduled-events', methods=['POST'])
def create_scheduled_event():
    """
    Create a new scheduled event.

    Request Body:
        {
            "scheduled_time": "2025-10-31T15:00:00Z" (ISO format),
            "target_channel_id": "C123456",
            "target_channel_name": "#general",
            "message": "Meeting at 3pm",
            "created_by_user_id": "U123456" (optional),
            "created_by_user_name": "User Name" (optional)
        }

    Returns:
        201: Event created successfully
        400: Invalid request
        500: Server error
    """
    try:
        if not initialize_services():
            return jsonify({'error': 'Bot services failed to initialize'}), 500

        from src.services.scheduled_event_service import ScheduledEventService

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate required fields
        required_fields = ['scheduled_time', 'target_channel_id', 'message']
        missing = [f for f in required_fields if f not in data]
        if missing:
            return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

        # Parse scheduled time
        try:
            scheduled_time = datetime.fromisoformat(data['scheduled_time'].replace('Z', '+00:00'))
            # Convert to naive UTC
            scheduled_time = scheduled_time.replace(tzinfo=None)
        except ValueError as e:
            return jsonify({'error': f'Invalid scheduled_time format: {e}'}), 400

        session = db_session()
        try:
            event_service = ScheduledEventService(
                db_session=session,
                scheduler=_get_or_init_scheduler(),
                slack_client=slack_client_sync
            )

            event, error = event_service.create_event(
                scheduled_time=scheduled_time,
                target_channel_id=data['target_channel_id'],
                target_channel_name=data.get('target_channel_name', data['target_channel_id']),
                message=data['message'],
                created_by_user_id=data.get('created_by_user_id'),
                created_by_user_name=data.get('created_by_user_name')
            )

            if event:
                logger.info(f"Created scheduled event {event.id} via API")
                return jsonify({
                    'success': True,
                    'event': event.to_dict()
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': error
                }), 400

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failed to create scheduled event: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/internal/scheduled-events/<int:event_id>', methods=['GET'])
def get_scheduled_event(event_id):
    """
    Get a specific scheduled event by ID.

    Returns:
        200: Event details
        404: Event not found
        500: Server error
    """
    try:
        if not initialize_services():
            return jsonify({'error': 'Bot services failed to initialize'}), 500

        from src.services.scheduled_event_service import ScheduledEventService

        session = db_session()
        try:
            event_service = ScheduledEventService(
                db_session=session,
                scheduler=_get_or_init_scheduler(),
                slack_client=slack_client_sync
            )

            event = event_service.get_event(event_id)
            if event:
                return jsonify({
                    'success': True,
                    'event': event.to_dict()
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Event not found'
                }), 404

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failed to get scheduled event {event_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/internal/scheduled-events/<int:event_id>', methods=['PUT'])
def update_scheduled_event(event_id):
    """
    Update a scheduled event's time and/or message.

    Request Body:
        {
            "scheduled_time": "2025-10-31T16:00:00Z" (optional),
            "message": "Updated message" (optional)
        }

    Returns:
        200: Event updated successfully
        400: Invalid request or cannot edit
        404: Event not found
        500: Server error
    """
    try:
        if not initialize_services():
            return jsonify({'error': 'Bot services failed to initialize'}), 500

        from src.services.scheduled_event_service import ScheduledEventService

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Parse scheduled time if provided
        scheduled_time = None
        if 'scheduled_time' in data:
            try:
                scheduled_time = datetime.fromisoformat(data['scheduled_time'].replace('Z', '+00:00'))
                scheduled_time = scheduled_time.replace(tzinfo=None)
            except ValueError as e:
                return jsonify({'error': f'Invalid scheduled_time format: {e}'}), 400

        session = db_session()
        try:
            event_service = ScheduledEventService(
                db_session=session,
                scheduler=_get_or_init_scheduler(),
                slack_client=slack_client_sync
            )

            event, error = event_service.update_event(
                event_id=event_id,
                scheduled_time=scheduled_time,
                message=data.get('message')
            )

            if event:
                logger.info(f"Updated scheduled event {event_id} via API")
                return jsonify({
                    'success': True,
                    'event': event.to_dict()
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': error or 'Event not found'
                }), 404 if 'not found' in (error or '').lower() else 400

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failed to update scheduled event {event_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/internal/scheduled-events/<int:event_id>', methods=['DELETE'])
def cancel_scheduled_event(event_id):
    """
    Cancel a pending scheduled event.

    Returns:
        200: Event cancelled successfully
        400: Cannot cancel (already executed, etc.)
        404: Event not found
        500: Server error
    """
    try:
        if not initialize_services():
            return jsonify({'error': 'Bot services failed to initialize'}), 500

        from src.services.scheduled_event_service import ScheduledEventService

        session = db_session()
        try:
            event_service = ScheduledEventService(
                db_session=session,
                scheduler=_get_or_init_scheduler(),
                slack_client=slack_client_sync
            )

            success, error = event_service.cancel_event(event_id)

            if success:
                logger.info(f"Cancelled scheduled event {event_id} via API")
                return jsonify({
                    'success': True,
                    'message': 'Event cancelled successfully'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': error or 'Event not found'
                }), 404 if 'not found' in (error or '').lower() else 400

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failed to cancel scheduled event {event_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/internal/all-scheduled-events', methods=['GET'])
def list_all_scheduled_events():
    """
    Get unified view of all scheduled events.

    Includes:
    - User-created channel messages (scheduled_events table)
    - System recurring tasks: Random DMs and Image Posts (scheduled_tasks table)

    Query Parameters:
        status: Filter by status (pending, completed, cancelled, failed)
        limit: Maximum number of results (default: 100)

    Returns:
        200: Unified list of all scheduled events
        500: Server error
    """
    try:
        if not initialize_services():
            return jsonify({'error': 'Bot services failed to initialize'}), 500

        from src.services.unified_schedule_service import UnifiedScheduleService

        # Parse query parameters
        status = request.args.get('status')
        limit = int(request.args.get('limit', 100))

        session = db_session()
        try:
            unified_service = UnifiedScheduleService(
                db_session=session,
                scheduler=_get_or_init_scheduler()
            )

            events = unified_service.get_all_scheduled_events(
                status=status,
                limit=limit
            )

            return jsonify({
                'success': True,
                'count': len(events),
                'events': events
            }), 200

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failed to list all scheduled events: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/internal/recurring-task/<job_name>', methods=['DELETE'])
def cancel_recurring_task(job_name):
    """
    Cancel a recurring task (random_dm_task or image_post_task).

    This will:
    1. Remove the APScheduler job (stops future executions)
    2. Mark pending ScheduledTask records as cancelled

    Path Parameters:
        job_name: Job name (random_dm_task or image_post_task)

    Returns:
        200: Task cancelled successfully
        400: Invalid job name
        500: Server error
    """
    try:
        if not initialize_services():
            return jsonify({'error': 'Bot services failed to initialize'}), 500

        from src.services.unified_schedule_service import UnifiedScheduleService

        session = db_session()
        try:
            unified_service = UnifiedScheduleService(
                db_session=session,
                scheduler=_get_or_init_scheduler()
            )

            result = unified_service.cancel_recurring_task(job_name)

            if result['success']:
                return jsonify(result), 200
            else:
                return jsonify(result), 400

        finally:
            session.close()

    except Exception as e:
        logger.error(f"Failed to cancel recurring task {job_name}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ===== ERROR HANDLERS =====

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Endpoint not found',
        'message': 'This internal API endpoint does not exist'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'error': 'Internal server error',
        'message': str(error)
    }), 500


def run_api(host='0.0.0.0', port=5001):
    """
    Run the internal API server.

    Args:
        host: Host to bind to (default: 0.0.0.0 for Docker)
        port: Port to listen on (default: 5001)
    """
    port = int(os.getenv('INTERNAL_API_PORT', port))

    logger.info(f"Starting internal bot API on {host}:{port}")
    logger.info("⚠️  This API is for internal Docker network only - NOT exposed to public internet")

    # Run Flask in production mode (no debug, no reloader)
    app.run(
        host=host,
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True
    )


if __name__ == '__main__':
    run_api()
