"""
API routes package for dashboard backend.
Registers all blueprint routes with the Flask application.
"""
import logging

logger = logging.getLogger(__name__)


def register_routes(app):
    """
    Register all API route blueprints with the Flask application.

    Args:
        app: Flask application instance

    Note:
        Routes are implemented in separate blueprint modules:
        - auth.py: Authentication routes (login, logout, session)
        - activity.py: Activity log routes (Phase 3)
        - images.py: Generated images routes (Phase 4)
        - events.py: Scheduled events routes (Phase 5)
        - controls.py: Manual control routes (Phase 6-7)
        - team.py: Team members routes (Phase 7)
    """
    # Phase 3: Authentication routes
    try:
        from backend.routes.auth import auth_bp
        app.register_blueprint(auth_bp, url_prefix='/api/auth')
        logger.info("✓ Registered auth routes")
    except ImportError:
        logger.warning("⚠️  Auth routes not yet implemented")

    # Phase 3: Activity log routes
    try:
        from backend.routes.activity import activity_bp
        app.register_blueprint(activity_bp, url_prefix='/api/activity')
        logger.info("✓ Registered activity routes")
    except ImportError:
        logger.warning("⚠️  Activity routes not yet implemented")

    # Phase 4: Images routes
    try:
        from backend.routes.images import images_bp
        app.register_blueprint(images_bp, url_prefix='/api/images')
        logger.info("✓ Registered images routes")
    except ImportError:
        logger.warning("⚠️  Images routes not yet implemented")

    # Phase 5: Events routes
    try:
        from backend.routes.events import events_bp
        app.register_blueprint(events_bp, url_prefix='/api/events')
        logger.info("✓ Registered events routes")
    except Exception as e:
        logger.warning(f"⚠️  Events routes error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    # Phase 6-7: Manual controls routes
    try:
        from backend.routes.controls import controls_bp
        app.register_blueprint(controls_bp, url_prefix='/api/controls')
        logger.info("✓ Registered controls routes")
    except ImportError:
        logger.warning("⚠️  Controls routes not yet implemented")

    # Phase 7: Team members routes
    try:
        from backend.routes.team import team_bp
        app.register_blueprint(team_bp, url_prefix='/api/team')
        logger.info("✓ Registered team routes")
    except ImportError:
        logger.warning("⚠️  Team routes not yet implemented")

    # Scheduled channel messages routes (new feature)
    try:
        from backend.routes.scheduled_events import scheduled_events_bp
        app.register_blueprint(scheduled_events_bp, url_prefix='/api/scheduled-events')
        logger.info("✓ Registered scheduled events routes")
    except ImportError as e:
        logger.warning(f"⚠️  Scheduled events routes not yet implemented: {e}")
    except Exception as e:
        logger.error(f"❌ Error registering scheduled events routes: {e}")
        import traceback
        traceback.print_exc()
