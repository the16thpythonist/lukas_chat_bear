"""
Database connection and session management for dashboard backend.
Provides SQLAlchemy engine and session management for the shared bot database.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
import logging

from backend.config import get_config

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine = None
_SessionFactory = None


def init_database(app=None):
    """
    Initialize the database engine and session factory.

    Args:
        app: Flask application instance (optional)

    Returns:
        SQLAlchemy engine instance
    """
    global _engine, _SessionFactory

    if _engine is not None:
        return _engine

    # Get database URI from config
    if app:
        database_uri = app.config['DATABASE_URI']
    else:
        config = get_config()
        database_uri = config.DATABASE_URI

    # Create engine with SQLite-specific settings
    # WAL mode is already enabled by the bot - we just need to connect
    _engine = create_engine(
        database_uri,
        connect_args={
            'check_same_thread': False,  # Allow multi-threading
            'timeout': 30  # 30 second timeout for lock acquisition
        },
        poolclass=StaticPool,  # Single connection pool for SQLite
        echo=False  # Set to True for SQL query logging in development
    )

    # Create session factory with scoped sessions
    _SessionFactory = scoped_session(
        sessionmaker(
            bind=_engine,
            autocommit=False,
            autoflush=False
        )
    )

    logger.info(f"✓ Database engine initialized: {database_uri}")
    return _engine


def get_engine():
    """
    Get the SQLAlchemy engine instance.

    Returns:
        SQLAlchemy engine

    Raises:
        RuntimeError: If database not initialized
    """
    if _engine is None:
        raise RuntimeError(
            "Database not initialized. Call init_database() first."
        )
    return _engine


def get_session():
    """
    Get a database session from the session factory.

    Returns:
        SQLAlchemy session instance

    Raises:
        RuntimeError: If database not initialized
    """
    if _SessionFactory is None:
        init_database()

    return _SessionFactory()


@contextmanager
def session_scope():
    """
    Provide a transactional scope for database operations.

    Usage:
        with session_scope() as session:
            user = session.query(User).first()

    Yields:
        SQLAlchemy session

    Note:
        Automatically commits on success, rolls back on exception.
        Dashboard mostly does read-only queries, but this is useful
        for manual action logging.
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database_connection():
    """
    Check if database connection is working.

    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        engine = get_engine() if _engine else init_database()
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


def cleanup_database():
    """
    Clean up database connections.
    Should be called on application shutdown.
    """
    global _engine, _SessionFactory

    if _SessionFactory:
        _SessionFactory.remove()

    if _engine:
        _engine.dispose()
        _engine = None
        _SessionFactory = None
        logger.info("✓ Database connections cleaned up")
