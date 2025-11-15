"""
Flask application factory for dashboard backend.
Creates and configures the Flask app with all extensions and routes.
"""
import os
import sys
from pathlib import Path
from flask import Flask, jsonify
from flask_cors import CORS
from flask_session import Session

from backend.config import get_config


def create_app(config_name=None):
    """
    Create and configure the Flask application.

    Args:
        config_name: Configuration name ('development', 'production', or None for auto-detect)

    Returns:
        Flask application instance
    """
    app = Flask(__name__, static_folder='static', static_url_path='')

    # Load configuration
    if config_name is None:
        config_class = get_config()
    else:
        from backend.config import config
        config_class = config.get(config_name, config['default'])

    app.config.from_object(config_class)

    # Startup checks
    _perform_startup_checks(app)

    # Initialize extensions
    CORS(app, origins=app.config['CORS_ORIGINS'], supports_credentials=True)
    Session(app)

    # Register blueprints (will be created in Phase 3+)
    _register_blueprints(app)

    # Register error handlers
    _register_error_handlers(app)

    # Health check endpoint
    @app.route('/api/health')
    def health():
        """Health check endpoint for monitoring."""
        from backend.services.database import check_database_connection

        db_status = 'connected' if check_database_connection() else 'disconnected'

        return jsonify({
            'status': 'healthy' if db_status == 'connected' else 'degraded',
            'database': db_status,
            'session_storage': 'ok' if Path(app.config['SESSION_DIR']).exists() else 'error',
            'environment': app.config['FLASK_ENV']
        })

    # Serve frontend static files in production
    @app.route('/')
    def index():
        """Serve the frontend index.html or placeholder."""
        if app.config['FLASK_ENV'] == 'production':
            return app.send_static_file('index.html')
        else:
            return jsonify({
                'message': 'Dashboard backend is running',
                'environment': 'development',
                'note': 'Frontend should be served by Vite dev server on port 5173'
            })

    return app


def _perform_startup_checks(app):
    """
    Perform startup checks to ensure critical resources are available.

    Args:
        app: Flask application instance

    Raises:
        SystemExit: If critical checks fail
    """
    # Check session directory
    session_dir = Path(app.config['SESSION_DIR'])
    if not session_dir.exists():
        try:
            session_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(session_dir, 0o755)
            app.logger.info(f"✓ Created session directory: {session_dir}")
        except Exception as e:
            app.logger.error(f"✗ Failed to create session directory: {e}")
            sys.exit(1)

    # Check session directory is writable
    if not os.access(session_dir, os.W_OK):
        app.logger.error(f"✗ Session directory is not writable: {session_dir}")
        sys.exit(1)

    # Check thumbnail directory
    thumbnail_dir = Path(app.config['THUMBNAIL_DIR'])
    if not thumbnail_dir.exists():
        try:
            thumbnail_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(thumbnail_dir, 0o755)
            app.logger.info(f"✓ Created thumbnail directory: {thumbnail_dir}")
        except Exception as e:
            app.logger.warning(f"⚠️  Failed to create thumbnail directory: {e}")

    # Check database path exists
    db_path = Path(app.config['DATABASE_PATH'])
    if not db_path.exists():
        app.logger.warning(
            f"⚠️  Database not found at {db_path}. "
            "Make sure the bot is running and has created the database."
        )

    app.logger.info("✓ Startup checks complete")


def _register_blueprints(app):
    """
    Register Flask blueprints for API routes.

    Args:
        app: Flask application instance
    """
    # Import blueprints (will be created in Phase 3+)
    try:
        from backend.routes import register_routes
        register_routes(app)
        app.logger.info("✓ Registered API routes")
    except ImportError:
        app.logger.warning("⚠️  API routes not yet implemented (Phase 3+)")


def _register_error_handlers(app):
    """
    Register global error handlers.

    Args:
        app: Flask application instance
    """
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found', 'message': str(e)}), 404

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error(f"Internal error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred. Please try again later.'
        }), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        """Catch-all exception handler."""
        app.logger.exception(f"Unhandled exception: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred. Please try again later.'
        }), 500


if __name__ == '__main__':
    # For development only - use gunicorn in production
    app = create_app('development')
    app.run(host='0.0.0.0', port=8080, debug=True)
