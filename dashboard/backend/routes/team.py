"""
Team Members API Routes

Provides endpoints for fetching team member information.
Used for user selection in manual controls (DM target dropdown).
"""

from flask import Blueprint, jsonify
import logging

from ..auth import require_auth
from ..services.database import session_scope
from src.models.team_member import TeamMember

logger = logging.getLogger(__name__)

team_bp = Blueprint('team', __name__)


@team_bp.route('', methods=['GET'])
@require_auth
def get_team_members():
    """
    Get list of active team members.

    Returns team members who have sent at least one message (message_count > 0),
    sorted by display name. Used for user selection in manual DM controls.

    Response (Success - 200):
        [
            {
                "slack_user_id": "U123456",
                "display_name": "John Doe",
                "real_name": "John Doe",
                "message_count": 42
            },
            ...
        ]

    Response (Error - 500):
        {
            "error": "Failed to fetch team members",
            "message": "Database error details"
        }

    Errors:
        - 401: Unauthorized (no session)
        - 500: Database error
    """
    try:
        with session_scope() as session:
            # Query active team members (total_messages_sent > 0)
            members = (
                session.query(TeamMember)
                .filter(TeamMember.total_messages_sent > 0)
                .order_by(TeamMember.display_name)
                .all()
            )

            # Convert to dict
            members_data = [
                {
                    'slack_user_id': m.slack_user_id,
                    'display_name': m.display_name,
                    'real_name': m.real_name,
                    'message_count': m.total_messages_sent
                }
                for m in members
            ]

            logger.debug(f"Fetched {len(members_data)} team members")

            return jsonify(members_data), 200

    except Exception as e:
        logger.error(f"Failed to fetch team members: {e}", exc_info=True)
        return jsonify({
            'error': 'Failed to fetch team members',
            'message': str(e)
        }), 500


# Export blueprint
__all__ = ['team_bp']
