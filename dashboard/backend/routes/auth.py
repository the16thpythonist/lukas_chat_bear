"""
Authentication routes for dashboard backend.
Provides login, logout, and session check endpoints.
"""
from flask import Blueprint, request, jsonify
from backend.auth import login, logout, get_session_info, is_authenticated
from backend.utils.errors import validation_error
import logging

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login_route():
    """
    Authenticate with password and create session.

    Request Body:
        {
            "password": "admin-password"
        }

    Returns:
        200: Login successful
        400: Missing password
        401: Invalid password
    """
    data = request.get_json()

    if not data or 'password' not in data:
        return validation_error('Password is required', field='password')

    password = data.get('password')
    success, message = login(password)

    if success:
        return jsonify({
            'success': True,
            'message': message,
            'session': get_session_info()
        }), 200
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 401


@auth_bp.route('/logout', methods=['POST'])
def logout_route():
    """
    Log out and clear session.

    Returns:
        200: Logout successful
    """
    success, message = logout()

    return jsonify({
        'success': success,
        'message': message
    }), 200


@auth_bp.route('/session', methods=['GET'])
def session_route():
    """
    Check current session status.

    Returns:
        200: Session information
    """
    session_info = get_session_info()

    return jsonify({
        'authenticated': is_authenticated(),
        'session': session_info if is_authenticated() else None
    }), 200
