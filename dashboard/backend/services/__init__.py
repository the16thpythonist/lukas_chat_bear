"""
Services package for dashboard backend.
Provides business logic and database query utilities.
"""

from backend.services.database import (
    init_database,
    get_engine,
    get_session,
    session_scope,
    check_database_connection,
    cleanup_database
)

from backend.services.query_builder import (
    paginate,
    build_activity_query,
    build_images_query,
    build_events_query,
    get_upcoming_events,
    get_completed_events
)

__all__ = [
    # Database services
    'init_database',
    'get_engine',
    'get_session',
    'session_scope',
    'check_database_connection',
    'cleanup_database',
    # Query builders
    'paginate',
    'build_activity_query',
    'build_images_query',
    'build_events_query',
    'get_upcoming_events',
    'get_completed_events',
]
