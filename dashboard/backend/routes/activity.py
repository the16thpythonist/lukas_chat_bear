"""
Activity log routes for dashboard backend.
Provides endpoints for viewing bot message history.
"""
from flask import Blueprint, request, jsonify
from backend.auth import require_auth
from backend.services import get_session, paginate, build_activity_query
from backend.utils.errors import handle_exception, not_found_error
import logging

logger = logging.getLogger(__name__)

activity_bp = Blueprint('activity', __name__)


@activity_bp.route('', methods=['GET'])
@require_auth
def list_activity():
    """
    Get paginated list of bot messages with optional filters.

    Query Parameters:
        page (int): Page number (default: 1)
        limit (int): Items per page (default: 50, max: 100)
        start_date (str): Filter messages after this date (ISO format)
        end_date (str): Filter messages before this date (ISO format)
        recipient (str): Filter by user_id
        channel_type (str): Filter by channel type ('dm', 'channel', 'thread')

    Returns:
        200: Paginated list of messages with metadata
        500: Database error
    """
    try:
        # Parse query parameters
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)

        # Build filters
        filters = {}
        if request.args.get('start_date'):
            filters['start_date'] = request.args.get('start_date')
        if request.args.get('end_date'):
            filters['end_date'] = request.args.get('end_date')
        if request.args.get('recipient'):
            filters['recipient'] = request.args.get('recipient')
        if request.args.get('channel_type'):
            filters['channel_type'] = request.args.get('channel_type')

        # Get database session
        session = get_session()

        # Build and execute query
        query = build_activity_query(session, filters)
        result = paginate(query, page, limit)

        # Format results
        items = []
        for row in result['items']:
            items.append({
                'id': row.id,
                'content': row.content,
                'timestamp': row.timestamp.isoformat() if row.timestamp else None,
                'token_count': row.token_count,
                'conversation_id': row.conversation_id,
                'channel_id': row.channel_id,
                'channel_type': row.channel_type,
                'user_id': row.user_id,
                'display_name': row.display_name,
                'real_name': row.real_name
            })

        return jsonify({
            'items': items,
            'page': result['page'],
            'limit': result['limit'],
            'total': result['total'],
            'pages': result['pages']
        }), 200

    except Exception as e:
        logger.exception(f"Error fetching activity log: {e}")
        return handle_exception(e, include_details=False)


@activity_bp.route('/<string:message_id>', methods=['GET'])
@require_auth
def get_activity_detail(message_id):
    """
    Get detailed information about a specific message.

    Path Parameters:
        message_id (str): Message ID (UUID)

    Returns:
        200: Message details with conversation context
        404: Message not found
        500: Database error
    """
    try:
        from backend.models import Message, Conversation, TeamMember

        session = get_session()

        # Get message with conversation context
        result = session.query(
            Message,
            Conversation,
            TeamMember
        ).join(
            Conversation, Message.conversation_id == Conversation.id
        ).outerjoin(
            TeamMember, Conversation.team_member_id == TeamMember.id
        ).filter(
            Message.id == message_id,
            Message.sender_type == 'bot'
        ).first()

        if not result:
            return not_found_error('Message')

        message, conversation, team_member = result

        # Get conversation messages for context (last 5 messages)
        conversation_messages = session.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.timestamp.desc()).limit(5).all()

        return jsonify({
            'id': message.id,
            'content': message.content,
            'timestamp': message.timestamp.isoformat() if message.timestamp else None,
            'token_count': message.token_count,
            'conversation': {
                'id': conversation.id,
                'user_id': team_member.slack_user_id if team_member else None,
                'channel_id': conversation.channel_id,
                'channel_type': conversation.channel_type,
                'started_at': conversation.created_at.isoformat() if conversation.created_at else None
            },
            'user': {
                'display_name': team_member.display_name if team_member else None,
                'real_name': team_member.real_name if team_member else None
            },
            'context': [
                {
                    'id': msg.id,
                    'sender': msg.sender_type,
                    'content': msg.content[:200] + '...' if len(msg.content) > 200 else msg.content,
                    'timestamp': msg.timestamp.isoformat() if msg.timestamp else None
                }
                for msg in reversed(conversation_messages)
            ]
        }), 200

    except Exception as e:
        logger.exception(f"Error fetching message detail: {e}")
        return handle_exception(e, include_details=False)
