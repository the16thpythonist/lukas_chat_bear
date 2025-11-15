"""
Authentication middleware for dashboard backend.
Provides password-based authentication with session management.
"""
from functools import wraps
from flask import session, jsonify, request, current_app
import logging

logger = logging.getLogger(__name__)


def require_auth(f):
    """
    Decorator to require authentication for a route.

    Usage:
        @app.route('/api/protected')
        @require_auth
        def protected_route():
            return {'message': 'You are authenticated'}

    Returns:
        401 Unauthorized if not authenticated, otherwise calls the wrapped function
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            logger.warning(
                f"Unauthorized access attempt to {request.path} from {request.remote_addr}"
            )
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Authentication required. Please log in.'
            }), 401

        return f(*args, **kwargs)

    return decorated_function


def is_authenticated():
    """
    Check if the current session is authenticated.

    Returns:
        bool: True if authenticated, False otherwise
    """
    return session.get('authenticated', False)


def verify_password(password):
    """
    Verify the provided password against the configured admin password.

    Args:
        password: Password to verify

    Returns:
        bool: True if password matches, False otherwise
    """
    admin_password = current_app.config.get('DASHBOARD_ADMIN_PASSWORD')

    if not admin_password:
        logger.error("DASHBOARD_ADMIN_PASSWORD not configured")
        return False

    return password == admin_password


def login(password):
    """
    Authenticate a user with the provided password.

    Args:
        password: Password to verify

    Returns:
        tuple: (success: bool, message: str)
    """
    if not password:
        return False, 'Password is required'

    if verify_password(password):
        session['authenticated'] = True
        session['login_time'] = request.environ.get('REQUEST_TIME', None)
        session.permanent = False  # Session expires when browser closes

        logger.info(f"Successful login from {request.remote_addr}")
        return True, 'Login successful'
    else:
        logger.warning(f"Failed login attempt from {request.remote_addr}")
        return False, 'Invalid password'


def logout():
    """
    Log out the current session.

    Returns:
        tuple: (success: bool, message: str)
    """
    if 'authenticated' in session:
        session.pop('authenticated')

    if 'login_time' in session:
        session.pop('login_time')

    logger.info(f"User logged out from {request.remote_addr}")
    return True, 'Logout successful'


def get_session_info():
    """
    Get information about the current session.

    Returns:
        dict: Session information including authentication status
    """
    return {
        'authenticated': is_authenticated(),
        'login_time': session.get('login_time'),
        'session_id': session.get('_id')  # Flask session ID
    }
